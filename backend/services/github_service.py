"""GitHub API service for repository tree navigation, commits, and diff fetching.

Adheres to:
- Read-only least-privilege operations
- Graceful rate-limit and status handling
- Secure token delegation per authenticated user
"""
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional
import httpx
from fastapi import HTTPException, status

from backend.core.config import settings
from backend.core.exceptions import AppException


class GitHubAPIError(AppException):
    """Exception raised when GitHub API requests fail."""

    def __init__(self, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message)
        self.status_code = status_code
        self.details = details or {}


class GitHubService:
    """Service wrapping GitHub REST API v3 operations."""

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        self._client = http_client

    def _get_headers(self, access_token: str, media_type: str = "application/vnd.github.v3+json") -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token.strip()}",
            "Accept": media_type,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CodeReviewAgent/0.2.0",
        }

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        params: Optional[Dict[str, Any]] = None,
        media_type: str = "application/vnd.github.v3+json",
    ) -> Any:
        url = f"{settings.github_api_base_url}/{path.lstrip('/')}"
        headers = self._get_headers(access_token, media_type=media_type)

        client = self._client or httpx.AsyncClient(timeout=30.0)
        try:
            resp = await client.request(method, url, headers=headers, params=params)
            
            # Rate limit check
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                raise GitHubAPIError(
                    "GitHub API rate limit exceeded. Please wait or authenticate with a personal GitHub token.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            if resp.status_code == 404:
                raise GitHubAPIError(
                    f"Requested GitHub resource '{path}' not found or repository access denied.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            if resp.status_code >= 400:
                raise GitHubAPIError(
                    f"GitHub API error: {resp.status_code} - {resp.text}",
                    status_code=resp.status_code,
                )

            if media_type == "application/vnd.github.v3.diff":
                return resp.text

            return resp.json()
        except httpx.RequestError as exc:
            raise GitHubAPIError(f"Network error communicating with GitHub: {exc}") from exc
        finally:
            if not self._client:
                await client.aclose()

    async def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """Verify token and return current authenticated GitHub user profile."""
        return await self._request("GET", "/user", access_token)

    async def list_repositories(self, access_token: str, per_page: int = 100) -> List[Dict[str, Any]]:
        """List repositories accessible to the user (owned or collaborator)."""
        repos = await self._request(
            "GET",
            "/user/repos",
            access_token,
            params={"sort": "updated", "per_page": per_page, "affiliation": "owner,collaborator,organization_member"},
        )
        return [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "full_name": r.get("full_name"),
                "owner": r.get("owner", {}).get("login"),
                "default_branch": r.get("default_branch", "main"),
                "private": r.get("private", False),
                "description": r.get("description"),
                "language": r.get("language"),
                "updated_at": r.get("updated_at"),
                "html_url": r.get("html_url"),
            }
            for r in repos
        ]

    async def list_branches(self, owner: str, repo: str, access_token: str) -> List[Dict[str, Any]]:
        """List branches for a given repository."""
        data = await self._request("GET", f"/repos/{owner}/{repo}/branches", access_token)
        return [
            {
                "name": b.get("name"),
                "commit_sha": b.get("commit", {}).get("sha"),
                "protected": b.get("protected", False),
            }
            for b in data
        ]

    async def get_tree(
        self,
        owner: str,
        repo: str,
        tree_sha: str,
        access_token: str,
        recursive: bool = False,
    ) -> List[Dict[str, Any]]:
        """Retrieve repository file tree for branch or commit SHA."""
        params = {"recursive": "1"} if recursive else {}
        data = await self._request("GET", f"/repos/{owner}/{repo}/git/trees/{tree_sha}", access_token, params=params)
        raw_tree = data.get("tree", [])
        return [
            {
                "path": item.get("path"),
                "mode": item.get("mode"),
                "type": item.get("type"),  # "blob" or "tree"
                "sha": item.get("sha"),
                "size": item.get("size"),
            }
            for item in raw_tree
        ]

    async def get_file_content(self, owner: str, repo: str, file_path: str, ref: str, access_token: str) -> str:
        """Fetch raw content of a specific file at a branch/commit."""
        data = await self._request("GET", f"/repos/{owner}/{repo}/contents/{file_path.lstrip('/')}", access_token, params={"ref": ref})
        encoding = data.get("encoding")
        content = data.get("content", "")
        if encoding == "base64":
            return base64.b64decode(content).decode("utf-8", errors="replace")
        return content

    async def get_commit_diff(self, owner: str, repo: str, commit_sha: str, access_token: str) -> str:
        """Fetch raw git diff of a specific commit."""
        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}/commits/{commit_sha}",
            access_token,
            media_type="application/vnd.github.v3.diff",
        )

    async def get_compare_diff(self, owner: str, repo: str, base: str, head: str, access_token: str) -> str:
        """Fetch unified diff comparing two branches or commits."""
        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}/compare/{base}...{head}",
            access_token,
            media_type="application/vnd.github.v3.diff",
        )

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        access_token: str,
        state: str = "open",
        per_page: int = 50,
    ) -> List[Dict[str, Any]]:
        """List pull requests for a repository."""
        data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            access_token,
            params={"state": state, "per_page": per_page, "sort": "updated", "direction": "desc"},
        )
        return data

    async def get_pull_request(self, owner: str, repo: str, pr_number: int, access_token: str) -> Dict[str, Any]:
        """Fetch pull request metadata."""
        return await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}", access_token)

    async def get_pull_request_diff(self, owner: str, repo: str, pr_number: int, access_token: str) -> str:
        """Fetch raw unified diff of a pull request."""
        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            access_token,
            media_type="application/vnd.github.v3.diff",
        )

    async def get_pull_request_files(self, owner: str, repo: str, pr_number: int, access_token: str) -> List[Dict[str, Any]]:
        """Fetch changed files list in a pull request."""
        data = await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/files", access_token)
        return [
            {
                "filename": f.get("filename"),
                "status": f.get("status"),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "changes": f.get("changes", 0),
                "patch": f.get("patch"),
            }
            for f in data
        ]


github_service = GitHubService()

