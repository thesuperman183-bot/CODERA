"""End-to-end verification script for the complete Code Review pipeline with live Neon PostgreSQL."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.database import get_session_factory
from backend.main import app
from backend.models import RetainedFact, Review, ReviewFinding, ReviewMemory, TeamRule


async def run_pipeline_test():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        print("=== Step 0: CLI Login to obtain live PAT ===")
        login_resp = await client.post(
            "/api/auth/cli-login",
            json={"email": "pipeline-tester@example.com"},
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        print("Obtained PAT successfully.")

        print("\n=== Step 1: Testing /api/retain pipeline ===")
        import uuid
        test_rule = f"All SQL queries must be parameterized to prevent SQL injection vulnerabilities ({uuid.uuid4().hex[:6]})"

        # Mock external Hindsight HTTP request to avoid external network dependencies while testing Neon persistence
        with patch("backend.services.review_service.hindsight_service._post") as mock_hindsight:
            mock_hindsight.return_value = {
                "success": True,
                "id": "hsk_mem_sql_001",
            }

            retain_resp = await client.post(
                "/api/retain",
                json={
                    "rule": test_rule,
                    "tags": ["security", "database", "owasp"],
                },
                headers=auth_headers,
            )
            assert retain_resp.status_code == 200, f"Retain failed: {retain_resp.text}"
            retain_data = retain_resp.json()
            print("Retain Response:", retain_data)
            assert retain_data["status"] == "retained"
            assert retain_data["memory_id"] == "hsk_mem_sql_001"
            assert retain_data.get("rule_id") is not None

            # Step 1b: Test deduplication / retry idempotency
            print("\n=== Step 1b: Testing Retain Retry & Deduplication ===")
            retry_resp = await client.post(
                "/api/retain",
                json={
                    "rule": test_rule,
                    "tags": ["security", "database", "owasp"],
                },
                headers=auth_headers,
            )
            assert retry_resp.status_code == 200, f"Retry retain failed: {retry_resp.text}"
            retry_data = retry_resp.json()
            assert retry_data["rule_id"] == retain_data["rule_id"], (
                f"Deduplication failed: got {retry_data['rule_id']} instead of {retain_data['rule_id']}"
            )
            print("Deduplication verified: re-used existing rule ID", retry_data["rule_id"])

        print("\n=== Step 2: Testing /api/review pipeline with code diff ===")
        sample_diff = """--- a/user_repository.py
+++ b/user_repository.py
@@ -10,2 +10,2 @@
-def get_user(db, user_id):
-    return db.query("SELECT * FROM users WHERE id = :id", {"id": user_id})
+def get_user(db, user_id):
+    return db.query(f"SELECT * FROM users WHERE id = '{user_id}'")
"""

        with patch("backend.services.review_service.hindsight_service._post") as mock_recall, \
             patch("backend.services.review_service.groq_service._get_client") as mock_groq_client:

            # Mock Hindsight recall response
            mock_recall.return_value = {
                "results": [
                    {"text": "All SQL queries must be parameterized to prevent SQL injection vulnerabilities"}
                ]
            }

            # Mock Groq review completion response
            mock_http = MagicMock()
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "## Code Review Summary\n\n"
                                "- [CRITICAL] SQL Injection Vulnerability in user_repository.py:11\n"
                                "  Description: Direct string interpolation into raw SQL query allows arbitrary SQL execution.\n"
                                "  Recommendation: Use parameterized queries: db.query(\"SELECT * FROM users WHERE id = :id\", {\"id\": user_id})\n\n"
                                "- [INFO] Function Documentation\n"
                                "  Description: Missing docstring describing function parameters and return type.\n"
                                "  Recommendation: Add Python docstring."
                            )
                        }
                    }
                ]
            }
            mock_http.post.return_value = mock_res
            mock_groq_client.return_value = mock_http

            review_resp = await client.post(
                "/api/review",
                json={
                    "code_diff": sample_diff,
                    "source": "CLI",
                },
                headers=auth_headers,
            )
            assert review_resp.status_code == 200, f"Review failed: {review_resp.text}"
            review_data = review_resp.json()

            print("Review ID:", review_data.get("review_id"))
            print("Model Used:", review_data.get("model_used"))
            print("Memories Used Count:", len(review_data.get("memories_used", [])))
            print("Findings Extracted:", len(review_data.get("findings", [])))
            for idx, finding in enumerate(review_data.get("findings", []), 1):
                print(f"  {idx}. [{finding['severity'].upper()}] {finding['title']}")
                if finding.get("recommendation"):
                    print(f"     Fix: {finding['recommendation']}")

            assert review_data.get("review_id") is not None
            assert len(review_data["findings"]) >= 1
            assert any(f["severity"].lower() == "critical" for f in review_data["findings"])

            # Step 3: Verify permanent persistence in Neon PostgreSQL
            print("\n=== Step 3: Verifying Permanent Records in Neon PostgreSQL ===")
            review_id = review_data["review_id"]

            session_factory = get_session_factory()
            async with session_factory() as session:
                stmt = (
                    select(Review)
                    .where(Review.id == review_id)
                    .options(
                        selectinload(Review.findings),
                        selectinload(Review.memories),
                    )
                )
                db_review = (await session.execute(stmt)).scalar_one_or_none()
                assert db_review is not None, f"Review {review_id} not found in Neon PostgreSQL"
                print(f"Neon Record Found: Review ID = {db_review.id}")
                print(f"Status: {db_review.status}, CreatedAt: {db_review.created_at}")
                print(f"Findings in Neon: {len(db_review.findings)}")
                for f in db_review.findings:
                    print(f"  - DB Finding: [{f.severity.upper()}] {f.title} (line {f.line_number})")
                print(f"Memories Linked in Neon: {len(db_review.memories)}")
                for m in db_review.memories:
                    print(f"  - DB Memory Link: {m.memory_text[:60]}... (Source: {m.relevance_metadata.get('source')})")

                # Verify rule in team_rules
                rule_stmt = select(TeamRule).where(TeamRule.rule_text == test_rule)
                db_rule = (await session.execute(rule_stmt)).scalars().all()
                assert len(db_rule) == 1, f"Expected exactly 1 rule in Neon, found {len(db_rule)} (deduplication check)"
                print(f"Deduplicated Rule Record Confirmed in Neon: ID={db_rule[0].id}")

        print("\nSUCCESS: Complete Code Review pipeline verified end-to-end with Neon PostgreSQL!")


if __name__ == "__main__":
    asyncio.run(run_pipeline_test())
