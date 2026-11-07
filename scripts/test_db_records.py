"""Test script demonstrating Neon PostgreSQL connectivity, inserting and retrieving sample records."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.database import get_session_factory
from backend.models import (
    HindsightBank,
    RetainedFact,
    Review,
    ReviewFinding,
    ReviewMemory,
    Team,
    TeamMember,
    TeamRule,
    User,
)


async def demonstrate_database_operations():
    session_factory = get_session_factory()
    async with session_factory() as session:
        print("--- 1. Creating sample User and Team ---")
        unique_suffix = uuid.uuid4().hex[:8]
        user = User(
            email=f"developer_{unique_suffix}@example.com",
            name="Alice Developer",
        )
        team = Team(name=f"Core Backend Team {unique_suffix}")
        session.add_all([user, team])
        await session.flush()
        print(f"User created: ID={user.id}, Email={user.email}")
        print(f"Team created: ID={team.id}, Name={team.name}")

        print("\n--- 2. Creating Team Membership ---")
        member = TeamMember(
            user_id=user.id,
            team_id=team.id,
            role="owner",
        )
        session.add(member)
        await session.flush()
        print(f"TeamMember created: User {user.id} -> Team {team.id} (Role: {member.role})")

        print("\n--- 3. Creating Hindsight Memory Bank Configuration ---")
        bank = HindsightBank(
            team_id=team.id,
            user_id=user.id,
            bank_id=f"bank_{unique_suffix}",
            bank_type="team",
            is_active=True,
        )
        session.add(bank)

        print("\n--- 4. Creating Team Rule and Retained Fact ---")
        rule = TeamRule(
            team_id=team.id,
            created_by=user.id,
            rule_text="Always validate JSON schemas in API request payloads.",
            hindsight_memory_id=f"mem_rule_{unique_suffix}",
        )
        fact = RetainedFact(
            team_id=team.id,
            user_id=user.id,
            content="Team prefers asyncpg with pool_pre_ping enabled.",
            hindsight_memory_id=f"mem_fact_{unique_suffix}",
            tags=["database", "performance"],
        )
        session.add_all([rule, fact])

        print("\n--- 5. Creating Review with Findings and Memories ---")
        review = Review(
            user_id=user.id,
            team_id=team.id,
            source="CLI",
            code_diff="--- a/server.py\n+++ b/server.py\n@@ -10 +10 @@\n-password = '123'\n+password = getenv('SECRET')",
            review_result="Approved: Hardcoded credential replaced with environment variable.",
            model_used="qwen-2.5-32b",
            status="completed",
        )
        session.add(review)
        await session.flush()

        finding = ReviewFinding(
            review_id=review.id,
            title="Credential Exposure Resolved",
            description="Replaced plaintext hardcoded credential with os.getenv call.",
            severity="high",
            file_path="server.py",
            line_number=10,
            recommendation="Ensure the secret is populated in deployment CI/CD secrets.",
        )
        memory = ReviewMemory(
            review_id=review.id,
            hindsight_memory_id=f"mem_rule_{unique_suffix}",
            memory_text="Always store credentials in environment variables.",
            relevance_metadata={"score": 0.95, "bank": bank.bank_id},
        )
        session.add_all([finding, memory])

        # Commit transaction
        await session.commit()
        print(f"Review created with ID={review.id}")

        print("\n--- 6. Querying and Verifying Persisted Records ---")
        stmt = (
            select(Review)
            .where(Review.id == review.id)
            .options(
                selectinload(Review.user),
                selectinload(Review.team),
                selectinload(Review.findings),
                selectinload(Review.memories),
            )
        )
        result = await session.execute(stmt)
        retrieved_review = result.scalar_one()

        print(f"Retrieved Review ID: {retrieved_review.id}")
        print(f"Source: {retrieved_review.source}, Status: {retrieved_review.status}")
        print(f"Model: {retrieved_review.model_used}")
        print(f"Associated User: {retrieved_review.user.name} ({retrieved_review.user.email})")
        print(f"Associated Team: {retrieved_review.team.name}")
        print(f"Findings Count: {len(retrieved_review.findings)}")
        for f in retrieved_review.findings:
            print(f"  - [{f.severity.upper()}] {f.title}: {f.description} (File: {f.file_path}:{f.line_number})")
        print(f"Memories Used Count: {len(retrieved_review.memories)}")
        for m in retrieved_review.memories:
            print(f"  - {m.memory_text} (Score: {m.relevance_metadata.get('score')})")

        print("\n--- 7. Querying Team Rules ---")
        rules_stmt = select(TeamRule).where(TeamRule.team_id == team.id)
        rules_res = await session.execute(rules_stmt)
        rules_list = rules_res.scalars().all()
        print(f"Team Rules Count: {len(rules_list)}")
        for r in rules_list:
            print(f"  - Rule: {r.rule_text} (Created: {r.created_at.isoformat()})")

        print("\nSUCCESS: All sample records inserted and retrieved with full relational integrity!")


if __name__ == "__main__":
    asyncio.run(demonstrate_database_operations())

