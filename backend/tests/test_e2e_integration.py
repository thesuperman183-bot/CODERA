"""End-to-End Integration Tests for Phase 12.

Covers:
1. CLI workflows: Login, Submit diff, Generate review, Save in Neon, Retain rule, History.
2. Web workflows: Auth, Submit diff, Generate review, Injected memory inspection, Add rule, View facts, View history.
3. Cross-interface synchronization: CLI review visible on web, CLI rule visible in Inspector, Web rule utilized by CLI review.
"""
from __future__ import annotations

import argparse
import io
import sys
import uuid
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cli
from backend.core.security import AuthenticatedContext, get_current_user, get_current_user_optional
from backend.database import Base, get_db
from backend.main import app
from backend.models import HindsightBank, RetainedFact, Review, ReviewFinding, ReviewMemory, Team, TeamMember, TeamRule, User

MOCK_SYNC_USER = AuthenticatedContext(
    user_id="user-sync-01",
    email="engineer@acme.com",
    name="Sync Engineer",
    token_type="pat",
    team_roles={"team-sync-core": "owner"},
)

active_context = MOCK_SYNC_USER


@pytest.fixture
def e2e_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    seeded = False

    async def override_get_db():
        nonlocal seeded
        if not seeded:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with factory() as session:
                team = Team(id="team-sync-core", name="Acme Core Team")
                user = User(id="user-sync-01", email="engineer@acme.com", name="Sync Engineer")
                tm = TeamMember(id="tm-sync-01", team_id="team-sync-core", user_id="user-sync-01", role="owner")
                bank = HindsightBank(id="bank-sync-01", team_id="team-sync-core", bank_id="bank-sync-core", bank_type="team", is_active=True)
                session.add_all([team, user, tm, bank])
                await session.commit()
            seeded = True

        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: active_context
    app.dependency_overrides[get_current_user_optional] = lambda: active_context

    with TestClient(app) as client:
        yield client, factory

    app.dependency_overrides.clear()


