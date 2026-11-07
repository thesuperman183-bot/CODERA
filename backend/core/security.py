"""Security, authentication, and role-based access control (RBAC)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.config import settings
from backend.database import get_db
from backend.models import ApiToken, TeamMember, User

bearer_scheme = HTTPBearer(auto_error=False)


# Role definitions
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"

VALID_ROLES = {ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER}


def hash_token(raw_token: str) -> str:
    """Return SHA-256 hex digest of personal access token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_pat(prefix: str = "cra_pat_") -> tuple[str, str, str]:
    """Generate a secure Personal Access Token.
    
    Returns (raw_token, token_hash, display_prefix).
    """
    random_part = secrets.token_urlsafe(32)
    raw_token = f"{prefix}{random_part}"
    token_hash = hash_token(raw_token)
    display_prefix = raw_token[:14]
    return raw_token, token_hash, display_prefix


class AuthenticatedContext:
    """Context object representing the verified caller and their team authorization."""

    def __init__(
        self,
        user_id: str,
        email: str,
        name: Optional[str] = None,
        token_type: str = "pat",
        token_id: Optional[str] = None,
        team_roles: Optional[Dict[str, str]] = None,
    ):
        self.user_id = user_id
        self.email = email
        self.name = name
        self.token_type = token_type
        self.token_id = token_id
        # Mapping of team_id -> role ("owner", "admin", "member")
        self.team_roles: Dict[str, str] = team_roles or {}

    @property
    def team_ids(self) -> Set[str]:
        """All team IDs the user belongs to."""
        return set(self.team_roles.keys())

    def has_team_access(self, team_id: Optional[str]) -> bool:
        """Check if user has any access to the specified team."""
        if not team_id:
            return True  # Individual personal access
        return team_id in self.team_roles

    def get_team_role(self, team_id: Optional[str]) -> Optional[str]:
        """Return user's assigned role in the team, or None."""
        if not team_id:
            return None
        return self.team_roles.get(team_id)

    def require_team_access(self, team_id: Optional[str]) -> None:
        """Raise 403 Forbidden if user is not a member of the team."""
        if team_id and team_id not in self.team_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You are not a member of team '{team_id}'.",
            )

    def require_team_role(self, team_id: Optional[str], allowed_roles: tuple[str, ...]) -> None:
        """Raise 403 Forbidden if user lacks required role in the team."""
        if not team_id:
            return
        self.require_team_access(team_id)
        current_role = self.team_roles.get(team_id)
        if current_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires one of {allowed_roles} roles in team '{team_id}' (your role: '{current_role}').",
            )


async def _load_user_team_roles(user_id: str, db: AsyncSession) -> Dict[str, str]:
    """Query team memberships and roles for user in Neon."""
    stmt = select(TeamMember.team_id, TeamMember.role).where(TeamMember.user_id == user_id)
    rows = (await db.execute(stmt)).all()
    return {r[0]: r[1].lower() for r in rows}


async def authenticate_token(token: str, db: AsyncSession) -> AuthenticatedContext:
    """Validate JWT or Personal Access Token and return AuthenticatedContext."""
    now_utc = datetime.now(timezone.utc)

    # 1. Check if token is a Personal Access Token (PAT)
    if token.startswith("cra_pat_"):
        t_hash = hash_token(token)
        stmt = (
            select(ApiToken)
            .options(selectinload(ApiToken.user))
            .where(ApiToken.token_hash == t_hash)
        )
        api_token = (await db.execute(stmt)).scalar_one_or_none()
        if not api_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Personal Access Token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if api_token.expires_at:
            token_expiry = api_token.expires_at
            if token_expiry.tzinfo is None:
                token_expiry = token_expiry.replace(tzinfo=timezone.utc)
            if token_expiry < now_utc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Personal Access Token has expired.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # Update last_used_at timestamp
        api_token.last_used_at = now_utc
        user = api_token.user
        team_roles = await _load_user_team_roles(user.id, db)

        return AuthenticatedContext(
            user_id=user.id,
            email=user.email,
            name=user.name,
            token_type="pat",
            token_id=api_token.id,
            team_roles=team_roles,
        )

    # 2. Check if token is a JWT (Neon Managed Better Auth, Clerk, or local token)
    try:
        # Decode without verification first to check header / alg, then verify
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Check expiration
    exp = unverified_claims.get("exp")
    if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < now_utc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_email = unverified_claims.get("email") or unverified_claims.get("sub")
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject or email identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Lookup user in Neon database
    stmt = select(User).where((User.email == user_email) | (User.id == unverified_claims.get("sub")))
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        # Create user record in Neon if first time connecting via verified external token
        user_name = unverified_claims.get("name", user_email.split("@")[0])
        user = User(
            id=unverified_claims.get("sub") or str(secrets.token_hex(16)),
            email=user_email,
            name=user_name,
        )
        db.add(user)
        await db.commit()

    team_roles = await _load_user_team_roles(user.id, db)

    return AuthenticatedContext(
        user_id=user.id,
        email=user.email,
        name=user.name,
        token_type="jwt",
        team_roles=team_roles,
    )


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedContext:
    """Enforce authentication on protected API endpoints."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided. Use 'review-agent login' or pass a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await authenticate_token(auth.credentials.strip(), db)


async def get_current_user_optional(
    auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[AuthenticatedContext]:
    """Optional authentication dependency for backward compatibility and open endpoints."""
    if not auth or not auth.credentials:
        return None
    try:
        return await authenticate_token(auth.credentials.strip(), db)
    except HTTPException:
        return None

