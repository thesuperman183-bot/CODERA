"""Router for Hindsight long-term memory operations, Inspector telemetry, and RBAC."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.config import settings
from backend.core.exceptions import AppException
from backend.core.security import AuthenticatedContext, get_current_user
from backend.database import get_db
from backend.models import HindsightBank, RetainedFact, Review, ReviewMemory, Team, TeamRule
from backend.schemas import (
    ActiveBankInfo,
    RecallRequest,
    RecallResponse,
    RetainedFactItem,
    RetainRequest,
    RetainResponse,
    ReviewMemoryTraceItem,
    ReviewMemoryTraceResponse,
    SearchMemoryResponse,
    SearchMemoryResultItem,
)
from backend.services.hindsight_service import hindsight_service
from backend.services.review_service import review_processor

router = APIRouter(tags=["Memories"])


@router.get(
    "/api/memories/active-bank",
    response_model=ActiveBankInfo,
    summary="Retrieve active Hindsight Bank metadata and status",
)
async def get_active_bank_info(
    team_id: Optional[str] = Query(default=None, description="Optional team filter"),
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActiveBankInfo:
    """Resolve active Hindsight memory bank ID, associated team, status, and memory stats."""
    if team_id:
        auth.require_team_access(team_id)
        effective_team_id = team_id
    elif auth.team_ids:
        effective_team_id = next(iter(auth.team_ids))
    else:
        effective_team_id = None

    bank_id = settings.hindsight_bank_id or "default"
    bank_type = "team" if effective_team_id else "personal"
    team_name = None

    if effective_team_id:
        # Check team name
        t_stmt = select(Team.name).where(Team.id == effective_team_id)
        t_name = (await db.execute(t_stmt)).scalar_one_or_none()
        if t_name:
            team_name = t_name

        # Query explicit bank mapping from Neon
        b_stmt = select(HindsightBank).where(
            and_(
                HindsightBank.team_id == effective_team_id,
                HindsightBank.is_active == True,  # noqa: E712
            )
        )
        custom_bank = (await db.execute(b_stmt)).scalar_one_or_none()
        if custom_bank:
            bank_id = custom_bank.bank_id
            bank_type = custom_bank.bank_type

    # Count retained facts
    fact_conditions = []
    if effective_team_id:
        fact_conditions.append(RetainedFact.team_id == effective_team_id)
    else:
        fact_conditions.append(RetainedFact.user_id == auth.user_id)
    fact_count = (await db.execute(select(func.count(RetainedFact.id)).where(or_(*fact_conditions)))).scalar() or 0

    # Count team rules
    rule_conditions = []
    if effective_team_id:
        rule_conditions.append(TeamRule.team_id == effective_team_id)
    else:
        rule_conditions.append(TeamRule.created_by == auth.user_id)
    rule_count = (await db.execute(select(func.count(TeamRule.id)).where(or_(*rule_conditions)))).scalar() or 0

    is_configured = bool(settings.hindsight_api_key)

    return ActiveBankInfo(
        bank_id=bank_id,
        team_id=effective_team_id,
        team_name=team_name,
        bank_type=bank_type,
        status="active" if is_configured else "unconfigured",
        is_active=is_configured,
        total_facts=fact_count,
        total_rules=rule_count,
        total_available_memories=fact_count + rule_count,
    )


@router.get(
    "/api/memories/facts",
    response_model=List[RetainedFactItem],
    summary="List retained memory facts scoped to user/team",
)
async def list_retained_facts(
    team_id: Optional[str] = Query(default=None, description="Optional team filter"),
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RetainedFactItem]:
    """Fetch retained memory items stored in Neon with their Hindsight memory identifiers."""
    if team_id:
        auth.require_team_access(team_id)
        effective_team_id = team_id
    elif auth.team_ids:
        effective_team_id = next(iter(auth.team_ids))
    else:
        effective_team_id = None

    conditions = []
    if effective_team_id:
        conditions.append(RetainedFact.team_id == effective_team_id)
    else:
        conditions.append(RetainedFact.user_id == auth.user_id)

    stmt = (
        select(RetainedFact)
        .where(or_(*conditions))
        .order_by(RetainedFact.created_at.desc())
        .limit(limit)
    )
    facts = (await db.execute(stmt)).scalars().all()

    return [
        RetainedFactItem(
            id=f.id,
            memory_id=f.hindsight_memory_id,
            content=f.content,
            tags=f.tags or [],
            created_at=f.created_at.isoformat(),
            team_id=f.team_id,
            user_id=f.user_id,
        )
        for f in facts
    ]


@router.post(
    "/api/memories/search",
    response_model=SearchMemoryResponse,
    summary="Search memory bank for matching rules & facts with metadata",
)
async def search_memories(
    query: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(default=5, ge=1, le=20),
    team_id: Optional[str] = Query(default=None, description="Optional team filter"),
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchMemoryResponse:
    """Perform vector semantic recall query against Hindsight bank."""
    if team_id:
        auth.require_team_access(team_id)
        effective_team_id = team_id
    elif auth.team_ids:
        effective_team_id = next(iter(auth.team_ids))
    else:
        effective_team_id = None

    bank_id = settings.hindsight_bank_id or "default"
    if effective_team_id:
        b_stmt = select(HindsightBank.bank_id).where(
            and_(
                HindsightBank.team_id == effective_team_id,
                HindsightBank.is_active == True,  # noqa: E712
            )
        )
        cb = (await db.execute(b_stmt)).scalar_one_or_none()
        if cb:
            bank_id = cb

    try:
        memories = hindsight_service.recall(query=query, top_k=limit, bank_id=bank_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Hindsight recall failed: {exc}",
        ) from exc

    results = [
        SearchMemoryResultItem(
            text=mem,
            relevance_rank=idx + 1,
            source_type="hindsight_bank",
            metadata={"bank_id": bank_id, "query": query},
        )
        for idx, mem in enumerate(memories)
    ]

    return SearchMemoryResponse(
        query=query,
        bank_id=bank_id,
        count=len(results),
        results=results,
    )


@router.get(
    "/api/memories/review-trace/{review_id}",
    response_model=ReviewMemoryTraceResponse,
    summary="Inspect memories injected into a specific review session",
)
async def get_review_memory_trace(
    review_id: str,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewMemoryTraceResponse:
    """Retrieve memories that were recalled and injected into a given code review."""
    stmt = (
        select(Review)
        .options(selectinload(Review.memories))
        .where(Review.id == review_id)
    )
    r = (await db.execute(stmt)).scalar_one_or_none()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review session '{review_id}' was not found.",
        )

    # Authorization check
    is_owner = r.user_id == auth.user_id
    is_team_member = bool(r.team_id and auth.has_team_access(r.team_id))
    if not (is_owner or is_team_member):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this review session.",
        )

    injected = [
        ReviewMemoryTraceItem(
            id=m.id,
            memory_text=m.memory_text,
            hindsight_memory_id=m.hindsight_memory_id,
            source_type=m.relevance_metadata.get("source", "hindsight_recall"),
            bank_id=m.relevance_metadata.get("bank_id"),
        )
        for m in r.memories
    ]

    return ReviewMemoryTraceResponse(
        review_id=r.id,
        review_status=r.status,
        model_used=r.model_used,
        created_at=r.created_at.isoformat(),
        injected_memories=injected,
        total_injected=len(injected),
    )


# -----------------------------------------------------------------------------
# Retain & Recall Endpoints (Backward compatible)
# -----------------------------------------------------------------------------

@router.post(
    "/api/retain",
    response_model=RetainResponse,
    summary="Retain review rule in Hindsight and Neon with authorization",
)
async def retain_compat(
    request: RetainRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RetainResponse:
    """Save rule to Hindsight and Neon with tenant isolation and authorization checks."""
    try:
        request.user_id = auth.user_id

        if request.team_id:
            auth.require_team_access(request.team_id)
            auth.require_team_role(request.team_id, ("owner", "admin"))
        elif auth.team_ids:
            request.team_id = next(iter(auth.team_ids))

        return await review_processor.retain_rule(request, session=db)
    except AppException:
        raise
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retention error: {exc}",
        ) from exc


@router.post(
    "/api/memories/retain",
    response_model=RetainResponse,
    summary="Retain memory item in Hindsight and Neon",
)
async def retain_memory(
    request: RetainRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RetainResponse:
    """Store rule in Hindsight Cloud and metadata in Neon."""
    request.user_id = auth.user_id
    if request.team_id:
        auth.require_team_access(request.team_id)
        auth.require_team_role(request.team_id, ("owner", "admin"))
    return await review_processor.retain_rule(request, session=db)


@router.post(
    "/api/memories/recall",
    response_model=RecallResponse,
    summary="Recall relevant memories from Hindsight",
)
def recall_memories(
    request: RecallRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
) -> RecallResponse:
    """Query Hindsight memory bank for matching rules or guidelines."""
    memories = hindsight_service.recall(
        query=request.query,
        top_k=request.top_k,
    )
    return RecallResponse(
        query=request.query,
        memories=memories,
        count=len(memories),
    )
