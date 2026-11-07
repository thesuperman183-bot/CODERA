"""Pydantic request and response schemas for all API domains."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class FindingItem(BaseModel):
    """Actionable issue or recommendation extracted from review."""

    id: Optional[str] = None
    title: str
    description: str
    severity: str = "medium"
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    recommendation: Optional[str] = None


class ReviewRequest(BaseModel):
    """Payload for submitting code diffs for review."""

    code_diff: str = Field(..., min_length=1, max_length=500_000, description="Raw code diff or patch (max 500KB)")
    user_id: Optional[str] = Field(default=None, description="Optional user ID")
    team_id: Optional[str] = Field(default=None, description="Optional team ID")
    source: str = Field(default="CLI", description="Review submission source (CLI or Web)")
    repository: Optional[str] = Field(default=None, max_length=255, description="GitHub repository full name (owner/repo)")
    commit_sha: Optional[str] = Field(default=None, max_length=64, description="Commit SHA associated with review")
    pr_number: Optional[int] = Field(default=None, description="Pull Request number associated with review")
    file_path: Optional[str] = Field(default=None, max_length=500, description="Specific file path reviewed")

    @model_validator(mode="before")
    @classmethod
    def resolve_diff_alias(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "code_diff" not in values and "diff" in values:
                values["code_diff"] = values["diff"]
        return values

    @field_validator("code_diff")
    @classmethod
    def require_diff_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("code_diff must not be blank")
        return value


class ReviewResponse(BaseModel):
    """Review generation output matching existing contract with expanded Neon metadata."""

    review: str
    memories_used: List[str]
    review_id: Optional[str] = None
    findings: List[FindingItem] = Field(default_factory=list)
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    model_used: Optional[str] = None
    repository: Optional[str] = None
    commit_sha: Optional[str] = None
    pr_number: Optional[int] = None
    file_path: Optional[str] = None
    status: str = "completed"


class RetainRequest(BaseModel):
    """Payload for saving a coding guideline/rule to long-term memory."""

    rule: str = Field(..., min_length=1, max_length=5000, description="Rule description or guideline (max 5000 chars)")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    user_id: Optional[str] = Field(default=None, description="Optional user ID")
    team_id: Optional[str] = Field(default=None, description="Optional team ID")

    @field_validator("rule")
    @classmethod
    def require_rule_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rule must not be blank")
        return value


class RetainResponse(BaseModel):
    """Retention status response matching existing contract with Neon record IDs."""

    status: str = "retained"
    memory_id: Optional[str] = None
    rule_id: Optional[str] = None
    team_id: Optional[str] = None


class RecallRequest(BaseModel):
    """Query payload for recalling memories directly."""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def require_query_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class RecallResponse(BaseModel):
    """Recalled guidelines from long-term memory."""

    query: str
    memories: List[str]
    count: int


class RuleItem(BaseModel):
    """Team rule representation."""

    id: Optional[str] = None
    rule: str
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None


class RulesListResponse(BaseModel):
    """List of configured team rules."""

    rules: List[RuleItem]
    count: int


class DashboardStatsResponse(BaseModel):
    """High-level health and metric statistics for the web dashboard."""

    total_reviews: int
    total_rules: int
    critical_issues: int = 0
    retained_memories: int = 0
    system_status: str
    groq_model: str
    hindsight_configured: bool
    hindsight_bank_id: str = "default"
    total_available_memories: int = 0
    recent_retained_facts: List[Dict[str, Any]] = Field(default_factory=list)
    recent_reviews: List[Dict[str, Any]] = Field(default_factory=list)
    findings_by_severity: Dict[str, int] = Field(default_factory=dict)
    activity_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    project_issues: List[Dict[str, Any]] = Field(default_factory=list)


class CreateTokenRequest(BaseModel):
    """Payload to mint a new Personal Access Token."""

    name: str = Field(..., min_length=1, max_length=100, description="Token descriptive label")
    expires_in_days: Optional[int] = Field(default=30, ge=1, le=365, description="Token validity in days")


class TokenCreatedResponse(BaseModel):
    """Returned when a new Personal Access Token is generated (raw token shown once)."""

    token: str
    token_id: str
    name: str
    token_prefix: str
    expires_at: Optional[str] = None


class TokenListItem(BaseModel):
    """Summary of an active Personal Access Token."""

    id: str
    name: str
    token_prefix: str
    created_at: str
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None


class TeamMembershipInfo(BaseModel):
    """Team membership and role details."""

    team_id: str
    team_name: str
    role: str


class UserProfileResponse(BaseModel):
    """Authenticated user profile with team memberships."""

    id: str
    email: str
    name: Optional[str] = None
    teams: List[TeamMembershipInfo] = Field(default_factory=list)


class CliLoginRequest(BaseModel):
    """CLI credentials login request."""

    email: str = Field(..., min_length=3)
    password: Optional[str] = Field(default=None, description="Optional password for password-based login")
    token_name: Optional[str] = Field(default="CLI Personal Access Token")


class CliLoginResponse(BaseModel):
    """CLI login response containing newly issued PAT."""

    token: str
    user: UserProfileResponse


class MessageResponse(BaseModel):
    """Generic status or placeholder message."""

    message: str
    detail: Optional[str] = None


# -----------------------------------------------------------------------------
# GitHub Integration Schemas (Phase 9)
# -----------------------------------------------------------------------------

class ConnectGitHubRequest(BaseModel):
    """Request to link user's GitHub Personal Access Token or App Installation token."""

    access_token: str = Field(..., min_length=1, description="GitHub token with repo read access")


