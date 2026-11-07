"""Unit tests for SQLAlchemy models and database relationships."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.database import Base
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


@pytest.fixture
async def async_db_session():
    """Create isolated in-memory SQLite database session for model testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.anyio
async def test_user_team_membership(async_db_session: AsyncSession):
    user = User(email="bob@example.com", name="Bob")
    team = Team(name="Engineering")
    async_db_session.add_all([user, team])
    await async_db_session.flush()

    membership = TeamMember(user_id=user.id, team_id=team.id, role="admin")
    async_db_session.add(membership)
    await async_db_session.commit()

    # Query with relationship loading
    stmt = select(User).where(User.id == user.id).options(selectinload(User.team_memberships))
    res = await async_db_session.execute(stmt)
    u = res.scalar_one()

    assert u.email == "bob@example.com"
    assert len(u.team_memberships) == 1
    assert u.team_memberships[0].role == "admin"


@pytest.mark.anyio
async def test_review_and_findings_cascade(async_db_session: AsyncSession):
    review = Review(
        code_diff="+ print('test')",
        review_result="Looks good",
        model_used="qwen-2.5-32b",
        source="CLI",
    )
    async_db_session.add(review)
    await async_db_session.flush()

    finding = ReviewFinding(
        review_id=review.id,
        title="Debug print",
        description="Remove debug print statement",
        severity="low",
    )
    memory = ReviewMemory(
        review_id=review.id,
        memory_text="Never ship debug statements",
        relevance_metadata={"relevance": 0.9},
    )
    async_db_session.add_all([finding, memory])
    await async_db_session.commit()

    stmt = (
        select(Review)
        .where(Review.id == review.id)
        .options(selectinload(Review.findings), selectinload(Review.memories))
    )
    res = await async_db_session.execute(stmt)
    r = res.scalar_one()

    assert len(r.findings) == 1
    assert r.findings[0].severity == "low"
    assert len(r.memories) == 1
    assert r.memories[0].relevance_metadata["relevance"] == 0.9


@pytest.mark.anyio
async def test_team_rules_and_banks(async_db_session: AsyncSession):
    team = Team(name="Platform")
    async_db_session.add(team)
    await async_db_session.flush()

    rule = TeamRule(team_id=team.id, rule_text="Use async functions for I/O")
    bank = HindsightBank(team_id=team.id, bank_id="platform_bank", bank_type="team")
    fact = RetainedFact(team_id=team.id, content="Platform team uses FastAPI", tags=["platform"])
    async_db_session.add_all([rule, bank, fact])
    await async_db_session.commit()

    stmt = select(Team).where(Team.id == team.id).options(
        selectinload(Team.rules),
        selectinload(Team.hindsight_banks),
        selectinload(Team.retained_facts),
    )
    res = await async_db_session.execute(stmt)
    t = res.scalar_one()

    assert len(t.rules) == 1
    assert t.rules[0].rule_text == "Use async functions for I/O"
    assert len(t.hindsight_banks) == 1
    assert t.hindsight_banks[0].bank_id == "platform_bank"
    assert len(t.retained_facts) == 1
    assert t.retained_facts[0].tags == ["platform"]

