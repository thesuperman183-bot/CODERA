"""Router for team settings, workspace configuration, and RBAC member management."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.config import settings
from backend.core.security import AuthenticatedContext, get_current_user
from backend.database import get_db
from backend.models import HindsightBank, Team, TeamMember, TeamRule, User
from backend.schemas import (
    ActiveBankInfo,
    InviteMemberRequest,
    TeamListItem,
    TeamMemberItem,
    TeamModelConfig,
    TeamRuleDetailItem,
    TeamSettingsResponse,
    UpdateMemberRoleRequest,
    UpdateTeamSettingsRequest,
)

router = APIRouter(prefix="/api/teams", tags=["Team Settings"])


@router.get("", response_model=List[TeamListItem], summary="List teams the user belongs to")
async def list_user_teams(
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TeamListItem]:
    """Retrieve all teams where the authenticated user is an active member."""
    stmt = (
        select(Team, TeamMember.role)
        .join(TeamMember, Team.id == TeamMember.team_id)
        .where(TeamMember.user_id == auth.user_id)
        .order_by(Team.created_at.desc())
    )
    results = (await db.execute(stmt)).all()

    items = []
    for team, role in results:
        # Count members in team
        m_count = (
            await db.execute(
                select(func.count(TeamMember.id)).where(TeamMember.team_id == team.id)
            )
        ).scalar() or 1
        items.append(
            TeamListItem(
                id=team.id,
                name=team.name,
                role=role,
                member_count=m_count,
                created_at=team.created_at.isoformat(),
            )
        )
    return items


@router.get("/{team_id}/settings", response_model=TeamSettingsResponse, summary="Get full team settings and members")
async def get_team_settings(
    team_id: str,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamSettingsResponse:
    """Retrieve team workspace settings, members, rules, bank status, and CLI configuration."""
    auth.require_team_access(team_id)
    caller_role = auth.get_team_role(team_id) or "member"
    can_manage = caller_role in ("owner", "admin")

    # Fetch team
    t_stmt = select(Team).where(Team.id == team_id)
    team = (await db.execute(t_stmt)).scalar_one_or_none()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team '{team_id}' not found.",
        )

    # Fetch members with user details
    m_stmt = (
        select(TeamMember, User)
        .join(User, TeamMember.user_id == User.id)
        .where(TeamMember.team_id == team_id)
        .order_by(TeamMember.role.asc())
    )
    members_raw = (await db.execute(m_stmt)).all()
    member_items = [
        TeamMemberItem(
            user_id=u.id,
            email=u.email,
            name=u.name or u.email.split("@")[0],
            role=tm.role,
            joined_at=u.created_at.isoformat(),
        )
        for tm, u in members_raw
    ]

    # Fetch team rules
    r_stmt = (
        select(TeamRule, User.name, User.email)
        .outerjoin(User, TeamRule.created_by == User.id)
        .where(TeamRule.team_id == team_id)
        .order_by(TeamRule.created_at.desc())
    )
    rules_raw = (await db.execute(r_stmt)).all()
    rule_items = [
        TeamRuleDetailItem(
            id=rule.id,
            rule_text=rule.rule_text,
            hindsight_memory_id=rule.hindsight_memory_id,
            created_by=rule.created_by,
            creator_name=u_name or (u_email.split("@")[0] if u_email else "System"),
            created_at=rule.created_at.isoformat(),
        )
        for rule, u_name, u_email in rules_raw
    ]

    # Fetch active Hindsight bank
    b_stmt = select(HindsightBank).where(
        and_(
            HindsightBank.team_id == team_id,
            HindsightBank.is_active == True,  # noqa: E712
        )
    )
    custom_bank = (await db.execute(b_stmt)).scalar_one_or_none()
    bank_id = custom_bank.bank_id if custom_bank else (settings.hindsight_bank_id or f"team-{team_id[:8]}")
    bank_type = custom_bank.bank_type if custom_bank else "team"

    is_configured = bool(settings.hindsight_api_key)

    active_bank = ActiveBankInfo(
        bank_id=bank_id,
        team_id=team_id,
        team_name=team.name,
        bank_type=bank_type,
        status="active" if is_configured else "unconfigured",
        is_active=is_configured,
        total_facts=0,
        total_rules=len(rule_items),
        total_available_memories=len(rule_items),
    )

    # CLI connection instructions customized with user email & team context
    cli_instructions = {
        "login": f"review-agent login --email {auth.email}",
        "whoami": "review-agent whoami",
        "check": "review-agent check path/to/feature.diff",
        "history": "review-agent history --limit 10",
        "learn": 'review-agent learn "All API endpoints must validate input schemas."',
        "env_setup": "export REVIEW_AGENT_API_URL=http://localhost:8000",
    }

    return TeamSettingsResponse(
        team_id=team.id,
        team_name=team.name,
        current_user_role=caller_role,
        can_manage=can_manage,
        members=member_items,
        rules=rule_items,
        active_hindsight_bank=active_bank,
        ai_model_config=TeamModelConfig(),
        cli_instructions=cli_instructions,
    )


@router.put("/{team_id}/settings", response_model=Dict[str, Any], summary="Update team workspace settings")
async def update_team_settings(
    team_id: str,
    payload: UpdateTeamSettingsRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update team name or active Hindsight bank ID. Requires Owner or Admin role."""
    auth.require_team_access(team_id)
    auth.require_team_role(team_id, ("owner", "admin"))

    t_stmt = select(Team).where(Team.id == team_id)
    team = (await db.execute(t_stmt)).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")

    if payload.name and payload.name.strip():
        team.name = payload.name.strip()

    if payload.hindsight_bank_id and payload.hindsight_bank_id.strip():
        # Update or create HindsightBank record
        b_stmt = select(HindsightBank).where(
            and_(HindsightBank.team_id == team_id, HindsightBank.is_active == True)  # noqa: E712
        )
        bank = (await db.execute(b_stmt)).scalar_one_or_none()
        if bank:
            bank.bank_id = payload.hindsight_bank_id.strip()
        else:
            bank = HindsightBank(
                id=str(uuid.uuid4()),
                team_id=team_id,
                bank_id=payload.hindsight_bank_id.strip(),
                bank_type="team",
                is_active=True,
            )
            db.add(bank)

    await db.commit()
    return {"status": "updated", "team_id": team_id, "name": team.name}


