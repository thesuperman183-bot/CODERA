"""Pull Request Intelligence and Review Router.

Endpoints for:
- Listing and ranking Pull Requests with explanatory recommendation reasons
- Fetching PR changed files and unified diffs
- Executing memory-guided AI review on a PR and saving results in Neon
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import AuthenticatedContext, get_current_user
from backend.database import get_db
from backend.models import TeamRule
from backend.routers.github import _get_user_github_token
from backend.schemas import (
    PullRequestItem,
    ReviewPullRequestRequest,
    ReviewRequest,
    ReviewResponse,
)
from backend.services.github_service import GitHubAPIError, github_service
from backend.services.pr_analysis_service import pr_analysis_service
from backend.services.review_service import review_processor

router = APIRouter(prefix="/api/pull-requests", tags=["Pull Requests"])


@router.get("/{owner}/{repo}", response_model=List[PullRequestItem], summary="List and rank repository pull requests with intelligence")
async def list_and_analyze_pull_requests(
    owner: str,
    repo: str,
    language: Optional[str] = Query(default=None, description="Filter by language"),
    framework: Optional[str] = Query(default=None, description="Filter by framework"),
    state: str = Query(default="open", description="PR state: open, closed, or all"),
    team_id: Optional[str] = Query(default=None, description="Team ID for rule matching"),
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[PullRequestItem]:
    """Retrieve PRs, evaluate changed files, and rank recommendations with clear explanatory reasons."""
    token = await _get_user_github_token(auth.user_id, db, optional=True)
    if not token:
        return []

    # 1. Fetch team rules for intelligence scoring
    team_rules: List[str] = []
    rule_conditions = []
    if team_id:
        auth.require_team_access(team_id)
        rule_conditions.append(TeamRule.team_id == team_id)
    elif auth.team_ids:
        rule_conditions.append(TeamRule.team_id.in_(auth.team_ids))
    rule_conditions.append(TeamRule.team_id.is_(None))

    stmt = select(TeamRule.rule_text).where(*rule_conditions)
    rules_res = (await db.execute(stmt)).scalars().all()
    team_rules = list(rules_res)

    try:
        # 2. Fetch raw PRs from GitHub API
        raw_prs = await github_service.list_pull_requests(owner, repo, access_token=token, state=state, per_page=30)
        if not raw_prs:
            return []

        # 3. Concurrently fetch changed files for top PRs (capped at 15 for API efficiency)
        top_prs = raw_prs[:15]
        files_by_pr: Dict[int, List[Dict[str, Any]]] = {}

        async def fetch_pr_files(pr_num: int):
            try:
                files = await github_service.get_pull_request_files(owner, repo, pr_num, token)
                files_by_pr[pr_num] = files
            except Exception:
                files_by_pr[pr_num] = []

        await asyncio.gather(*(fetch_pr_files(p.get("number")) for p in top_prs))

        # 4. Analyze and rank PRs with clear human-readable reasons
        ranked_prs = pr_analysis_service.analyze_and_rank_pull_requests(
            pull_requests=top_prs,
            files_by_pr=files_by_pr,
            team_rules=team_rules,
            language_filter=language,
            framework_filter=framework,
        )

        return [PullRequestItem(**item) for item in ranked_prs]

    except GitHubAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/review", response_model=ReviewResponse, summary="Execute deep AI review on a Pull Request")
async def review_pull_request(
    payload: ReviewPullRequestRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Fetch PR unified diff, invoke review pipeline with team rules and memories, and persist to Neon."""
    token = await _get_user_github_token(auth.user_id, db)
    repo_full_name = f"{payload.owner}/{payload.repo}"

    if payload.team_id:
        auth.require_team_access(payload.team_id)

    try:
        # 1. Fetch PR unified diff
        diff_text = await github_service.get_pull_request_diff(payload.owner, payload.repo, payload.pr_number, token)
        if not diff_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pull Request #{payload.pr_number} contains no diff changes.",
            )

        # 2. Fetch PR metadata for commit SHA
        pr_meta = await github_service.get_pull_request(payload.owner, payload.repo, payload.pr_number, token)
        commit_sha = pr_meta.get("head", {}).get("sha")

        # 3. Delegate to existing CodeReviewProcessor pipeline
        req = ReviewRequest(
            code_diff=diff_text,
            user_id=auth.user_id,
            team_id=payload.team_id,
            source="Web",
            repository=repo_full_name,
            commit_sha=commit_sha,
            pr_number=payload.pr_number,
        )

        return await review_processor.process_review(req, session=db)

    except GitHubAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

