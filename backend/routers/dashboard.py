"""Dashboard metrics router secured by authentication."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.config import settings
from backend.core.security import AuthenticatedContext, get_current_user
from backend.database import get_db
from backend.models import HindsightBank, RetainedFact, Review, ReviewFinding, TeamRule
from backend.schemas import DashboardStatsResponse
from backend.services.review_service import review_processor

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse, summary="Retrieve dashboard statistics scoped to user/team")
async def get_dashboard_stats(
    team_id: Optional[str] = Query(default=None, description="Optional team filter"),
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardStatsResponse:
    """Return aggregated real metrics from Neon scoped to the authenticated user's authorized teams."""
    hindsight_configured = bool(settings.hindsight_api_key)
    groq_configured = bool(settings.groq_api_key)

    # 1. Base team security filters
    if team_id:
        auth.require_team_access(team_id)
        effective_team_ids = {team_id}
    else:
        effective_team_ids = auth.team_ids

    # User review conditions: either review authored by user, or in one of authorized teams
    review_conditions = [Review.user_id == auth.user_id]
    if effective_team_ids:
        review_conditions.append(Review.team_id.in_(effective_team_ids))

    # Total Reviews
    reviews_count_stmt = select(func.count()).select_from(Review).where(or_(*review_conditions))
    total_reviews = (await db.execute(reviews_count_stmt)).scalar() or 0

    # Total Active Team Rules
    rule_conditions = []
    if effective_team_ids:
        rule_conditions.append(TeamRule.team_id.in_(effective_team_ids))
    else:
        rule_conditions.append(TeamRule.created_by == auth.user_id)
    rules_count_stmt = select(func.count()).select_from(TeamRule).where(or_(*rule_conditions))
    total_rules = (await db.execute(rules_count_stmt)).scalar() or 0

    # Retained Facts / Memories
    fact_conditions = []
    if effective_team_ids:
        fact_conditions.append(RetainedFact.team_id.in_(effective_team_ids))
    else:
        fact_conditions.append(RetainedFact.user_id == auth.user_id)
    facts_count_stmt = select(func.count()).select_from(RetainedFact).where(or_(*fact_conditions))
    retained_memories = (await db.execute(facts_count_stmt)).scalar() or 0

    # Total Available Memories = Retained Facts + Team Rules
    total_available_memories = retained_memories + total_rules

    # Subquery for authorized review IDs to aggregate findings
    auth_review_ids_stmt = select(Review.id).where(or_(*review_conditions))

    # Findings grouped by severity & Critical count
    findings_severity_stmt = (
        select(ReviewFinding.severity, func.count(ReviewFinding.id))
        .where(ReviewFinding.review_id.in_(auth_review_ids_stmt))
        .group_by(ReviewFinding.severity)
    )
    severity_rows = (await db.execute(findings_severity_stmt)).all()
    findings_by_severity = {row[0].lower(): row[1] for row in severity_rows}
    critical_issues = findings_by_severity.get("critical", 0)

    # Resolve active Hindsight Bank ID
    hindsight_bank_id = settings.hindsight_bank_id or "default"
    if effective_team_ids:
        bank_stmt = select(HindsightBank.bank_id).where(
            and_(
                HindsightBank.team_id.in_(effective_team_ids),
                HindsightBank.is_active == True,  # noqa: E712
            )
        )
        active_bank = (await db.execute(bank_stmt)).scalars().first()
        if active_bank:
            hindsight_bank_id = active_bank

    # Recent Retained Facts
    recent_facts_stmt = (
        select(RetainedFact)
        .where(or_(*fact_conditions))
        .order_by(RetainedFact.created_at.desc())
        .limit(5)
    )
    recent_facts = (await db.execute(recent_facts_stmt)).scalars().all()
    recent_retained_facts = [
        {
            "id": f.id,
            "content": f.content,
            "hindsight_memory_id": f.hindsight_memory_id,
            "tags": f.tags,
            "created_at": f.created_at.isoformat(),
        }
        for f in recent_facts
    ]

    # Recent Reviews with Findings count
    recent_reviews_stmt = (
        select(Review)
        .options(selectinload(Review.findings))
        .where(or_(*review_conditions))
        .order_by(Review.created_at.desc())
        .limit(6)
    )
    reviews_res = (await db.execute(recent_reviews_stmt)).scalars().all()
    recent_reviews = [
        {
            "id": r.id,
            "source": r.source,
            "status": r.status,
            "model_used": r.model_used,
            "created_at": r.created_at.isoformat(),
            "findings_count": len(r.findings),
            "critical_count": sum(1 for f in r.findings if f.severity.lower() == "critical"),
        }
        for r in reviews_res
    ]

    # Activity Timeline (Reviews grouped by day)
    timeline_stmt = (
        select(
            func.date(Review.created_at).label("day"),
            func.count(Review.id).label("reviews"),
        )
        .where(or_(*review_conditions))
        .group_by(func.date(Review.created_at))
        .order_by(func.date(Review.created_at).desc())
        .limit(7)
    )
    timeline_rows = (await db.execute(timeline_stmt)).all()
    activity_timeline = [
        {"day": str(row[0]), "reviews": row[1]}
        for row in reversed(timeline_rows)
    ]

    # Issues detected across projects (file_path based breakdown)
    file_issues_stmt = (
        select(
            ReviewFinding.file_path,
            func.count(ReviewFinding.id).label("count"),
            func.sum(
                case((ReviewFinding.severity == "critical", 1), else_=0)
            ).label("criticals"),
        )
        .where(
            and_(
                ReviewFinding.review_id.in_(auth_review_ids_stmt),
                ReviewFinding.file_path.isnot(None),
            )
        )
        .group_by(ReviewFinding.file_path)
        .order_by(func.count(ReviewFinding.id).desc())
        .limit(6)
    )
    project_issues_rows = (await db.execute(file_issues_stmt)).all()
    project_issues = [
        {
            "project_or_file": row[0] or "General",
            "issues": row[1],
            "criticals": row[2] or 0,
        }
        for row in project_issues_rows
    ]

    system_status = "healthy" if (hindsight_configured and groq_configured) else "degraded"

    return DashboardStatsResponse(
        total_reviews=total_reviews,
        total_rules=total_rules,
        critical_issues=critical_issues,
        retained_memories=retained_memories,
        system_status=system_status,
        groq_model=settings.groq_model,
        hindsight_configured=hindsight_configured,
        hindsight_bank_id=hindsight_bank_id,
        total_available_memories=total_available_memories,
        recent_retained_facts=recent_retained_facts,
        recent_reviews=recent_reviews,
        findings_by_severity=findings_by_severity,
        activity_timeline=activity_timeline,
        project_issues=project_issues,
    )
