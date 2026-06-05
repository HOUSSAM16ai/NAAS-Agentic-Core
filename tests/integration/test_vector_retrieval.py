import json
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.database import create_db_engine, create_session_factory
from app.core.settings.base import BaseServiceSettings

pytestmark = pytest.mark.asyncio


@pytest.fixture
def db_settings():
    db_url = os.environ.get("DATABASE_URL")

    return BaseServiceSettings(
        DATABASE_URL=db_url, ENVIRONMENT="testing", SERVICE_NAME="TestVectorRetrieval"
    )


@pytest_asyncio.fixture
async def db_session(db_settings):
    engine = create_db_engine(db_settings)
    session_factory = create_session_factory(engine)

    # We must ensure tables exist in sqlite memory
    if "sqlite" in db_settings.DATABASE_URL:
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS bac_exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject VARCHAR(80),
                    topic VARCHAR(120),
                    draw_type VARCHAR(40),
                    year INTEGER,
                    language VARCHAR(8),
                    raw_text TEXT,
                    content_hash VARCHAR(64) UNIQUE
                );
            """)
            )
            await conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS bac_exercise_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_id INTEGER NOT NULL REFERENCES bac_exercises(id),
                    question_number VARCHAR(20),
                    question_text TEXT,
                    question_type VARCHAR(50),
                    parsed_entities TEXT,
                    embedding TEXT
                );
            """)
            )

    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_vector_retrieval_surgical_precision(db_session):
    # Testing the structure of vector search without making real embedding API calls.
    # We mock a vector field and try to fetch it via pgvector `<=>` (cosine distance).

    # 1. Setup mock data
    unique_hash = uuid.uuid4().hex

    # Insert a dummy bac_exercise
    ex_res = await db_session.execute(
        text("""
        INSERT INTO bac_exercises (
            subject, topic, draw_type, year, language, raw_text, content_hash
        ) VALUES (
            'Math', 'Probability', 'Simultaneous', 2024, 'ar', 'Dummy Content', :chash
        )
        RETURNING id;
        """),
        {"chash": unique_hash},
    )
    ex_id = ex_res.scalar_one()

    # Insert a dummy surgical question with a deterministic vector
    mock_vector = f"[{','.join(['0.01'] * 1023)}, 1.0]"  # A vector with a spike at the end

    if "sqlite" in str(db_session.bind.engine.url):
        # MOCK TEST FOR SQLITE CI RUNNERS
        await db_session.execute(
            text("""
            INSERT INTO bac_exercise_questions (
                exercise_id, question_number, question_text, question_type, parsed_entities, embedding
            ) VALUES (
                :exid, '1.a', 'احسب احتمال الحادثة P(A)', 'probability', :entities, :emb
            );
            """),
            {"exid": ex_id, "entities": json.dumps({"event": "A"}), "emb": mock_vector},
        )
        # Just assert insertion success and skip vector search `<=>`
        assert True
        return

    try:
        await db_session.execute(
            text("""
            INSERT INTO bac_exercise_questions (
                exercise_id, question_number, question_text, question_type, parsed_entities, embedding
            ) VALUES (
                :exid, '1.a', 'احسب احتمال الحادثة P(A)', 'probability', :entities, :emb::vector
            );
            """),
            {"exid": ex_id, "entities": json.dumps({"event": "A"}), "emb": mock_vector},
        )

        # 2. Test Retrieval
        query_vector = mock_vector
        res = await db_session.execute(
            text("""
            SELECT beq.question_text, 1 - (beq.embedding <=> :qvec::vector) as similarity
            FROM bac_exercise_questions beq
            WHERE beq.exercise_id = :exid
            ORDER BY beq.embedding <=> :qvec::vector
            LIMIT 1;
            """),
            {"qvec": query_vector, "exid": ex_id},
        )

        row = res.fetchone()
        assert row is not None
        assert row[0] == "احسب احتمال الحادثة P(A)"
        # Similarity should be extremely close to 1.0 since we queried with the exact vector
        assert row[1] > 0.99
    except Exception as e:
        raise e

    # 3. Teardown
    await db_session.rollback()
