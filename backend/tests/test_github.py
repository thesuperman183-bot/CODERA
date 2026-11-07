"""Unit and integration tests for GitHub and Pull Request Intelligence routers."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.security import AuthenticatedContext, get_current_user, get_current_user_optional
from backend.database import Base, get_db
from backend.main import app
from backend.models import User, UserGitHubAccount
from backend.services.pr_analysis_service import detect_pr_languages, detect_test_coverage_presence, pr_analysis_service

MOCK_USER_CTX = AuthenticatedContext(
    user_id="github-test-user-id",
    email="github-user@example.com",
    name="GitHub Tester",
    token_type="pat",
    team_roles={"team-gh": "owner"},
)


@pytest.fixture
def github_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async def override_get_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as session:
            # Seed test user and github account
            user = User(id="github-test-user-id", email="github-user@example.com", name="GitHub Tester")
            gh_acc = UserGitHubAccount(
                id="gh-acc-01",
                user_id="github-test-user-id",
                github_username="octocat",
                access_token_encrypted="ghp_mock_token_12345",
            )
            session.add(user)
            session.add(gh_acc)
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


def test_pr_intelligence_language_and_test_detection():
    files = [
        {"filename": "backend/auth.py"},
        {"filename": "tests/test_auth.py"},
        {"filename": "frontend/App.tsx"},
    ]
    languages = detect_pr_languages(files)
    assert "Python" in languages
    assert "TypeScript (React)" in languages
    assert detect_test_coverage_presence(files) is True

    files_no_tests = [{"filename": "src/utils.js"}]
    assert detect_test_coverage_presence(files_no_tests) is False


def test_pr_intelligence_ranking_with_reasons():
    prs = [
        {
            "number": 42,
            "title": "Fix SQL injection vulnerability in user queries",
            "body": "Replaces string format with parameterized queries",
            "state": "open",
            "user": {"login": "dev1"},
            "additions": 10,
            "deletions": 5,
        }
    ]
    files_by_pr = {
        42: [
            {"filename": "backend/db.py"},
            {"filename": "backend/tests/test_db.py"},
        ]
    }
    team_rules = ["Always parameterize SQL queries"]

    ranked = pr_analysis_service.analyze_and_rank_pull_requests(
        pull_requests=prs,
        files_by_pr=files_by_pr,
        team_rules=team_rules,
    )

    assert len(ranked) == 1
    top = ranked[0]
    assert top["number"] == 42
    assert top["recommendation_score"] >= 75
    assert top["recommendation_priority"] == "high"
    # Verify human-readable reasons exist
    reasons_text = " ".join(top["recommendation_reasons"]).lower()
    assert "security" in reasons_text
    assert "defect" in reasons_text or "bug" in reasons_text


def test_github_status_endpoint(github_client: TestClient):
    resp = github_client.get("/api/github/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["github_username"] == "octocat"


def test_github_repositories_list(github_client: TestClient):
    with patch("backend.services.github_service.github_service.list_repositories", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [
            {
                "id": 101,
                "name": "code_review_agent",
                "full_name": "octocat/code_review_agent",
                "owner": "octocat",
                "default_branch": "main",
                "private": False,
                "description": "Agent repo",
                "language": "Python",
                "updated_at": "2026-11-06T12:00:00Z",
                "html_url": "https://github.com/octocat/code_review_agent",
            }
        ]

        resp = github_client.get("/api/github/repositories")
        assert resp.status_code == 200
        repos = resp.json()
        assert len(repos) == 1
        assert repos[0]["full_name"] == "octocat/code_review_agent"


def test_github_branches_list(github_client: TestClient):
    with patch("backend.services.github_service.github_service.list_branches", new_callable=AsyncMock) as mock_branches:
        mock_branches.return_value = [
            {"name": "main", "commit_sha": "abc1234", "protected": True},
            {"name": "feature/auth", "commit_sha": "def5678", "protected": False},
        ]

        resp = github_client.get("/api/github/repositories/octocat/code_review_agent/branches")
        assert resp.status_code == 200
        branches = resp.json()
        assert len(branches) == 2
        assert branches[0]["name"] == "main"


def test_pull_requests_list_and_rank(github_client: TestClient):
    with patch("backend.services.github_service.github_service.list_pull_requests", new_callable=AsyncMock) as mock_prs, \
         patch("backend.services.github_service.github_service.get_pull_request_files", new_callable=AsyncMock) as mock_files:
        mock_prs.return_value = [
            {
                "number": 12,
                "title": "Hotfix: parameterize authentication queries",
                "body": "Fixes security issue",
                "state": "open",
                "user": {"login": "alice", "avatar_url": "https://example.com/avatar.png"},
                "additions": 15,
                "deletions": 5,
                "created_at": "2026-11-06T10:00:00Z",
                "updated_at": "2026-11-06T11:00:00Z",
            }
        ]
        mock_files.return_value = [{"filename": "backend/auth.py"}]

        resp = github_client.get("/api/pull-requests/octocat/code_review_agent")
        assert resp.status_code == 200
        prs = resp.json()
        assert len(prs) == 1
        assert prs[0]["number"] == 12
        assert len(prs[0]["recommendation_reasons"]) > 0


def test_pull_request_review_execution(github_client: TestClient):
    with patch("backend.services.github_service.github_service.get_pull_request_diff", new_callable=AsyncMock) as mock_diff, \
         patch("backend.services.github_service.github_service.get_pull_request", new_callable=AsyncMock) as mock_meta, \
         patch("backend.services.review_service.hindsight_service.recall") as mock_recall, \
         patch("backend.services.review_service.groq_service.generate_review") as mock_groq:
        mock_diff.return_value = "--- a/auth.py\n+++ b/auth.py\n@@ -1 +1 @@\n-old\n+new"
        mock_meta.return_value = {"head": {"sha": "c0ffee123"}}
        mock_recall.return_value = ["Always validate tokens"]
        mock_groq.return_value = ("PR Review: Looks well tested and clean.", "qwen-2.5-32b")

        resp = github_client.post(
            "/api/pull-requests/review",
            json={"owner": "octocat", "repo": "code_review_agent", "pr_number": 12},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review"] == "PR Review: Looks well tested and clean."
        assert data["repository"] == "octocat/code_review_agent"
        assert data["pr_number"] == 12
        assert data["commit_sha"] == "c0ffee123"
        assert data["review_id"] is not None

