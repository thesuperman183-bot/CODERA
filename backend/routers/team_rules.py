"""Router for managing team review rules with RBAC authorization."""
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import AuthenticatedContext, get_current_user
from backend.database import get_db
from backend.models import TeamRule
from backend.schemas import RetainRequest, RuleItem, RulesListResponse
from backend.services.review_service import review_processor

router = APIRouter(prefix="/api/rules", tags=["Team Rules"])


@router.get("", response_model=RulesListResponse, summary="List team review rules authorized for current user")
async def list_rules(
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RulesListResponse:
    """Return team rules restricted to the caller's teams or global rules."""
    conditions = [TeamRule.team_id.is_(None)]
    if auth.team_ids:
        conditions.append(TeamRule.team_id.in_(auth.team_ids))

    stmt = select(TeamRule).where(or_(*conditions)).order_by(TeamRule.created_at.desc())
    rules = (await db.execute(stmt)).scalars().all()
    items = [
        RuleItem(
            id=r.id,
            rule=r.rule_text,
            tags=[],
            created_at=r.created_at.isoformat(),
        )
        for r in rules
    ]
    return RulesListResponse(rules=items, count=len(items))


@router.post("", response_model=RuleItem, summary="Add team review rule (Requires Owner or Admin role)")
async def create_rule(
    request: RetainRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RuleItem:
    """Store rule in Hindsight and Neon. Requires Owner or Admin role if team is specified."""
    request.user_id = auth.user_id
    if request.team_id:
        auth.require_team_access(request.team_id)
        auth.require_team_role(request.team_id, ("owner", "admin"))
    elif auth.team_ids:
        request.team_id = next(iter(auth.team_ids))

    res = await review_processor.retain_rule(request, session=db)
    return RuleItem(
        id=res.rule_id,
        rule=request.rule,
        tags=request.tags,
        created_at=None,
    )


@router.delete("/{rule_id}", summary="Delete team review rule (Requires Owner or Admin role)")
async def delete_rule(
    rule_id: str,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a team rule with authorization verification."""
    stmt = select(TeamRule).where(TeamRule.id == rule_id)
    rule = (await db.execute(stmt)).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found.")

    if rule.team_id:
        auth.require_team_access(rule.team_id)
        auth.require_team_role(rule.team_id, ("owner", "admin"))
    elif rule.created_by != auth.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another user's personal rule.")

    await db.delete(rule)
    await db.commit()
    return {"status": "deleted", "rule_id": rule_id}