class GitHubConnectionStatus(BaseModel):
    """Status of user's GitHub account connection."""

    connected: bool
    github_username: Optional[str] = None
    created_at: Optional[str] = None


class GitHubRepoItem(BaseModel):
    """Repository accessible to the connected user."""

    id: int
    name: str
    full_name: str
    owner: str
    default_branch: str
    private: bool
    description: Optional[str] = None
    language: Optional[str] = None
    updated_at: Optional[str] = None
    html_url: Optional[str] = None


class GitHubBranchItem(BaseModel):
    """Branch in a GitHub repository."""

    name: str
    commit_sha: Optional[str] = None
    protected: bool = False


class GitHubTreeItem(BaseModel):
    """File or directory item in repository git tree."""

    path: str
    type: str  # "blob" or "tree"
    sha: str
    size: Optional[int] = None


class ReviewGitHubResourceRequest(BaseModel):
    """Request to trigger a code review on a GitHub file, commit diff, or branch compare."""

    owner: str
    repo: str
    ref: Optional[str] = Field(default=None, description="Branch or commit ref")
    file_path: Optional[str] = Field(default=None, description="Specific file path (if reviewing a file)")
    commit_sha: Optional[str] = Field(default=None, description="Commit SHA (if reviewing a commit diff)")
    base: Optional[str] = Field(default=None, description="Base branch (if comparing branches)")
    head: Optional[str] = Field(default=None, description="Head branch (if comparing branches)")
    team_id: Optional[str] = Field(default=None, description="Team ID for rules and bank resolution")


class ReviewPullRequestRequest(BaseModel):
    """Request to trigger a review on a GitHub Pull Request."""

    owner: str
    repo: str
    pr_number: int
    team_id: Optional[str] = None


class PullRequestFilterRequest(BaseModel):
    """Filters to query and rank pull requests with intelligence."""

    language: Optional[str] = None
    framework: Optional[str] = None
    state: str = "open"


class PullRequestItem(BaseModel):
    """Pull request overview with recommendation ranking and explanation reasons."""

    number: int
    title: str
    author: Optional[str] = None
    author_avatar: Optional[str] = None
    state: str
    html_url: Optional[str] = None
    base_branch: Optional[str] = None
    head_branch: Optional[str] = None
    head_sha: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    additions: int = 0
    deletions: int = 0
    changed_files_count: int = 0
    languages: List[str] = Field(default_factory=list)
    has_tests: bool = False
    recommendation_score: int = 50
    recommendation_priority: str = "medium"  # high, medium, low
    recommendation_reasons: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Hindsight Inspector Schemas (Phase 10)
# -----------------------------------------------------------------------------

class ActiveBankInfo(BaseModel):
    """Hindsight memory bank status and metadata."""

    bank_id: str
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    bank_type: str = "team"  # team, personal, or system
    status: str = "active"  # active or unconfigured
    is_active: bool = True
    total_facts: int = 0
    total_rules: int = 0
    total_available_memories: int = 0


