"""Unit and integration tests for Phase 11: Review History and Team Settings."""
from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.security import AuthenticatedContext, get_current_user, get_current_user_optional
from backend.database import Base, get_db
from backend.main import app
from backend.models import HindsightBank, Review, ReviewFinding, ReviewMemory, Team, TeamMember, TeamRule, User

MOCK_OWNER_CTX = AuthenticatedContext(
    user_id="user-owner-01",
    email="owner@company.com",
    name="Team Owner",
    token_type="pat",
    team_roles={"team-core": "owner"},
)

MOCK_ADMIN_CTX = AuthenticatedContext(
    user_id="user-admin-01",
    email="admin@company.com",
    name="Team Admin",
    token_type="pat",
    team_roles={"team-core": "admin"},
)

MOCK_MEMBER_CTX = AuthenticatedContext(
    user_id="user-member-01",
    email="member@company.com",
    name="Team Member",
    token_type="pat",
    team_roles={"team-core": "member"},
)

MOCK_OUTSIDER_CTX = AuthenticatedContext(
    user_id="user-outsider-01",
    email="outsider@other.com",
    name="Outsider User",
    token_type="pat",
    team_roles={"team-other": "owner"},
)

current_mock_user = MOCK_OWNER_CTX


@pytest.fixture
def test_client_phase11():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    seeded = False

    async def override_get_db():
        nonlocal seeded
        if not seeded:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with factory() as session:
                # Seed Teams
                team_core = Team(id="team-core", name="Engineering Core")
                team_other = Team(id="team-other", name="Other Org")
                session.add_all([team_core, team_other])

                # Seed Users
                u_owner = User(id="user-owner-01", email="owner@company.com", name="Team Owner")
                u_admin = User(id="user-admin-01", email="admin@company.com", name="Team Admin")
                u_member = User(id="user-member-01", email="member@company.com", name="Team Member")
                u_outsider = User(id="user-outsider-01", email="outsider@other.com", name="Outsider User")
                session.add_all([u_owner, u_admin, u_member, u_outsider])

                # Seed Team Memberships
                tm1 = TeamMember(id="tm-1", team_id="team-core", user_id="user-owner-01", role="owner")
                tm2 = TeamMember(id="tm-2", team_id="team-core", user_id="user-admin-01", role="admin")
                tm3 = TeamMember(id="tm-3", team_id="team-core", user_id="user-member-01", role="member")
                tm4 = TeamMember(id="tm-4", team_id="team-other", user_id="user-outsider-01", role="owner")
                session.add_all([tm1, tm2, tm3, tm4])

                # Seed Bank for team-core
                bank = HindsightBank(
                    id="bank-core-01",
                    team_id="team-core",
                    bank_id="bank-eng-core",
                    bank_type="team",
                    is_active=True,
                )
                session.add(bank)

                # Seed Team Rules
                r1 = TeamRule(
                    id="rule-core-01",
                    team_id="team-core",
                    created_by="user-owner-01",
                    rule_text="Always validate input schemas before database persistence.",
                    hindsight_memory_id="hs-mem-rule-1",
                )
                session.add(r1)

                # Seed Reviews for team-core
                rev1 = Review(
                    id="rev-01",
                    user_id="user-owner-01",
                    team_id="team-core",
                    repository="acme/web-service",
                    commit_sha="a1b2c3d4",
                    pr_number=42,
                    file_path="src/auth.py",
                    code_diff="diff --git a/src/auth.py b/src/auth.py",
                    review_result="Looks mostly good, found critical SQL issue.",
                    model_used="groq/llama-3.3-70b-versatile",
                    status="completed",
                    source="Web",
                )
                rev2 = Review(
                    id="rev-02",
                    user_id="user-member-01",
                    team_id="team-core",
                    repository="acme/payment-api",
                    commit_sha="e5f6a7b8",
                    file_path="routes/checkout.py",
                    code_diff="diff --git a/routes/checkout.py b/routes/checkout.py",
                    review_result="Clean code, minor style comments.",
                    model_used="groq/llama-3.3-70b-versatile",
                    status="completed",
                    source="CLI",
                )
                rev_other = Review(
                    id="rev-other-01",
                    user_id="user-outsider-01",
                    team_id="team-other",
                    repository="secret/org-repo",
                    code_diff="diff --git a/secret.py",
                    review_result="Secret code review",
                    model_used="groq/llama-3.3-70b-versatile",
                    status="completed",
                    source="CLI",
                )
                session.add_all([rev1, rev2, rev_other])

                # Seed Findings for rev1
                f1 = ReviewFinding(
                    id="finding-01",
                    review_id="rev-01",
                    title="SQL Injection Vulnerability",
                    description="Unsanitized user input formatted directly into query.",
                    severity="critical",
                    file_path="src/auth.py",
                    line_number=42,
                    recommendation="Use parameterized queries.",
                )
                f2 = ReviewFinding(
                    id="finding-02",
                    review_id="rev-01",
                    title="Missing Rate Limiting",
                    description="Endpoint allows unbounded attempts.",
                    severity="medium",
                    file_path="src/auth.py",
                    line_number=88,
                )
                session.add_all([f1, f2])

                # Seed Memory for rev1
                mem1 = ReviewMemory(
                    id="mem-rev-01",
                    review_id="rev-01",
                    memory_text="Always validate input schemas before database persistence.",
                    hindsight_memory_id="hs-mem-rule-1",
                    relevance_metadata={"source": "team_rule", "bank_id": "bank-eng-core"},
                )
                session.add(mem1)

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
    app.dependency_overrides[get_current_user] = lambda: current_mock_user
    app.dependency_overrides[get_current_user_optional] = lambda: current_mock_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# =============================================================================
