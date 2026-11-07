"""Router for code review endpoints with strict multi-tenant authorization."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.exceptions import AppException, ResourceNotFoundError
from backend.core.security import AuthenticatedContext, get_current_user, get_current_user_optional
from backend.database import get_db
from backend.models import Review, ReviewFinding
from backend.schemas import (
    ReviewHistoryItem,
    ReviewHistoryResponse,
    ReviewRequest,
    ReviewResponse,
    ReviewSeverityCounts,
)
from backend.services.review_service import review_processor

router = APIRouter(tags=["Reviews"])


@router.post(
    "/api/review",
    response_model=ReviewResponse,
    summary="Generate code review and persist in Neon with caller authorization",
)
async def review_compat(
    request: ReviewRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Submit code diff for review with verified user identity and team tenancy checks."""
    try:
        # Enforce server-side user identity (never trust client-supplied user_id)
        request.user_id = auth.user_id

        # Verify team authorization if team_id was specified
        if request.team_id:
            auth.require_team_access(request.team_id)
        elif auth.team_ids:
            # Default to user's first team
            request.team_id = next(iter(auth.team_ids))

        return await review_processor.process_review(request, session=db)
    except AppException:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review processing error: {exc}",
        ) from exc


@router.post(
    "/api/reviews",
    response_model=ReviewResponse,
    summary="RESTful code review submission",
)
async def create_review(
    request: ReviewRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """REST review endpoint enforcing authenticated caller and team boundaries."""
    request.user_id = auth.user_id
    if request.team_id:
        auth.require_team_access(request.team_id)
    elif auth.team_ids:
        request.team_id = next(iter(auth.team_ids))
    return await review_processor.process_review(request, session=db)


def _compute_severity_counts(findings: list) -> ReviewSeverityCounts:
    """Helper to compute critical, high, medium, low breakdown."""
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        sev = (getattr(f, "severity", None) or "medium").lower()
        if sev in counts:
            counts[sev] += 1
        else:
            counts["medium"] += 1
    return ReviewSeverityCounts(**counts)


@router.get(
    "/api/reviews/history",
    response_model=ReviewHistoryResponse,
    summary="Paginated, searchable, and filtered review history scoped to caller",
)
async def get_review_history(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(default=None, description="Search repository, commit SHA, PR number, or review ID"),
    source: Optional[str] = Query(default=None, description="Filter by CLI or Web source"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by review status"),
    severity: Optional[str] = Query(default=None, description="Filter reviews containing findings of specific severity"),
    repository: Optional[str] = Query(default=None, description="Filter by repository name"),
    team_id: Optional[str] = Query(default=None, description="Filter by team"),
    sort_by: str = Query(default="created_at", description="Sort field: created_at or findings_count"),
    sort_order: str = Query(default="desc", description="Sort order: desc or asc"),
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewHistoryResponse:
    """Return paginated review history from Neon with search, filters, sorting, and severity counts."""
    # 1. Base access scoping
    if team_id:
        auth.require_team_access(team_id)
        access_condition = Review.team_id == team_id
    else:
        tenant_conditions = [Review.user_id == auth.user_id]
        if auth.team_ids:
            tenant_conditions.append(Review.team_id.in_(auth.team_ids))
        access_condition = or_(*tenant_conditions)

    # 2. Filter conditions
    filters = [access_condition]

    if search and search.strip():
        term = f"%{search.strip()}%"
        search_clauses = [
            Review.id.ilike(term),
            Review.repository.ilike(term),
            Review.commit_sha.ilike(term),
            Review.file_path.ilike(term),
        ]
        if search.strip().isdigit():
            search_clauses.append(Review.pr_number == int(search.strip()))
        filters.append(or_(*search_clauses))

    if source and source.strip():
        filters.append(Review.source == source.strip())

    if status_filter and status_filter.strip():
        filters.append(Review.status == status_filter.strip())

    if repository and repository.strip():
        filters.append(Review.repository == repository.strip())

    if severity and severity.strip():
        # Subquery filter to reviews that contain a finding matching the severity
        filters.append(
            Review.findings.any(ReviewFinding.severity == severity.strip().lower())
        )

    # 3. Query total count
    count_stmt = select(func.count(distinct(Review.id))).where(and_(*filters))
    total_count = (await db.execute(count_stmt)).scalar() or 0

    # 4. Query unique repositories for the filter dropdown
    repo_stmt = (
        select(Review.repository)
        .distinct()
        .where(and_(access_condition, Review.repository.is_not(None)))
        .order_by(Review.repository.asc())
    )
    unique_repos_raw = (await db.execute(repo_stmt)).scalars().all()
    unique_repositories = [r for r in unique_repos_raw if r]

    # 5. Order clause
    if sort_by == "findings_count":
        # Group by findings count
        subq = (
            select(Review.id, func.count(ReviewFinding.id).label("f_count"))
            .outerjoin(ReviewFinding, Review.id == ReviewFinding.review_id)
            .group_by(Review.id)
            .subquery()
        )
        if sort_order == "asc":
            order_clause = subq.c.f_count.asc()
        else:
            order_clause = subq.c.f_count.desc()
        query_stmt = (
            select(Review)
            .join(subq, Review.id == subq.c.id)
            .options(selectinload(Review.findings), selectinload(Review.memories))
            .where(and_(*filters))
            .order_by(order_clause, Review.created_at.desc())
        )
    else:
        if sort_order == "asc":
            order_clause = Review.created_at.asc()
        else:
            order_clause = Review.created_at.desc()
        query_stmt = (
            select(Review)
            .options(selectinload(Review.findings), selectinload(Review.memories))
            .where(and_(*filters))
            .order_by(order_clause)
        )

    offset = (page - 1) * page_size
    query_stmt = query_stmt.offset(offset).limit(page_size)
    reviews = (await db.execute(query_stmt)).scalars().all()

    items = [
        ReviewHistoryItem(
            id=r.id,
            repository=r.repository,
            commit_sha=r.commit_sha,
            pr_number=r.pr_number,
            file_path=r.file_path,
            created_at=r.created_at.isoformat(),
            source=r.source,
            status=r.status,
            model_used=r.model_used,
            findings_count=len(r.findings),
            severity_counts=_compute_severity_counts(r.findings),
            memories_count=len(r.memories),
        )
        for r in reviews
    ]

    total_pages = max(1, math.ceil(total_count / page_size)) if total_count > 0 else 1

    return ReviewHistoryResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        unique_repositories=unique_repositories,
    )


@router.get(
    "/api/reviews",
    response_model=List[Dict[str, Any]],
    summary="List review sessions authorized for current user/teams",
)
async def list_reviews(
    limit: int = 50,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return historical code reviews restricted to the user's personal reviews or team reviews."""
    conditions = [Review.user_id == auth.user_id]
    if auth.team_ids:
        conditions.append(Review.team_id.in_(auth.team_ids))

    stmt = (
        select(Review)
        .options(selectinload(Review.findings), selectinload(Review.memories))
        .where(or_(*conditions))
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    reviews = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "code_diff": r.code_diff,
            "review": r.review_result,
            "model_used": r.model_used,
            "source": r.source,
            "status": r.status,
            "user_id": r.user_id,
            "team_id": r.team_id,
            "created_at": r.created_at.isoformat(),
            "findings_count": len(r.findings),
            "severity_counts": _compute_severity_counts(r.findings).model_dump(),
            "memories_count": len(r.memories),
            "repository": r.repository,
            "commit_sha": r.commit_sha,
            "pr_number": r.pr_number,
            "file_path": r.file_path,
        }
        for r in reviews
    ]


@router.get(
    "/api/reviews/{review_id}",
    response_model=Dict[str, Any],
    summary="Get review session by ID with cross-tenant authorization guard",
)
async def get_review(
    review_id: str,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve review details with verification that caller owns the review or belongs to the team."""
    stmt = (
        select(Review)
        .where(Review.id == review_id)
        .options(selectinload(Review.findings), selectinload(Review.memories))
    )
    r = (await db.execute(stmt)).scalar_one_or_none()
    if not r:
        raise ResourceNotFoundError(f"Review session '{review_id}' was not found.")

    # Cross-team authorization check
    is_author = r.user_id == auth.user_id
    is_team_member = bool(r.team_id and auth.has_team_access(r.team_id))

    if not (is_author or is_team_member):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to view this review.",
        )

    return {
        "id": r.id,
        "code_diff": r.code_diff,
        "review": r.review_result,
        "model_used": r.model_used,
        "source": r.source,
        "status": r.status,
        "user_id": r.user_id,
        "team_id": r.team_id,
        "repository": r.repository,
        "commit_sha": r.commit_sha,
        "pr_number": r.pr_number,
        "file_path": r.file_path,
        "created_at": r.created_at.isoformat(),
        "severity_counts": _compute_severity_counts(r.findings).model_dump(),
        "findings": [
            {
                "id": f.id,
                "title": f.title,
                "description": f.description,
                "severity": f.severity,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "recommendation": f.recommendation,
            }
            for f in r.findings
        ],
        "memories": [
            {
                "id": m.id,
                "memory_text": m.memory_text,
                "hindsight_memory_id": m.hindsight_memory_id,
                "relevance_metadata": m.relevance_metadata,
            }
            for m in r.memories
        ],
    }
