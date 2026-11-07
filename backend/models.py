"""SQLAlchemy 2.x database models for persistent application data."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _gen_uuid() -> str:
    """Generate string UUID identifier."""
    return str(uuid.uuid4())


class User(Base):
    """User account entity."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    team_memberships: Mapped[List[TeamMember]] = relationship("TeamMember", back_populates="user", cascade="all, delete-orphan")
    reviews: Mapped[List[Review]] = relationship("Review", back_populates="user")
    rules_created: Mapped[List[TeamRule]] = relationship("TeamRule", back_populates="creator")
    retained_facts: Mapped[List[RetainedFact]] = relationship("RetainedFact", back_populates="user")
    hindsight_banks: Mapped[List[HindsightBank]] = relationship("HindsightBank", back_populates="user")
    api_tokens: Mapped[List[ApiToken]] = relationship("ApiToken", back_populates="user", cascade="all, delete-orphan")
    github_account: Mapped[Optional[UserGitHubAccount]] = relationship("UserGitHubAccount", back_populates="user", cascade="all, delete-orphan", uselist=False)


class ApiToken(Base):
    """Personal Access Token for CLI and automated API authentication."""

    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # SHA-256 of token
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)  # Display prefix e.g. "cra_pat_abc12"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="api_tokens")


class Team(Base):
    """Team entity for collaborative code reviews and isolated rule banks."""

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    members: Mapped[List[TeamMember]] = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    reviews: Mapped[List[Review]] = relationship("Review", back_populates="team")
    rules: Mapped[List[TeamRule]] = relationship("TeamRule", back_populates="team", cascade="all, delete-orphan")
    retained_facts: Mapped[List[RetainedFact]] = relationship("RetainedFact", back_populates="team", cascade="all, delete-orphan")
    hindsight_banks: Mapped[List[HindsightBank]] = relationship("HindsightBank", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    """Membership association mapping users to teams with role-based permissions."""

    __tablename__ = "team_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="member", nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="team_memberships")
    team: Mapped[Team] = relationship("Team", back_populates="members")


class Review(Base):
    """Code review session with diff, results, model provenance, and execution source."""

    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    team_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("teams.id", ondelete="SET NULL"), index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="CLI", nullable=False)  # CLI or Web
    repository: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)  # owner/repo
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    pr_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    code_diff: Mapped[str] = mapped_column(Text, nullable=False)
    review_result: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    # Relationships
    user: Mapped[Optional[User]] = relationship("User", back_populates="reviews")
    team: Mapped[Optional[Team]] = relationship("Team", back_populates="reviews")
    findings: Mapped[List[ReviewFinding]] = relationship("ReviewFinding", back_populates="review", cascade="all, delete-orphan")
    memories: Mapped[List[ReviewMemory]] = relationship("ReviewMemory", back_populates="review", cascade="all, delete-orphan")


class ReviewFinding(Base):
    """Granular actionable finding identified within a code review."""

    __tablename__ = "review_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    review_id: Mapped[str] = mapped_column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="medium", nullable=False, index=True)  # info, low, medium, high, critical
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    review: Mapped[Review] = relationship("Review", back_populates="findings")


class RetainedFact(Base):
    """Retained rule or fact stored for long-term memory guidance."""

    __tablename__ = "retained_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    team_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    hindsight_memory_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    tags: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    team: Mapped[Optional[Team]] = relationship("Team", back_populates="retained_facts")
    user: Mapped[Optional[User]] = relationship("User", back_populates="retained_facts")


class TeamRule(Base):
    """Organizational team-level coding rules."""

    __tablename__ = "team_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    team_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    hindsight_memory_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    team: Mapped[Optional[Team]] = relationship("Team", back_populates="rules")
    creator: Mapped[Optional[User]] = relationship("User", back_populates="rules_created")


class HindsightBank(Base):
    """Configuration mapping teams or users to specific Hindsight memory bank identifiers."""

    __tablename__ = "hindsight_banks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    team_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    bank_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    bank_type: Mapped[str] = mapped_column(String(50), default="team", nullable=False)  # team or personal
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    team: Mapped[Optional[Team]] = relationship("Team", back_populates="hindsight_banks")
    user: Mapped[Optional[User]] = relationship("User", back_populates="hindsight_banks")


class ReviewMemory(Base):
    """Trace of recalled memories/rules utilized in a particular review session."""

    __tablename__ = "review_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    review_id: Mapped[str] = mapped_column(String(36), ForeignKey("reviews.id", ondelete="CASCADE"), index=True, nullable=False)
    hindsight_memory_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    memory_text: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    review: Mapped[Review] = relationship("Review", back_populates="memories")


class UserGitHubAccount(Base):
    """Secure OAuth / GitHub App token connection for user repository access."""

    __tablename__ = "user_github_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    github_user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    github_username: Mapped[str] = mapped_column(String(100), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # Stored securely on server
    token_type: Mapped[str] = mapped_column(String(50), default="bearer", nullable=False)
    scope: Mapped[Optional[str]] = mapped_column(String(255), default="repo,read:user", nullable=True)
    installation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="github_account")

