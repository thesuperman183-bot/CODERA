"""GitHub Repository Integration Router.

Manages:
- Secure connection and revocation of user GitHub accounts
- Listing authorized repositories and branches
- Repository tree browsing and file content fetching
- Reviewing selected files or commit diffs via existing ReviewService pipeline
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import AuthenticatedContext, get_current_user
from backend.database import get_db
from backend.models import UserGitHubAccount
from backend.schemas import (
    ConnectGitHubRequest,
    GitHubBranchItem,
    GitHubConnectionStatus,
    GitHubRepoItem,
    GitHubTreeItem,
    MessageResponse,
    ReviewGitHubResourceRequest,
    ReviewRequest,
    ReviewResponse,
)
from backend.services.github_service import GitHubAPIError, github_service
from backend.services.review_service import review_processor

router = APIRouter(prefix="/api/github", tags=["GitHub Integration"])


async def _get_user_github_token(user_id: str, db: AsyncSession, optional: bool = False) -> Optional[str]:
    """Retrieve verified GitHub access token for the authenticated user."""
    stmt = select(UserGitHubAccount).where(UserGitHubAccount.user_id == user_id)
    account = (await db.execute(stmt)).scalar_one_or_none()
    if not account or not account.access_token_encrypted:
        if optional:
            return None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account not connected. Please connect your GitHub account in Settings or the Review Workspace.",
        )
    return account.access_token_encrypted


@router.get("/status", response_model=GitHubConnectionStatus, summary="Check user GitHub connection status")
async def get_github_connection_status(
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GitHubConnectionStatus:
    """Check if the current user has linked an active GitHub account."""
    stmt = select(UserGitHubAccount).where(UserGitHubAccount.user_id == auth.user_id)
    account = (await db.execute(stmt)).scalar_one_or_none()
    if not account:
        return GitHubConnectionStatus(connected=False)

    return GitHubConnectionStatus(
        connected=True,
        github_username=account.github_username,
        created_at=account.created_at.isoformat(),
    )


@router.post("/connect", response_model=GitHubConnectionStatus, summary="Connect GitHub token for user")
async def connect_github_account(
    payload: ConnectGitHubRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GitHubConnectionStatus:
    """Verify GitHub access token with GitHub API, store securely on server, and link to user."""
    token = payload.access_token.strip()

    try:
        profile = await github_service.get_user_profile(token)
    except GitHubAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub token verification failed: {exc.message}",
        ) from exc

    github_user_id = str(profile.get("id"))
    github_username = profile.get("login", "unknown")

    # Upsert connection record for user
    stmt = select(UserGitHubAccount).where(UserGitHubAccount.user_id == auth.user_id)
    account = (await db.execute(stmt)).scalar_one_or_none()

    now_utc = datetime.now(timezone.utc)
    if not account:
        account = UserGitHubAccount(
            id=str(uuid.uuid4()),
            user_id=auth.user_id,
            github_user_id=github_user_id,
            github_username=github_username,
            access_token_encrypted=token,
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(account)
    else:
        account.github_user_id = github_user_id
        account.github_username = github_username
        account.access_token_encrypted = token
        account.updated_at = now_utc

    await db.commit()

    return GitHubConnectionStatus(
        connected=True,
        github_username=github_username,
        created_at=account.created_at.isoformat(),
    )


@router.delete("/disconnect", response_model=MessageResponse, summary="Disconnect user's GitHub account")
async def disconnect_github_account(
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Remove stored GitHub token from server."""
    stmt = delete(UserGitHubAccount).where(UserGitHubAccount.user_id == auth.user_id)
    res = await db.execute(stmt)
    await db.commit()

    if res.rowcount == 0:
        return MessageResponse(message="No GitHub account was connected.")

    return MessageResponse(message="GitHub account disconnected successfully.")


@router.get("/repositories", response_model=List[GitHubRepoItem], summary="List authorized user repositories")
async def list_repositories(
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[GitHubRepoItem]:
    """Fetch repositories accessible to the user via GitHub API."""
    token = await _get_user_github_token(auth.user_id, db, optional=True)
    if not token:
        return []
    try:
        repos = await github_service.list_repositories(token)
        return [GitHubRepoItem(**r) for r in repos]
    except GitHubAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/repositories/{owner}/{repo}/branches", response_model=List[GitHubBranchItem], summary="List repository branches")
async def list_repository_branches(
    owner: str,
    repo: str,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[GitHubBranchItem]:
    """List branches for the specified repository."""
    token = await _get_user_github_token(auth.user_id, db)
    try:
        branches = await github_service.list_branches(owner, repo, token)
        return [GitHubBranchItem(**b) for b in branches]
    except GitHubAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/repositories/{owner}/{repo}/tree", response_model=List[GitHubTreeItem], summary="List repository files/directories")
async def get_repository_tree(
    owner: str,
    repo: str,
    ref: str = Query(default="main", description="Branch name or commit SHA"),
    recursive: bool = Query(default=False, description="Whether to recurse tree"),
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[GitHubTreeItem]:
    """Fetch git tree items for branch or commit SHA."""
    token = await _get_user_github_token(auth.user_id, db)
    try:
        tree = await github_service.get_tree(owner, repo, tree_sha=ref, access_token=token, recursive=recursive)
        return [GitHubTreeItem(**item) for item in tree]
    except GitHubAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/review", response_model=ReviewResponse, summary="Trigger AI review of selected GitHub file or commit")
async def review_github_resource(
    payload: ReviewGitHubResourceRequest,
    auth: AuthenticatedContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Fetch file content or commit diff from GitHub, run through review pipeline, and persist in Neon."""
    token = await _get_user_github_token(auth.user_id, db)
    repo_full_name = f"{payload.owner}/{payload.repo}"

    # Verify team authorization if team_id supplied
    if payload.team_id:
        auth.require_team_access(payload.team_id)

    code_diff: str = ""
    target_file: Optional[str] = payload.file_path
    commit_sha: Optional[str] = payload.commit_sha

    try:
        # Case 1: Review a specific commit diff
        if payload.commit_sha:
            diff_text = await github_service.get_commit_diff(
                payload.owner, payload.repo, payload.commit_sha, token
            )
            code_diff = diff_text

        # Case 2: Compare two branches/refs
        elif payload.base and payload.head:
            diff_text = await github_service.get_compare_diff(
                payload.owner, payload.repo, payload.base, payload.head, token
            )
            code_diff = diff_text

        # Case 3: Review a specific single file
        elif payload.file_path:
            ref = payload.ref or "main"
            file_content = await github_service.get_file_content(
                payload.owner, payload.repo, payload.file_path, ref=ref, access_token=token
            )
            # Create synthetic unified diff for single file analysis
            code_diff = f"--- a/{payload.file_path}\n+++ b/{payload.file_path}\n@@ -1,1 +1,{len(file_content.splitlines())} @@\n"
            for line in file_content.splitlines():
                code_diff += f"+{line}\n"

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must specify either 'file_path', 'commit_sha', or ('base' and 'head') to review.",
            )

        if not code_diff.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No diff content found for the specified GitHub resource.",
            )

        # Build ReviewRequest and delegate to existing review_processor pipeline
        req = ReviewRequest(
            code_diff=code_diff,
            user_id=auth.user_id,
            team_id=payload.team_id,
            source="Web",
            repository=repo_full_name,
            commit_sha=commit_sha,
            file_path=target_file,
        )

        return await review_processor.process_review(req, session=db)

    except GitHubAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

