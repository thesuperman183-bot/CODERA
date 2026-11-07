"""Unit tests for Phase 10 Hindsight Inspector endpoints."""
from __future__ import annotations

import uuid
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.security import AuthenticatedContext, get_current_user, get_current_user_optional
from backend.database import Base, get_db
from backend.main import app
from backend.models import HindsightBank, RetainedFact, Review, ReviewMemory, Team, TeamRule, User

MOCK_USER_CTX = AuthenticatedContext(
    user_id="user-phase10-1",
    email="inspector@example.com",
    name="Inspector User",
    token_type="pat",
    team_roles={"team-phase10-a": "owner"},
)

TEST_REVIEW_ID = str(uuid.uuid4())
TEST_OTHER_REVIEW_ID = str(uuid.uuid4())


@pytest.fixture
def memory_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def override_get_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as session:
            # Seed team and facts
            team = Team(id="team-phase10-a", name="Inspector Core Team")
            session.add(team)

            bank = HindsightBank(
                id=str(uuid.uuid4()),
                team_id="team-phase10-a",
                bank_id="bank-team-a",
                bank_type="team",
                is_active=True,
            )
            session.add(bank)

            user = User(id="user-phase10-1", email="inspector@example.com", name="Inspector User")
            session.add(user)

            fact1 = RetainedFact(
                id="fact-1",
                user_id="user-phase10-1",
                team_id="team-phase10-a",
                content="Use parameterized queries for SQL operations.",
                hindsight_memory_id="hs-mem-1",
                tags=["sql", "database"],
            )
            fact2 = RetainedFact(
                id="fact-2",
                user_id="user-other-person",
                team_id="team-phase10-b",
                content="Unrelated fact from other team.",
                hindsight_memory_id="hs-mem-2",
                tags=["other"],
            )
            session.add_all([fact1, fact2])

            rule = TeamRule(
                id="rule-1",
                team_id="team-phase10-a",
                rule_text="Require docstrings on all exported functions.",
                created_by="user-phase10-1",
            )
            session.add(rule)

            # Seed review with memories
            rev = Review(
                id=TEST_REVIEW_ID,
                user_id="user-phase10-1",
                team_id="team-phase10-a",
                code_diff="diff --git a/test.py b/test.py",
                review_result="Review feedback: looks good",
                model_used="groq/llama-3.3-70b-versatile",
                status="completed",
                source="Web",
            )
            session.add(rev)

            mem1 = ReviewMemory(
                id=str(uuid.uuid4()),
                review_id=TEST_REVIEW_ID,
                memory_text="Ensure all endpoints validate JWT expiry.",
                hindsight_memory_id="mem-jwt-001",
                relevance_metadata={"source": "hindsight_recall", "bank_id": "team-phase10-a"},
            )
            mem2 = ReviewMemory(
                id=str(uuid.uuid4()),
                review_id=TEST_REVIEW_ID,
                memory_text="Always use constant-time comparison for tokens.",
                hindsight_memory_id=None,
                relevance_metadata={"source": "team_rule"},
            )
            session.add_all([mem1, mem2])

            # Seed review belonging to another team
            other_rev = Review(
                id=TEST_OTHER_REVIEW_ID,
                user_id="user-other-person",
                team_id="team-phase10-b",
                code_diff="diff --git a/secret.py b/secret.py",
                review_result="Private review feedback",
                model_used="groq/llama-3.3-70b-versatile",
                status="completed",
                source="CLI",
            )
            session.add(other_rev)

            await session.commit()
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER_CTX
    app.dependency_overrides[get_current_user_optional] = lambda: MOCK_USER_CTX

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_get_active_bank_info(memory_client: TestClient):
    resp = memory_client.get("/api/memories/active-bank?team_id=team-phase10-a")
    assert resp.status_code == 200
    data = resp.json()
    assert data["team_id"] == "team-phase10-a"
    assert data["team_name"] == "Inspector Core Team"
    assert data["bank_id"] == "bank-team-a"
    assert data["bank_type"] == "team"
    assert data["total_facts"] == 1
    assert data["total_rules"] == 1
    assert data["total_available_memories"] == 2


def test_list_retained_facts(memory_client: TestClient):
    resp = memory_client.get("/api/memories/facts?team_id=team-phase10-a")
    assert resp.status_code == 200
    facts = resp.json()
    assert len(facts) == 1
    assert facts[0]["id"] == "fact-1"
    assert facts[0]["memory_id"] == "hs-mem-1"
    assert facts[0]["content"] == "Use parameterized queries for SQL operations."
    assert "sql" in facts[0]["tags"]


def test_search_memories(memory_client: TestClient):
    with patch("backend.routers.memories.hindsight_service.recall") as mock_recall:
        mock_recall.return_value = [
            "Use parameterized queries for SQL operations.",
            "Sanitize all HTML outputs to mitigate XSS.",
        ]

        resp = memory_client.post("/api/memories/search?query=SQL%20injection&limit=5&team_id=team-phase10-a")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "SQL injection"
        assert data["count"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["relevance_rank"] == 1
        assert "parameterized queries" in data["results"][0]["text"]


def test_review_memory_trace(memory_client: TestClient):
    resp = memory_client.get(f"/api/memories/review-trace/{TEST_REVIEW_ID}")
    assert resp.status_code == 200
    trace = resp.json()
    assert trace["review_id"] == TEST_REVIEW_ID
    assert trace["total_injected"] == 2
    assert len(trace["injected_memories"]) == 2

    # Check that sources distinguish between hindsight recall and stored rules
    sources = [m["source_type"] for m in trace["injected_memories"]]
    assert "hindsight_recall" in sources
    assert "team_rule" in sources


def test_review_memory_trace_cross_team_denied(memory_client: TestClient):
    # MOCK_USER_CTX is not in team-phase10-b and is not user-other-person
    resp = memory_client.get(f"/api/memories/review-trace/{TEST_OTHER_REVIEW_ID}")
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"].lower()