class RetainedFactItem(BaseModel):
    """Retained fact stored in Neon and Hindsight."""

    id: str
    memory_id: Optional[str] = None
    content: str
    tags: List[str] = Field(default_factory=list)
    created_at: str
    team_id: Optional[str] = None
    user_id: Optional[str] = None


class SearchMemoryResultItem(BaseModel):
    """Individual memory item retrieved from Hindsight search query."""

    text: str
    relevance_rank: int
    source_type: str = "hindsight_bank"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchMemoryResponse(BaseModel):
    """Response from querying memory bank."""

    query: str
    bank_id: str
    count: int
    results: List[SearchMemoryResultItem] = Field(default_factory=list)


class ReviewMemoryTraceItem(BaseModel):
    """Detail of a memory injected into a specific review session."""

    id: str
    memory_text: str
    hindsight_memory_id: Optional[str] = None
    source_type: str  # "hindsight_recall" or "team_rule"
    bank_id: Optional[str] = None


class ReviewMemoryTraceResponse(BaseModel):
    """Review memory audit showing memories injected into review."""

    review_id: str
    review_status: str
    model_used: str
    created_at: str
    injected_memories: List[ReviewMemoryTraceItem] = Field(default_factory=list)
    total_injected: int = 0


# -----------------------------------------------------------------------------
# Review History & Intelligence Schemas (Phase 11)
# -----------------------------------------------------------------------------

class ReviewSeverityCounts(BaseModel):
    """Counts of findings broken down by severity."""

    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class ReviewHistoryItem(BaseModel):
    """Item in paginated review history list."""

    id: str
    repository: Optional[str] = None
    commit_sha: Optional[str] = None
    pr_number: Optional[int] = None
    file_path: Optional[str] = None
    created_at: str
    source: str  # "CLI" or "Web"
    status: str  # "completed", "failed", "pending"
    model_used: str
    findings_count: int
    severity_counts: ReviewSeverityCounts
    memories_count: int


class ReviewHistoryResponse(BaseModel):
    """Paginated review history response with facets and metadata."""

    items: List[ReviewHistoryItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10
    total_pages: int = 1
    unique_repositories: List[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Team Settings & RBAC Schemas (Phase 11)
# -----------------------------------------------------------------------------

class TeamMemberItem(BaseModel):
    """Team member details with role-based permissions."""

    user_id: str
    email: str
    name: Optional[str] = None
    role: str  # "owner", "admin", "member"
    joined_at: Optional[str] = None


class TeamRuleDetailItem(BaseModel):
    """Team rule with creator attribution and memory mapping."""

    id: str
    rule_text: str
    hindsight_memory_id: Optional[str] = None
    created_by: Optional[str] = None
    creator_name: Optional[str] = None
    created_at: str


class TeamModelConfig(BaseModel):
    """LLM configuration for the team workspace."""

    model: str = "llama-3.3-70b-versatile"
    provider: str = "Groq"
    temperature: float = 0.1
    max_tokens: int = 4096


class TeamSettingsResponse(BaseModel):
    """Complete team workspace settings, members, rules, and configuration."""

    team_id: str
    team_name: str
    current_user_role: str  # "owner", "admin", or "member"
    can_manage: bool  # True if owner or admin
    members: List[TeamMemberItem] = Field(default_factory=list)
    rules: List[TeamRuleDetailItem] = Field(default_factory=list)
    active_hindsight_bank: ActiveBankInfo
    ai_model_config: TeamModelConfig = Field(default_factory=TeamModelConfig)
    cli_instructions: Dict[str, str] = Field(default_factory=dict)


class TeamListItem(BaseModel):
    """Item for user's team list."""

    id: str
    name: str
    role: str
    member_count: int = 1
    created_at: str


class InviteMemberRequest(BaseModel):
    """Payload to invite a new team member."""

    email: str
    role: str = "member"  # "admin" or "member"


class UpdateMemberRoleRequest(BaseModel):
    """Payload to update member role."""

    role: str  # "owner", "admin", "member"


class UpdateTeamSettingsRequest(BaseModel):
    """Payload to update team workspace settings."""

    name: Optional[str] = None
    hindsight_bank_id: Optional[str] = None
    default_model: Optional[str] = None