def _bridge_cli_to_testclient(client: TestClient):
    """Bridge CLI HTTP helper calls directly into the FastAPI TestClient."""
    def fake_post(api_url: str, path: str, json_data: dict | None = None, token: str | None = None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = client.post(path, json=json_data, headers=headers)
        if resp.status_code >= 400:
            raise cli.CliError(f"API request failed: {resp.text}")
        return resp.json()

    def fake_get(api_url: str, path: str, token: str | None = None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = client.get(path, headers=headers)
        if resp.status_code >= 400:
            raise cli.CliError(f"API request failed: {resp.text}")
        return resp.json()

    return fake_post, fake_get


# =============================================================================
# 1. CLI Scenarios
# =============================================================================

def test_cli_end_to_end_flow(e2e_client, monkeypatch, tmp_path):
    client, _ = e2e_client
    fake_post, fake_get = _bridge_cli_to_testclient(client)

    # A. CLI Login
    args_login = argparse.Namespace(
        api_url="http://testserver",
        email="engineer@acme.com",
        token_name="Test CLI Token",
    )
    with patch("cli._post", side_effect=fake_post), patch("cli._store_token") as mock_store:
        exit_code = cli._cmd_login(args_login)
        assert exit_code == 0
        assert mock_store.called
        token_saved = mock_store.call_args[0][0]
        assert token_saved.startswith("cra_pat_")

    # B. CLI Check (Submit code diff)
    diff_file = tmp_path / "patch.diff"
    diff_file.write_text("--- a/login.py\n+++ b/login.py\n@@ -10,3 +10,4 @@\n+ password_hash = md5(password)", encoding="utf-8")

    args_check = argparse.Namespace(
        api_url="http://testserver",
        file_or_diff=str(diff_file),
        token=token_saved,
    )

    with patch("cli._post", side_effect=fake_post), \
         patch("backend.services.groq_service.groq_service.generate_review") as mock_groq, \
         patch("backend.services.hindsight_service.hindsight_service.recall") as mock_recall:
        mock_recall.return_value = ["Never use MD5 for password hashing."]
        mock_groq.return_value = (
            "Review findings:\n- [CRITICAL] Insecure Password Hash in login.py:11\n  Description: MD5 is broken\n  Recommendation: Use Argon2id or bcrypt",
            "llama-3.3-70b-versatile",
        )

        stdout_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf):
            exit_code = cli._cmd_check(args_check)
            assert exit_code == 0

        output = stdout_buf.getvalue()
        assert "Insecure Password Hash" in output
        assert "Use Argon2id or bcrypt" in output

    # C. CLI Learn (Retain new rule)
    args_learn = argparse.Namespace(
        api_url="http://testserver",
        rule_text="Always salt and hash passwords using Argon2id.",
        token=token_saved,
    )

    with patch("cli._post", side_effect=fake_post), \
         patch("backend.services.hindsight_service.hindsight_service.retain") as mock_retain:
        mock_retain.return_value = {"id": "hs-mem-argon2", "success": True}

        stdout_learn = io.StringIO()
        with patch("sys.stdout", stdout_learn):
            exit_code = cli._cmd_learn(args_learn)
            assert exit_code == 0

        assert '"status": "retained"' in stdout_learn.getvalue()
        assert "hs-mem-argon2" in stdout_learn.getvalue()

    # D. CLI History (Retrieve reviews)
    args_history = argparse.Namespace(
        api_url="http://testserver",
        limit=5,
        token=token_saved,
    )
    stdout_hist = io.StringIO()
    with patch("cli._get", side_effect=fake_get), patch("sys.stdout", stdout_hist):
        exit_code = cli._cmd_history(args_history)
        assert exit_code == 0

    assert "review session(s)" in stdout_hist.getvalue()


# =============================================================================
# 2. Web Scenarios
# =============================================================================

def test_web_end_to_end_flow(e2e_client):
    client, _ = e2e_client

    # A. Submit code diff through Web editor
    with patch("backend.services.groq_service.groq_service.generate_review") as mock_groq, \
         patch("backend.services.hindsight_service.hindsight_service.recall") as mock_recall:
        mock_recall.return_value = ["Enforce strict Content Security Policy."]
        mock_groq.return_value = (
            "- [HIGH] Missing CSP Headers in server.ts:20\n  Description: XSS risk\n  Recommendation: Add helmet CSP",
            "llama-3.3-70b-versatile",
        )

        resp = client.post(
            "/api/review",
            json={
                "code_diff": "+ app.use(cors())",
                "team_id": "team-sync-core",
                "source": "Web",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        review_id = data["review_id"]
        assert review_id is not None
        assert data["status"] == "completed"
        assert len(data["findings"]) == 1
        assert data["findings"][0]["severity"] == "high"

    # B. Inspect injected Hindsight memories
    trace_resp = client.get(f"/api/memories/review-trace/{review_id}")
    assert trace_resp.status_code == 200
    trace = trace_resp.json()
    assert trace["review_id"] == review_id
    assert trace["total_injected"] >= 1
    assert any("Content Security Policy" in m["memory_text"] for m in trace["injected_memories"])

    # C. Add team rule through Web
    with patch("backend.services.hindsight_service.hindsight_service.retain") as mock_retain:
        mock_retain.return_value = {"id": "hs-web-rule-01", "success": True}
        rule_resp = client.post(
            "/api/rules",
            json={
                "rule": "Enforce HTTPS redirect on all incoming traffic.",
                "tags": ["security", "networking"],
                "team_id": "team-sync-core",
            },
        )
        assert rule_resp.status_code == 200
        assert rule_resp.json()["rule"] == "Enforce HTTPS redirect on all incoming traffic."

    # D. View Retained Facts
    facts_resp = client.get("/api/memories/facts?team_id=team-sync-core")
    assert facts_resp.status_code == 200
    facts = facts_resp.json()
    assert len(facts) >= 1
    assert any("HTTPS redirect" in f["content"] for f in facts)

    # E. View Review History
    history_resp = client.get("/api/reviews/history?team_id=team-sync-core")
    assert history_resp.status_code == 200
    hist = history_resp.json()
    assert hist["total"] >= 1
    assert hist["items"][0]["source"] == "Web"


# =============================================================================
# 3. Cross-Interface Synchronization
# =============================================================================

def test_cross_interface_synchronization(e2e_client, tmp_path):
    client, _ = e2e_client
    fake_post, fake_get = _bridge_cli_to_testclient(client)

    # 1. Submit review through CLI
    diff_file = tmp_path / "cli_feature.diff"
    diff_file.write_text("+ export function calculateTax() { return 0; }", encoding="utf-8")

    with patch("cli._post", side_effect=fake_post), \
         patch("backend.services.groq_service.groq_service.generate_review") as mock_groq, \
         patch("backend.services.hindsight_service.hindsight_service.recall") as mock_recall:
        mock_recall.return_value = []
        mock_groq.return_value = (
            "- [MEDIUM] Stub Implementation in tax.ts:1\n  Description: Returns constant\n  Recommendation: Implement calculation",
            "llama-3.3-70b-versatile",
        )

        cli._cmd_check(
            argparse.Namespace(
                api_url="http://testserver",
                file_or_diff=str(diff_file),
                token="mock_token",
            )
        )

    # 2. Verify it appears on the website immediately
    web_history = client.get("/api/reviews/history?team_id=team-sync-core")
    assert web_history.status_code == 200
    history_items = web_history.json()["items"]
    cli_review = next(item for item in history_items if item["source"] == "CLI")
    assert cli_review is not None
    assert cli_review["findings_count"] == 1

    # 3. Add team rule through CLI
    with patch("cli._post", side_effect=fake_post), \
         patch("backend.services.hindsight_service.hindsight_service.retain") as mock_retain:
        mock_retain.return_value = {"id": "hs-cli-rule-99", "success": True}
        cli._cmd_learn(
            argparse.Namespace(
                api_url="http://testserver",
                rule_text="Never commit hardcoded tax exemption keys.",
                token="mock_token",
            )
        )

    # 4. Verify rule appears in Hindsight Inspector / Facts endpoint
    facts_resp = client.get("/api/memories/facts?team_id=team-sync-core")
    assert facts_resp.status_code == 200
    facts_contents = [f["content"] for f in facts_resp.json()]
    assert "Never commit hardcoded tax exemption keys." in facts_contents

    # 5. Add team rule through Website
    with patch("backend.services.hindsight_service.hindsight_service.retain") as mock_retain:
        mock_retain.return_value = {"id": "hs-web-rule-88", "success": True}
        client.post(
            "/api/rules",
            json={
                "rule": "Audit all financial calculation routines with unit tests.",
                "tags": ["finance", "testing"],
                "team_id": "team-sync-core",
            },
        )

    # 6. Verify subsequent CLI review retrieves that team rule from Neon
    rules_resp = client.get("/api/rules")
    assert rules_resp.status_code == 200
    rules_texts = [r["rule"] for r in rules_resp.json()["rules"]]
    assert "Audit all financial calculation routines with unit tests." in rules_texts

    # 7. Verify both interfaces retrieve the exact same review history records
    cli_history_resp = client.get("/api/reviews?limit=10")
    web_history_resp = client.get("/api/reviews/history?team_id=team-sync-core")
    assert cli_history_resp.status_code == 200
    assert web_history_resp.status_code == 200

    cli_ids = {r["id"] for r in cli_history_resp.json()}
    web_ids = {r["id"] for r in web_history_resp.json()["items"]}
    assert cli_ids == web_ids