# 1. Review History Tests
# =============================================================================

def test_review_history_pagination_and_counts(test_client_phase11: TestClient):
    global current_mock_user
    current_mock_user = MOCK_OWNER_CTX

    resp = test_client_phase11.get("/api/reviews/history?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total_pages"] == 1
    assert "acme/web-service" in data["unique_repositories"]
    assert "acme/payment-api" in data["unique_repositories"]

    # Verify severity counts for rev-01
    rev1 = next(item for item in data["items"] if item["id"] == "rev-01")
    assert rev1["findings_count"] == 2
    assert rev1["severity_counts"]["critical"] == 1
    assert rev1["severity_counts"]["medium"] == 1
    assert rev1["severity_counts"]["high"] == 0
    assert rev1["memories_count"] == 1
    assert rev1["source"] == "Web"
    assert rev1["repository"] == "acme/web-service"
    assert rev1["pr_number"] == 42


def test_review_history_search_filter(test_client_phase11: TestClient):
    global current_mock_user
    current_mock_user = MOCK_OWNER_CTX

    # Search by repository substring
    resp = test_client_phase11.get("/api/reviews/history?search=payment")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "rev-02"

    # Search by PR number
    resp_pr = test_client_phase11.get("/api/reviews/history?search=42")
    assert resp_pr.status_code == 200
    assert resp_pr.json()["total"] == 1
    assert resp_pr.json()["items"][0]["id"] == "rev-01"


def test_review_history_source_and_severity_filters(test_client_phase11: TestClient):
    global current_mock_user
    current_mock_user = MOCK_OWNER_CTX

    # Filter by source: CLI
    resp_cli = test_client_phase11.get("/api/reviews/history?source=CLI")
    assert resp_cli.status_code == 200
    assert resp_cli.json()["total"] == 1
    assert resp_cli.json()["items"][0]["source"] == "CLI"

    # Filter by severity: critical
    resp_sev = test_client_phase11.get("/api/reviews/history?severity=critical")
    assert resp_sev.status_code == 200
    assert resp_sev.json()["total"] == 1
    assert resp_sev.json()["items"][0]["id"] == "rev-01"


def test_review_history_tenant_isolation(test_client_phase11: TestClient):
    global current_mock_user
    current_mock_user = MOCK_OUTSIDER_CTX

    resp = test_client_phase11.get("/api/reviews/history")
    assert resp.status_code == 200
    data = resp.json()

    # Outsider sees only rev-other-01, none of team-core's reviews
    assert data["total"] == 1
    assert data["items"][0]["id"] == "rev-other-01"
    assert "acme/web-service" not in data["unique_repositories"]


def test_get_full_review_with_findings_and_memories(test_client_phase11: TestClient):
    global current_mock_user
    current_mock_user = MOCK_OWNER_CTX

    resp = test_client_phase11.get("/api/reviews/rev-01")
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"] == "rev-01"
    assert data["repository"] == "acme/web-service"
    assert data["pr_number"] == 42
    assert len(data["findings"]) == 2
    assert len(data["memories"]) == 1
    assert data["findings"][0]["severity"] == "critical"
    assert data["memories"][0]["hindsight_memory_id"] == "hs-mem-rule-1"


# =============================================================================
# 2. Team Settings Tests
# =============================================================================

def test_list_user_teams(test_client_phase11: TestClient):
    global current_mock_user
    current_mock_user = MOCK_OWNER_CTX

    resp = test_client_phase11.get("/api/teams")
    assert resp.status_code == 200
    teams = resp.json()
    assert len(teams) >= 1
    core_team = next(t for t in teams if t["id"] == "team-core")
    assert core_team["name"] == "Engineering Core"
    assert core_team["role"] == "owner"
    assert core_team["member_count"] == 3


