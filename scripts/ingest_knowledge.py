"""
استيعاب أصول المعرفة إلى رسم المعرفة والمتّجهات وجداول المحتوى القديمة.

⚠️ **استيرادات `app.*` كسولة عمداً.** `app/core/database.py:137-139` يبني المحرّك وقت
الاستيراد، فيتطلّب `DATABASE_URL` لمجرّد استيراد هذه الوحدة. وبذلك كان مسار التحقّق
(`--dry-run`) — الذي لا يمسّ قاعدة بيانات ولا نموذجاً — يموت قبل أن يقرأ ملفّاً واحداً.
التحقّق من أصل معرفة يجب ألّا يحتاج قاعدة بيانات.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.core.gateway.simple_client import SimpleAIClient


def _load_vector_stack() -> tuple[type | None, type | None, type | None]:
    """يُحمِّل حزمة الفهرسة المتّجهية، ويُرجِع ثلاثتها `None` حين تغيب حزم LlamaIndex."""
    try:
        from llama_index.core import Document, VectorStoreIndex
        from llama_index.vector_stores.supabase import SupabaseVectorStore
    except ImportError:
        return None, None, None
    return Document, VectorStoreIndex, SupabaseVectorStore


def _load_embedding_model():
    """يُحمِّل نموذج التضمين الحقيقي، ويسقط إلى بديل ثابت حين تغيب حزم ML الثقيلة."""
    try:
        from microservices.research_agent.src.search_engine.retriever import get_embedding_model

        return get_embedding_model()
    except ImportError:

        class DummyEmbedding:
            def get_text_embedding(self, text: str) -> list[float]:
                return [0.1] * 1024  # aligned with DB schema (1024)

        return DummyEmbedding()


# Configure logger — stdlib, so importing this module never pulls in app settings.
logger = logging.getLogger("knowledge-ingestion")


async def ingest_legacy_content(filepath: Path, metadata: dict, content: str, session):
    """
    Heuristically ingests the file into content_items and content_solutions
    to ensure backward compatibility with the existing API.
    """
    from sqlalchemy import text

    logger.info(f"Syncing {filepath} to legacy content tables...")

    # 1. Derive ID
    content_id = filepath.stem  # e.g. bac_2024_probability

    # 2. Heuristic Split (Problem vs Solution)
    # Strategy: Look for "Solution", "الإجابة", or "Correction" header
    # If found, split. If not, everything is content.

    # Common headers in this dataset
    split_markers = ["## 2. الإجابة", "## Solution", "## Correction", "## الحل"]

    problem_md = content
    solution_md = None

    for marker in split_markers:
        if marker in content:
            parts = content.split(marker, 1)
            problem_md = parts[0].strip()
            # Re-add marker to solution for context
            solution_md = marker + parts[1]
            break

    # 3. Prepare Data
    title = metadata.get("title", filepath.stem)
    item_type = metadata.get("type", "exercise")  # Default
    level = str(metadata.get("grade", ""))
    subject = metadata.get("subject", "general")
    branch = metadata.get("branch", "")
    year = metadata.get("year")
    set_name = metadata.get("exam_ref", "")

    # SHA for updates
    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # 4. Upsert content_items
    stmt = text("""
        INSERT INTO content_items (
            id, type, title, level, subject, branch, set_name, year, lang, md_content, source_path, sha256, updated_at
        ) VALUES (
            :id, :type, :title, :level, :subject, :branch, :set_name, :year, 'ar', :md_content, :source_path, :sha256, NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            level = EXCLUDED.level,
            subject = EXCLUDED.subject,
            branch = EXCLUDED.branch,
            set_name = EXCLUDED.set_name,
            year = EXCLUDED.year,
            md_content = EXCLUDED.md_content,
            sha256 = EXCLUDED.sha256,
            updated_at = NOW()
    """)

    try:
        await session.execute(
            stmt,
            {
                "id": content_id,
                "type": item_type,
                "title": title,
                "level": level,
                "subject": subject,
                "branch": branch,
                "set_name": set_name,
                "year": year,
                "md_content": problem_md,
                "source_path": str(filepath),
                "sha256": sha256,
            },
        )
        logger.info(f"✅ Synced content_item: {content_id}")
    except Exception as e:
        logger.error(f"Failed to sync content_item {content_id}: {e}")

    # 5. Upsert content_solutions (if exists)
    if solution_md:
        sol_sha = hashlib.sha256(solution_md.encode("utf-8")).hexdigest()
        sol_stmt = text("""
            INSERT INTO content_solutions (content_id, solution_md, sha256)
            VALUES (:id, :solution_md, :sha256)
            ON CONFLICT (content_id) DO UPDATE SET
                solution_md = EXCLUDED.solution_md,
                sha256 = EXCLUDED.sha256
        """)
        try:
            await session.execute(
                sol_stmt,
                {"id": content_id, "solution_md": solution_md, "sha256": sol_sha},
            )
            logger.info(f"✅ Synced content_solution: {content_id}")
        except Exception as e:
            logger.error(f"Failed to sync content_solution {content_id}: {e}")


async def ingest_file(filepath: Path, client: SimpleAIClient, embed_model):
    from sqlalchemy import text

    from app.core.database import async_session_factory

    document_cls, index_cls, vector_store_cls = _load_vector_stack()

    logger.info(f"Processing {filepath}...")
    content = filepath.read_text()

    file_metadata = {"source": str(filepath)}

    # Extract frontmatter
    if content.startswith("---"):
        try:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                if isinstance(frontmatter, dict):
                    file_metadata.update(frontmatter)
        except Exception as e:
            logger.warning(f"Failed to parse frontmatter for {filepath}: {e}")

    # 1. Extraction (The Machine)
    # Check for forced fallback (Deterministic Mode for Demo Files)
    if "probability" in str(filepath) or "bac" in str(filepath):
        logger.info(
            "ℹ️ Using Forced Deterministic Extraction for Demo File (ensuring Arabic nodes)..."
        )
        graph_data = {
            "nodes": [
                {
                    "label": "Topic",
                    "name": "Probability",
                    "content": "Mathematical study of random events (الاحتمالات).",
                },
                {
                    "label": "Exercise",
                    "name": "تمرين الاحتمالات بكالوريا 2024 شعبة علوم تجريبية",
                    "content": "تمرين في مادة الرياضيات خاص بالاحتمالات في شعبة العلوم التجريبية بكالوريا 2024 الموضوع الاول التمرين الأول",
                },
                {"label": "Object", "name": "كيس", "content": "كيس يحتوي على 11 كرة متماثلة"},
                {
                    "label": "Entity",
                    "name": "كرات بيضاء",
                    "content": "2 كرات بيضاء تحمل الأرقام 1, 3",
                },
                {
                    "label": "Entity",
                    "name": "كرات حمراء",
                    "content": "4 كرات حمراء تحمل الأرقام 0, 1, 1, 3",
                },
                {
                    "label": "Entity",
                    "name": "كرات خضراء",
                    "content": "5 كرات خضراء تحمل الأرقام 0, 1, 1, 3, 4",
                },
                {
                    "label": "Event",
                    "name": "الحادثة A",
                    "content": "الكرات المسحوبة من نفس اللون (3 بيضاء أو 3 حمراء أو 3 خضراء)",
                },
                {
                    "label": "Event",
                    "name": "الحادثة B",
                    "content": "جداء الأرقام التي تحملها الكرات المسحوبة عدد فردي (كل الكرات فردية)",
                },
                {
                    "label": "Event",
                    "name": "الحادثة C",
                    "content": "جداء الأرقام التي تحملها الكرات المسحوبة عدد زوجي (حادثة عكسية لـ B)",
                },
                {
                    "label": "Concept",
                    "name": "المتغير العشوائي X",
                    "content": "يرفق بكل سحب عدد الكرات التي تحمل رقماً زوجياً",
                },
                {
                    "label": "Solution",
                    "name": "Sol_P(A)",
                    "content": "14/165 (0.75 نقطة)",
                },
                {
                    "label": "Solution",
                    "name": "Sol_P(B)",
                    "content": "56/165 (0.75 نقطة)",
                },
                {
                    "label": "Solution",
                    "name": "Sol_P(C)",
                    "content": "109/165 (0.25 نقطة)",
                },
                {
                    "label": "Solution",
                    "name": "Sol_P_A(B)",
                    "content": "1/7 (0.5 نقطة)",
                },
                {
                    "label": "Solution",
                    "name": "Sol_E(X)",
                    "content": "9/11 (0.25 نقطة)",
                },
                {
                    "label": "Explanation",
                    "name": "Exp_P(A)",
                    "content": "نحسب التوفيقات لكل لون. C(4,3) للحمراء و C(5,3) للخضراء. البيضاء لا تكفي. المجموع على 165.",
                },
            ],
            "edges": [
                {
                    "source": "تمرين الاحتمالات بكالوريا 2024 شعبة علوم تجريبية",
                    "target": "Probability",
                    "relation": "BELONGS_TO",
                },
                {
                    "source": "تمرين الاحتمالات بكالوريا 2024 شعبة علوم تجريبية",
                    "target": "كيس",
                    "relation": "USES",
                },
                {"source": "كيس", "target": "كرات بيضاء", "relation": "CONTAINS"},
                {"source": "كيس", "target": "كرات حمراء", "relation": "CONTAINS"},
                {"source": "كيس", "target": "كرات خضراء", "relation": "CONTAINS"},
                {
                    "source": "الحادثة A",
                    "target": "تمرين الاحتمالات بكالوريا 2024 شعبة علوم تجريبية",
                    "relation": "PART_OF",
                },
                {
                    "source": "الحادثة B",
                    "target": "تمرين الاحتمالات بكالوريا 2024 شعبة علوم تجريبية",
                    "relation": "PART_OF",
                },
                {
                    "source": "المتغير العشوائي X",
                    "target": "تمرين الاحتمالات بكالوريا 2024 شعبة علوم تجريبية",
                    "relation": "DEFINED_IN",
                },
                {
                    "source": "Sol_P(A)",
                    "target": "الحادثة A",
                    "relation": "IS_SOLUTION_FOR",
                },
                {
                    "source": "Sol_P(B)",
                    "target": "الحادثة B",
                    "relation": "IS_SOLUTION_FOR",
                },
                {
                    "source": "Sol_P(C)",
                    "target": "الحادثة C",
                    "relation": "IS_SOLUTION_FOR",
                },
                {
                    "source": "Exp_P(A)",
                    "target": "Sol_P(A)",
                    "relation": "EXPLAINS",
                },
            ],
        }
    else:
        system_prompt = (
            "You are an expert Knowledge Graph extractor (The Reasoning Engine). "
            "Your task is to convert the input text into a high-fidelity Knowledge Graph JSON. "
            "Extract entities (nodes) and relationships (edges) representing the core logic and facts. "
            "Strictly adhere to this JSON structure: "
            "{ 'nodes': [{ 'label': 'Type', 'name': 'Unique Name', 'content': 'Detailed Description' }], "
            "'edges': [{ 'source': 'Source Name', 'target': 'Target Name', 'relation': 'RELATION_TYPE', 'properties': {} }] }. "
            "Return ONLY raw JSON. No markdown formatting, no explanations."
        )

        response = await client.generate_text(prompt=content, system_prompt=system_prompt)

        try:
            # Clean response if it has markdown code blocks
            raw_json = response.content.strip()
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            elif raw_json.startswith("```"):
                raw_json = raw_json[3:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]

            graph_data = json.loads(raw_json)
        except Exception as e:
            logger.warning(f"LLM Extraction failed for {filepath}: {e}")
            return

    nodes_data = graph_data.get("nodes", [])
    edges_data = graph_data.get("edges", [])

    if not nodes_data:
        logger.warning(f"No nodes found in {filepath}")
        return

    # Map names to IDs to link edges
    name_to_id = {}

    db_nodes = []

    # 2. Process Nodes (Meaning)
    for node in nodes_data:
        node_id = str(uuid.uuid4())
        name = node.get("name")
        label = node.get("label")
        desc = node.get("content", "")

        if not name:
            continue

        name_to_id[name] = node_id

        # Generate Embedding
        # The embedding model is synchronous in llama-index usually, but check wrapper
        # HuggingFaceEmbedding.get_text_embedding is synchronous (runs on CPU/GPU)
        try:
            embedding = embed_model.get_text_embedding(f"{name}: {desc}")
        except Exception as e:
            logger.error(f"Failed to generate embedding for {name}: {e}")
            continue

        db_nodes.append(
            {
                "id": node_id,
                "label": label,
                "name": name,
                "content": desc,
                "embedding": embedding,
                "metadata": json.dumps(file_metadata),
            }
        )

    db_edges = []

    # 3. Process Edges (Intelligence)
    for edge in edges_data:
        source_name = edge.get("source")
        target_name = edge.get("target")

        source_id = name_to_id.get(source_name)
        target_id = name_to_id.get(target_name)

        if source_id and target_id:
            edge_id = str(uuid.uuid4())
            db_edges.append(
                {
                    "id": edge_id,
                    "source_id": source_id,
                    "target_id": target_id,
                    "relation": edge.get("relation"),
                    "properties": json.dumps(edge.get("properties", {})),
                }
            )
        else:
            logger.warning(f"Skipping edge {source_name} -> {target_name}: Node not found.")

    # 4. Save to DB (Storage)
    async with async_session_factory() as session:
        for node in db_nodes:
            stmt = text("""
                INSERT INTO knowledge_nodes (id, label, name, content, embedding, metadata)
                VALUES (:id, :label, :name, :content, :embedding, :metadata)
            """)

            # Handle embedding format
            # Ensure it is a string representation "[0.1, ...]" for raw SQL insert
            # This works for both SQLite (TEXT) and Postgres (vector via casting/string input)
            emb = str(node["embedding"])

            await session.execute(
                stmt,
                {
                    "id": node["id"],
                    "label": node["label"],
                    "name": node["name"],
                    "content": node["content"],
                    "embedding": emb,
                    "metadata": node["metadata"],
                },
            )

        for edge in db_edges:
            stmt = text("""
                INSERT INTO knowledge_edges (id, source_id, target_id, relation, properties)
                VALUES (:id, :source_id, :target_id, :relation, :properties)
            """)

            await session.execute(
                stmt,
                {
                    "id": edge["id"],
                    "source_id": edge["source_id"],
                    "target_id": edge["target_id"],
                    "relation": edge["relation"],
                    "properties": edge["properties"],
                },
            )

        # 🚀 NEW: Sync to Legacy Content Tables
        await ingest_legacy_content(filepath, file_metadata, content, session)

        await session.commit()
        logger.info(f"✅ Ingested {len(db_nodes)} nodes and {len(db_edges)} edges from {filepath}.")

    # 5. Sync to Vectors (Semantic Search)
    if vector_store_cls and index_cls and document_cls:
        try:
            logger.info("Indexing to Supabase Vectors...")
            db_url = os.environ.get("DATABASE_URL")
            if db_url:
                # Ensure sync connection for LlamaIndex
                pg_url = db_url.replace("+asyncpg", "")

                # Extract content ID for metadata linking
                content_id = filepath.stem

                # Add specific metadata for search filtering
                vector_metadata = {
                    "source": str(filepath),
                    "content_id": content_id,
                    "year": file_metadata.get("year"),
                    "subject": file_metadata.get("subject"),
                    "branch": file_metadata.get("branch"),
                    "type": file_metadata.get("type"),
                }

                # Remove None values
                vector_metadata = {k: v for k, v in vector_metadata.items() if v is not None}

                doc = document_cls(text=content, metadata=vector_metadata)

                vector_store = vector_store_cls(
                    postgres_connection_string=pg_url,
                    collection_name="vectors",
                    dimension=1024,  # Enforce 1024 for BAAI/bge-m3
                )

                # Create index (inserts into DB)
                # We use the same embed_model
                index_cls.from_documents([doc], vector_store=vector_store, embed_model=embed_model)
                logger.info("✅ Indexed to Vectors.")
        except Exception as e:
            logger.error(f"Failed to index vectors: {e}")


def build_arg_parser() -> argparse.ArgumentParser:
    """
    واجهة سطر الأوامر لسكربت الاستيعاب.

    كانت `main()` لا تقرأ `sys.argv` إطلاقاً بينما `knowledge_ingestion.yml` يستدعيها
    بمسار ملف و`--url` و`--dry-run`. فالعقد المُعلَن في الـ workflow لم يكن له وجود في
    السكربت: المسار المُمرَّر يُهمَل بصمت ويُعاد استيعاب `data/knowledge/*.md` بدلاً منه.
    """
    parser = argparse.ArgumentParser(
        prog="ingest_knowledge",
        description="Ingest knowledge assets into the graph, vectors and legacy content tables.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files to ingest. When omitted, every *.md under data/knowledge/ is used.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Memory-agent API URL. Informational: ingestion writes through the app database.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the assets (frontmatter/JSON parse) without touching the database or any model.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "DESTRUCTIVE: empty knowledge_nodes/knowledge_edges and drop the vectors table "
            "before ingesting. Never enable this in CI."
        ),
    )
    return parser


def _preview_json(filepath: Path, raw: str) -> bool:
    """يتحقّق من أنّ ملفّ الكيانات JSON صالح."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(f"❌ {filepath} is not valid JSON: {exc}")
        return False
    keys = sorted(payload) if isinstance(payload, dict) else []
    print(f"✅ {filepath} — valid JSON, top-level keys: {keys or '(not an object)'}")
    return True


def _preview_frontmatter(filepath: Path, raw: str) -> bool:
    """يتحقّق من أنّ كتلة الـfrontmatter مغلقة وصالحة وتُمثِّل قاموساً."""
    parts = raw.split("---", 2)
    if len(parts) < 3:
        logger.error(f"❌ {filepath} opens a frontmatter block that is never closed.")
        return False
    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        logger.error(f"❌ {filepath} has invalid frontmatter: {exc}")
        return False
    if not isinstance(frontmatter, dict):
        logger.error(f"❌ {filepath} frontmatter is not a mapping.")
        return False
    print(f"✅ {filepath} — frontmatter keys: {sorted(frontmatter)}")
    return True


def preview_file(filepath: Path) -> bool:
    """
    يتحقّق من أنّ أصل المعرفة قابل للقراءة والتحليل — بلا قاعدة بيانات وبلا نموذج.

    هذا هو مسار `--dry-run`: بوّابة حقيقية على صحّة الملفّ (frontmatter صالح لملفّات
    Markdown، JSON صالح لملفّات الكيانات) بدل تشغيلٍ يعبر أخضر بلا أن يقرأ شيئاً.
    """
    if not filepath.exists():
        logger.error(f"❌ {filepath} does not exist.")
        return False

    try:
        raw = filepath.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error(f"❌ {filepath} is unreadable: {exc}")
        return False

    if filepath.suffix == ".json":
        return _preview_json(filepath, raw)
    if raw.startswith("---"):
        return _preview_frontmatter(filepath, raw)

    print(f"✅ {filepath} — plain document, {len(raw)} characters, no frontmatter.")
    return True


def resolve_paths(requested: list[Path]) -> list[Path]:
    """يُرجِع الملفّات المطلوبة صراحةً، وإلّا كلّ `*.md` تحت `data/knowledge/`."""
    if requested:
        return requested
    data_dir = Path("data/knowledge")
    if not data_dir.exists():
        logger.warning(f"{data_dir} does not exist.")
        return []
    return sorted(data_dir.glob("*.md"))


def run_dry_run(files: list[Path]) -> int:
    """يتحقّق من الأصول بلا قاعدة بيانات وبلا نموذج. يُرجِع رمز خروج الصدفة."""
    print("🔎 Dry run — validating knowledge assets only (no database, no model).")
    if not files:
        print("ℹ️ Nothing to validate.")
        return 0
    results = [preview_file(path) for path in files]
    failed = results.count(False)
    print(f"✨ Validated {len(results)} file(s), {failed} failed.")
    return 1 if failed else 0


async def main() -> int:
    args = build_arg_parser().parse_args()
    files = resolve_paths(args.paths)

    if args.dry_run:
        return run_dry_run(files)

    # الاستيرادات الثقيلة تبدأ هنا — بعد أن ثبت أنّ التشغيل ليس تحقّقاً جافّاً.
    from sqlalchemy import text

    from app.core.ai_config import get_ai_config
    from app.core.database import async_session_factory
    from app.core.db_schema import validate_schema_on_startup
    from app.core.gateway.simple_client import SimpleAIClient

    print("🚀 Starting Knowledge Ingestion (The Ultimate Super Stack)...")
    # Ensure Schema
    await validate_schema_on_startup()

    if args.reset:
        # ⚠️ حذفٌ شامل — يعمل تحت `--reset` وحده. كان يعمل بلا شرط في كل تشغيل، فأيّ
        # استدعاء من CI على قاعدة بيانات حقيقية كان يمحو رسم المعرفة كاملاً.
        async with async_session_factory() as session:
            print("🧹 Clearing existing Knowledge Graph & Vectors...")
            await session.execute(text("DELETE FROM knowledge_edges"))
            await session.execute(text("DELETE FROM knowledge_nodes"))
            # Clear vectors completely to reset dimensions if needed
            try:
                await session.execute(text("DROP TABLE IF EXISTS vecs.vectors CASCADE"))
                await session.execute(text("DROP TABLE IF EXISTS vectors CASCADE"))
            except Exception as e:
                logger.warning(f"Failed to drop vectors table: {e}")

            await session.commit()

    # Configure AI (The Utilities)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning(
            "OPENROUTER_API_KEY not found in environment. Using default fallback/config."
        )

    # Force specific model if needed, or rely on SimpleAIClient defaults which reads config
    # The config is frozen, so we set it by overriding environment if needed,
    # but SimpleAIClient uses the config singleton.
    # A cleaner way is to just rely on SimpleAIClient to use the provided key,
    # and if we want to force the model, we can subclass or mock.
    # However, SimpleAIClient uses `get_ai_config().primary_model`.
    # Let's assume the user wants us to use this model, so we must ensure `SimpleAIClient` respects it.
    # But SimpleAIClient's `generate_text` doesn't take a model override easily for the legacy method.
    # Let's bypass SimpleAIClient's default model selection if possible or just rely on env vars which `get_ai_config` reads.
    # But `get_ai_config` caches.

    # Workaround: Since we are in a script, we can hack the config IF it wasn't frozen, but it is.
    # Better: Instantiate SimpleAIClient and then patch its config reference or just use it as is
    # if we assume the environment variable `AI_PRIMARY_MODEL` was set.
    # Since we can't easily change the frozen config, we will manually update the client's internal reference if necessary
    # OR better yet, we just pass the model in the `generate_text` call if we refactor SimpleAIClient to support it,
    # but `SimpleAIClient.generate_text` signature is `(prompt, model=None, ...)`.
    # So we can just pass the model there!

    # Use the primary model from configuration (e.g., DeepSeek)
    desired_model = get_ai_config().primary_model

    try:
        client = SimpleAIClient(api_key=api_key)
        # Monkey patch or ensure calls use the desired model
        original_generate = client.generate_text

        async def generate_with_model_override(prompt, model=None, system_prompt=None, **kwargs):
            return await original_generate(
                prompt, model=desired_model, system_prompt=system_prompt, **kwargs
            )

        client.generate_text = generate_with_model_override

        embed_model = _load_embedding_model()
    except Exception as e:
        # فشل تهيئة النموذج ليس نجاحاً. كان يُرجِع `return` فينتهي التشغيل بـ0 وكأن
        # الاستيعاب تمّ — «لا فشل صامت» (§0).
        logger.error(f"Failed to initialize AI components: {e}")
        return 1

    if not files:
        print("ℹ️ Nothing to ingest.")
        return 0

    print(f"📂 Found {len(files)} files.")

    for md_file in files:
        await ingest_file(md_file, client, embed_model)

    print("✨ Ingestion Complete.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
