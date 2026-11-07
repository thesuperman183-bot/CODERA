"""Authentication and Personal Access Token (PAT) management router."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.security import (
    AuthenticatedContext,
    ROLE_MEMBER,
    generate_pat,
    get_current_user,
)
from backend.database import get_db
from backend.models import ApiToken, Team, TeamMember, User
from backend.schemas import (
    CliLoginRequest,
    CliLoginResponse,
    CreateTokenRequest,
    MessageResponse,
    TeamMembershipInfo,
    TokenCreatedResponse,
    TokenListItem,
    UserProfileResponse,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/me", response_model=UserProfileResponse, summary="Get current user profile and team roles")
async def get_me(
    user_ctx: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Return the profile and team role mappings of the authenticated caller."""
    stmt = (
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user_ctx.user_id)
    )
    memberships = (await db.execute(stmt)).scalars().all()
    teams = [
        TeamMembershipInfo(
            team_id=m.team_id,
            team_name=m.team.name if m.team else "Unnamed Team",
            role=m.role,
        )
        for m in memberships
    ]
    return UserProfileResponse(
        id=user_ctx.user_id,
        email=user_ctx.email,
        name=user_ctx.name,
        teams=teams,
    )


@router.post("/tokens", response_model=TokenCreatedResponse, summary="Mint a new Personal Access Token for CLI/API")
async def create_api_token(
    request: CreateTokenRequest,
    user_ctx: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenCreatedResponse:
    """Generate a secure Personal Access Token. The raw token is returned once and not stored in plaintext."""
    raw_token, token_hash, prefix = generate_pat()
    token_id = str(uuid.uuid4())

    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)

    db_token = ApiToken(
        id=token_id,
        user_id=user_ctx.user_id,
        name=request.name,
        token_hash=token_hash,
        token_prefix=prefix,
        expires_at=expires_at,
    )
    db.add(db_token)
    await db.commit()

    return TokenCreatedResponse(
        token=raw_token,
        token_id=token_id,
        name=request.name,
        token_prefix=prefix,
        expires_at=expires_at.isoformat() if expires_at else None,
    )


@router.get("/tokens", response_model=List[TokenListItem], summary="List active Personal Access Tokens")
async def list_api_tokens(
    user_ctx: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TokenListItem]:
    """List all Personal Access Tokens minted for the current user."""
    stmt = (
        select(ApiToken)
        .where(ApiToken.user_id == user_ctx.user_id)
        .order_by(ApiToken.created_at.desc())
    )
    tokens = (await db.execute(stmt)).scalars().all()
    return [
        TokenListItem(
            id=t.id,
            name=t.name,
            token_prefix=t.token_prefix,
            created_at=t.created_at.isoformat(),
            expires_at=t.expires_at.isoformat() if t.expires_at else None,
            last_used_at=t.last_used_at.isoformat() if t.last_used_at else None,
        )
        for t in tokens
    ]


@router.delete("/tokens/{token_id}", response_model=MessageResponse, summary="Revoke a Personal Access Token")
async def revoke_api_token(
    token_id: str,
    user_ctx: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Permanently delete / revoke a Personal Access Token."""
    stmt = delete(ApiToken).where(
        ApiToken.id == token_id,
        ApiToken.user_id == user_ctx.user_id,
    )
    res = await db.execute(stmt)
    await db.commit()
    if res.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Token '{token_id}' not found or not owned by you.",
        )
    return MessageResponse(message="Token successfully revoked.")


@router.post("/cli-login", response_model=CliLoginResponse, summary="CLI user login and automatic PAT generation")
async def cli_login(
    payload: CliLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> CliLoginResponse:
    """Authenticate with user email and issue a dedicated CLI Personal Access Token."""
    email = payload.email.strip().lower()

    # Find or provision user in Neon
    stmt = select(User).where(User.email == email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            email=email,
            name=email.split("@")[0].capitalize(),
        )
        db.add(user)
        # Create a default personal team for new user
        team = Team(id=str(uuid.uuid4()), name=f"{user.name}'s Team")
        db.add(team)
        membership = TeamMember(
            id=str(uuid.uuid4()),
            user_id=user.id,
            team_id=team.id,
            role="owner",
        )
        db.add(membership)
        await db.flush()

    # Generate dedicated CLI PAT
    raw_token, token_hash, prefix = generate_pat()
    token_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=90)

    token_record = ApiToken(
        id=token_id,
        user_id=user.id,
        name=payload.token_name or "CLI Access Token",
        token_hash=token_hash,
        token_prefix=prefix,
        expires_at=expires_at,
    )
    db.add(token_record)
    await db.commit()

    # Fetch team memberships
    m_stmt = (
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user.id)
    )
    memberships = (await db.execute(m_stmt)).scalars().all()
    teams = [
        TeamMembershipInfo(
            team_id=m.team_id,
            team_name=m.team.name if m.team else "Team",
            role=m.role,
        )
        for m in memberships
    ]

    return CliLoginResponse(
        token=raw_token,
        user=UserProfileResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            teams=teams,
        ),
    )