def test_get_team_settings(test_client_phase11: TestClient):
    global current_mock_user
    current_mock_user = MOCK_OWNER_CTX

    resp = test_client_phase11.get("/api/teams/team-core/settings")
    assert resp.status_code == 200
    data = resp.json()

    assert data["team_id"] == "team-core"
    assert data["team_name"] == "Engineering Core"
    assert data["current_user_role"] == "owner"
    assert data["can_manage"] is True
    assert len(data["members"]) == 3
    assert len(data["rules"]) == 1
    assert data["active_hindsight_bank"]["bank_id"] == "bank-eng-core"
    assert data["ai_model_config"]["provider"] == "Groq"
    assert "login" in data["cli_instructions"]


def test_get_team_settings_cross_team_denied(test_client_phase11: TestClient):
    global current_mock_user
    current_mock_user = MOCK_OUTSIDER_CTX

    # Outsider trying to access team-core
    resp = test_client_phase11.get("/api/teams/team-core/settings")
    assert resp.status_code == 403


# =============================================================================
# 3. RBAC Enforcement Tests (Admin/Owner vs Member)
# =============================================================================

def test_invite_member_authorized_and_unauthorized(test_client_phase11: TestClient):
    global current_mock_user

    # Owner can invite
    current_mock_user = MOCK_OWNER_CTX
    resp_ok = test_client_phase11.post(
        "/api/teams/team-core/members/invite",
        json={"email": "newhire@company.com", "role": "member"},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["email"] == "newhire@company.com"

    # Member is blocked by FastAPI RBAC
    current_mock_user = MOCK_MEMBER_CTX
    resp_denied = test_client_phase11.post(
        "/api/teams/team-core/members/invite",
        json={"email": "hacker@evil.com", "role": "admin"},
    )
    assert resp_denied.status_code == 403
    assert "requires one of" in resp_denied.json()["detail"].lower()


def test_update_member_role_rbac(test_client_phase11: TestClient):
    global current_mock_user

    # Admin cannot promote anyone to owner
    current_mock_user = MOCK_ADMIN_CTX
    resp_forbidden = test_client_phase11.put(
        "/api/teams/team-core/members/user-member-01/role",
        json={"role": "owner"},
    )
    assert resp_forbidden.status_code == 403

    # Owner can promote member to admin
    current_mock_user = MOCK_OWNER_CTX
    resp_ok = test_client_phase11.put(
        "/api/teams/team-core/members/user-member-01/role",
        json={"role": "admin"},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["role"] == "admin"

    # Member cannot change any role
    current_mock_user = MOCK_MEMBER_CTX
    resp_denied = test_client_phase11.put(
        "/api/teams/team-core/members/user-admin-01/role",
        json={"role": "member"},
    )
    assert resp_denied.status_code == 403


def test_cannot_remove_team_owner(test_client_phase11: TestClient):
    global current_mock_user
    current_mock_user = MOCK_OWNER_CTX

    resp = test_client_phase11.delete("/api/teams/team-core/members/user-owner-01")
    assert resp.status_code == 400
    assert "cannot remove team owner" in resp.json()["detail"].lower()


def test_delete_team_rule_rbac(test_client_phase11: TestClient):
    global current_mock_user

    # Member cannot delete rule
    current_mock_user = MOCK_MEMBER_CTX
    resp_denied = test_client_phase11.delete("/api/teams/team-core/rules/rule-core-01")
    assert resp_denied.status_code == 403

    # Admin/Owner can delete rule
    current_mock_user = MOCK_OWNER_CTX
    resp_ok = test_client_phase11.delete("/api/teams/team-core/rules/rule-core-01")
    assert resp_ok.status_code == 200
    assert resp_ok.json()["status"] == "deleted"


def test_update_team_settings_rbac(test_client_phase11: TestClient):
    global current_mock_user

    # Member cannot update settings
    current_mock_user = MOCK_MEMBER_CTX
    resp_denied = test_client_phase11.put(
        "/api/teams/team-core/settings",
        json={"name": "Hacked Name"},
    )
    assert resp_denied.status_code == 403

    # Owner can update team settings
    current_mock_user = MOCK_OWNER_CTX
    resp_ok = test_client_phase11.put(
        "/api/teams/team-core/settings",
        json={"name": "Engineering Production Team", "hindsight_bank_id": "bank-prod-01"},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["name"] == "Engineering Production Team"