@router.post("/{team_id}/members/invite", response_model=TeamMemberItem, summary="Invite/add a member to the team")
async def invite_team_member(
    team_id: str,
    payload: InviteMemberRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberItem:
    """Add user to team with assigned role. Requires Owner or Admin role."""
    auth.require_team_access(team_id)
    auth.require_team_role(team_id, ("owner", "admin"))

    email_clean = payload.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address.")

    desired_role = payload.role.strip().lower()
    if desired_role not in ("admin", "member"):
        desired_role = "member"

    # Find or provision user
    u_stmt = select(User).where(User.email == email_clean)
    user = (await db.execute(u_stmt)).scalar_one_or_none()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=email_clean,
            name=email_clean.split("@")[0].title(),
        )
        db.add(user)
        await db.flush()

    # Check existing membership
    m_stmt = select(TeamMember).where(
        and_(TeamMember.team_id == team_id, TeamMember.user_id == user.id)
    )
    existing_member = (await db.execute(m_stmt)).scalar_one_or_none()
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{email_clean}' is already a member of this team.",
        )

    # Create membership
    new_member = TeamMember(
        id=str(uuid.uuid4()),
        team_id=team_id,
        user_id=user.id,
        role=desired_role,
    )
    db.add(new_member)
    await db.commit()

    return TeamMemberItem(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=new_member.role,
        joined_at=user.created_at.isoformat(),
    )


@router.put("/{team_id}/members/{user_id}/role", response_model=Dict[str, Any], summary="Update team member role")
async def update_member_role(
    team_id: str,
    user_id: str,
    payload: UpdateMemberRoleRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Change member role between admin and member, or transfer owner. Requires Owner or Admin role."""
    auth.require_team_access(team_id)
    caller_role = auth.get_team_role(team_id)
    auth.require_team_role(team_id, ("owner", "admin"))

    desired_role = payload.role.strip().lower()
    if desired_role not in ("owner", "admin", "member"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role specified.")

    # Admins cannot promote anyone to owner
    if desired_role == "owner" and caller_role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the current team owner can transfer ownership.",
        )

    m_stmt = select(TeamMember).where(
        and_(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
    )
    target_member = (await db.execute(m_stmt)).scalar_one_or_none()
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in team.")

    if target_member.role == "owner" and caller_role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change role of team owner.",
        )

    target_member.role = desired_role
    await db.commit()
    return {"status": "updated", "user_id": user_id, "role": desired_role}


@router.delete("/{team_id}/members/{user_id}", response_model=Dict[str, Any], summary="Remove member from team")
async def remove_team_member(
    team_id: str,
    user_id: str,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Remove user from team. Requires Owner or Admin role."""
    auth.require_team_access(team_id)
    caller_role = auth.get_team_role(team_id)
    auth.require_team_role(team_id, ("owner", "admin"))

    m_stmt = select(TeamMember).where(
        and_(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
    )
    target_member = (await db.execute(m_stmt)).scalar_one_or_none()
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in team.")

    if target_member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove team owner. Transfer ownership before leaving.",
        )

    if target_member.role == "admin" and caller_role != "owner" and user_id != auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team owners can remove other admins.",
        )

    await db.delete(target_member)
    await db.commit()
    return {"status": "removed", "user_id": user_id, "team_id": team_id}


@router.delete("/{team_id}/rules/{rule_id}", response_model=Dict[str, Any], summary="Delete a team review rule")
async def delete_team_rule(
    team_id: str,
    rule_id: str,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a team rule. Requires Owner or Admin role."""
    auth.require_team_access(team_id)
    auth.require_team_role(team_id, ("owner", "admin"))

    r_stmt = select(TeamRule).where(
        and_(TeamRule.team_id == team_id, TeamRule.id == rule_id)
    )
    rule = (await db.execute(r_stmt)).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found.")

    await db.delete(rule)
    await db.commit()
    return {"status": "deleted", "rule_id": rule_id, "team_id": team_id}
