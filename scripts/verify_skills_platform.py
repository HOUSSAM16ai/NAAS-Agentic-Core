#!/usr/bin/env python3
"""
verify_skills_platform.py — تحقّق حيّ في-العملية لمنصّة الـ Skills (D-100).

يفحص:
  1. الـ registry يبني 14 Skill (12 ACTIVE + 2 FLAGGED) بلا ZOMBIE.
  2. `compose_text_refinement` يُشغِّل خط التنقية الحقيقي ويُرجِع نصاً منقَّحاً.
  3. الـ Skills المُفعَّلة من قدرات DORMANT تحترم العلم:
       • مُعطَّلة افتراضياً → تُرجِع None.
       • مُفعَّلة (ENABLE_*=1) → تُرجِع مخرَجاً (أو تتدهور رشيقاً).

يتطلّب تبعيات المشروع (pydantic, …) → يُشغَّل في Codespaces/CI، لا الـ sandbox.

Usage:
  python3 scripts/verify_skills_platform.py
  ENABLE_RETRIEVAL_RERANK_SKILL=1 ENABLE_MCP_TOOL_SKILL=1 python3 scripts/verify_skills_platform.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _ok(msg: str) -> None:
    print(f"✅ {msg}")


def _fail(msg: str) -> None:
    print(f"❌ {msg}")
    sys.exit(1)


async def main() -> None:
    print("=== Skills Platform live verification (D-100) ===\n")

    from app.services.skills.registry import (
        compose_text_refinement,
        get_skill_registry,
    )

    # 1) Registry
    reg = get_skill_registry()
    names = reg.names()
    if len(names) != 15:
        _fail(f"expected 15 skills, got {len(names)}: {names}")
    if len(reg.by_status("ACTIVE")) != 12:
        _fail(f"expected 12 ACTIVE, got {len(reg.by_status('ACTIVE'))}")
    if len(reg.by_status("FLAGGED")) != 2:
        _fail(f"expected 2 FLAGGED, got {len(reg.by_status('FLAGGED'))}")
    for d in reg.list():
        if not d.consumed_by:
            _fail(f"ZOMBIE skill (empty consumed_by): {d.name}")
    _ok(f"registry: {len(names)} skills, 12 ACTIVE + 2 FLAGGED, no ZOMBIE")

    # 2) compose_text_refinement (real skills)
    sample = "هذه إجابة تجريبية. <div>html</div> النتيجة $$x = 1$$."
    result = compose_text_refinement(sample, {"question": "ما قيمة x؟", "intent": "educational"})
    if not isinstance(result.text, str) or not result.text:
        _fail("compose_text_refinement returned empty text")
    _ok(
        f"compose: applied={list(result.applied_steps)} "
        f"failed={list(result.failed_steps)} len={len(result.text)}"
    )

    # 3) Flagged skills honor their flags
    from app.services.skills.mcp_tool_skill import MCPToolInput, get_mcp_tool_skill
    from app.services.skills.retrieval_rerank_skill import (
        RetrievalRerankInput,
        get_retrieval_rerank_skill,
    )

    rr_on = os.getenv("ENABLE_RETRIEVAL_RERANK_SKILL", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    rr_out = await get_retrieval_rerank_skill().retrieve(
        RetrievalRerankInput(query="نهاية دالة عند اللانهاية", top_k=5, top_n=3)
    )
    if rr_on:
        if rr_out is None:
            _fail("retrieval_rerank enabled but returned None")
        _ok(
            f"retrieval_rerank ENABLED → retrieved={rr_out.retrieved_count} reranked={rr_out.reranked_count} degraded={rr_out.degraded}"
        )
    else:
        if rr_out is not None:
            _fail("retrieval_rerank disabled but returned a result (flag leak)")
        _ok("retrieval_rerank DISABLED → None (correct, no behavior change)")

    mcp_on = os.getenv("ENABLE_MCP_TOOL_SKILL", "").strip().lower() in {"1", "true", "yes", "on"}
    mcp_out = await get_mcp_tool_skill().call(MCPToolInput(action="list"))
    if mcp_on:
        if mcp_out is None:
            _fail("mcp_tool enabled but returned None")
        _ok(f"mcp_tool ENABLED → tool_count={mcp_out.tool_count}")
    else:
        if mcp_out is not None:
            _fail("mcp_tool disabled but returned a result (flag leak)")
        _ok("mcp_tool DISABLED → None (correct, no behavior change)")

    print("\n=== ✅ Skills Platform verification passed ===")


if __name__ == "__main__":
    asyncio.run(main())
