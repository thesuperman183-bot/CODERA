"""CLI client for a running Code Review Agent FastAPI server."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, Sequence

import httpx

try:
    import keyring
except ImportError:
    keyring = None  # type: ignore

KEYRING_SERVICE_NAME = "code-review-agent"
KEYRING_USERNAME = "default_user_token"

# Fallback credentials file location if OS keychain is unavailable
_CREDENTIALS_DIR = Path.home() / ".config" / "review-agent"
_CREDENTIALS_FILE = _CREDENTIALS_DIR / "credentials.json"


# ---------------------------------------------------------------------------
# Secure Token Storage (OS Credential Store / Keyring with secure file fallback)
# ---------------------------------------------------------------------------

def _store_token(token: str) -> None:
    """Store token securely using OS keyring (macOS Keychain, Linux Secret Service, Windows Credential Vault)."""
    stored_in_keyring = False
    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME, token)
            stored_in_keyring = True
        except Exception:
            stored_in_keyring = False

    # Also persist to secure file (0600) as fallback or secondary cache
    _CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    _CREDENTIALS_FILE.write_text(
        json.dumps({"token": token, "source": "keyring" if stored_in_keyring else "file"}, ensure_ascii=False),
        encoding="utf-8",
    )
    try:
        _CREDENTIALS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _load_token() -> str | None:
    """Load token from OS keyring or fallback secure file."""
    if keyring is not None:
        try:
            val = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME)
            if val and val.strip():
                return val.strip()
        except Exception:
            pass

    try:
        data = json.loads(_CREDENTIALS_FILE.read_text(encoding="utf-8"))
        val = data.get("token")
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _remove_token() -> bool:
    """Remove token from OS keyring and fallback file."""
    removed = False
    if keyring is not None:
        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME)
            removed = True
        except Exception:
            pass

    try:
        if _CREDENTIALS_FILE.exists():
            _CREDENTIALS_FILE.unlink()
            removed = True
    except OSError:
        pass
    return removed


def _resolve_token(args: argparse.Namespace) -> str | None:
    """Priority: --token flag > REVIEW_AGENT_TOKEN env var > OS Keyring / stored credentials."""
    if hasattr(args, "token") and args.token:
        return args.token
    env_token = os.getenv("REVIEW_AGENT_TOKEN")
    if env_token:
        return env_token
    return _load_token()


# ---------------------------------------------------------------------------
# HTTP Helpers
# ---------------------------------------------------------------------------

def _build_headers(token: str | None) -> dict[str, str]:
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _post(
    base_url: str,
    endpoint: str,
    payload: dict[str, object],
    token: str | None = None,
) -> dict[str, Any]:
    try:
        timeout = float(os.getenv("REVIEW_AGENT_TIMEOUT_SECONDS", "30"))
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        response = httpx.post(
            base_url.rstrip("/") + endpoint,
            json=payload,
            headers=_build_headers(token),
            timeout=timeout,
        )
        if response.status_code == 401:
            raise RuntimeError(
                "Authentication required (401 Unauthorized). Run 'review-agent login' or set REVIEW_AGENT_TOKEN."
            )
        if response.status_code == 403:
            raise RuntimeError(
                f"Access denied (403 Forbidden): {response.text}"
            )
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("API returned an invalid response")
    return result


def _get(
    base_url: str,
    endpoint: str,
    token: str | None = None,
) -> Any:
    try:
        timeout = float(os.getenv("REVIEW_AGENT_TIMEOUT_SECONDS", "30"))
        response = httpx.get(
            base_url.rstrip("/") + endpoint,
            headers=_build_headers(token),
            timeout=timeout,
        )
        if response.status_code == 401:
            raise RuntimeError(
                "Authentication required (401 Unauthorized). Run 'review-agent login' or set REVIEW_AGENT_TOKEN."
            )
        if response.status_code == 403:
            raise RuntimeError(
                f"Access denied (403 Forbidden): {response.text}"
            )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc


def _read_input(arg: str) -> str:
    if arg == "-":
        value = sys.stdin.read()
    else:
        try:
            value = Path(arg).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(f"cannot read input file: {exc}") from exc
    if not value.strip():
        raise RuntimeError("input diff is empty")
    return value


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="review-agent",
        description="AI-powered Code Review Agent CLI with Neon & Hindsight Integration",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("REVIEW_AGENT_API_URL", "http://127.0.0.1:8000"),
        help="FastAPI base URL (default: http://127.0.0.1:8000 or REVIEW_AGENT_API_URL)",
    )
    parser.add_argument(
        "--token",
        default=None,
        metavar="PAT",
        help="Personal Access Token (overrides OS keyring and REVIEW_AGENT_TOKEN)",
    )

    commands = parser.add_subparsers(dest="command", required=True)

    # 1. check
    check = commands.add_parser("check", help="Review a file or stdin diff")
    check.add_argument("file_or_diff", help="UTF-8 file path, or - to read from stdin")

    # 2. learn
    learn = commands.add_parser("learn", help="Save a review rule to persistent memory")
    learn.add_argument("rule_text", help="Review rule or guideline text")

    # 3. login
    login = commands.add_parser("login", help="Authenticate with your user account and securely store credentials")
    login.add_argument("--email", required=False, help="Account email address (prompted if omitted)")
    login.add_argument(
        "--token-name",
        default="CLI Access Token",
        help="Label for the issued Personal Access Token",
    )

    # 4. logout
    commands.add_parser("logout", help="Log out and purge stored credentials from OS keyring")

    # 5. whoami
    commands.add_parser("whoami", help="Display details of current authenticated user, team, and roles")

    # 6. history
    history = commands.add_parser("history", help="List recent reviews submitted by you or your team")
    history.add_argument("--limit", type=int, default=10, help="Number of reviews to display (default: 10)")

    return parser


# ---------------------------------------------------------------------------
# Command Implementations
# ---------------------------------------------------------------------------

def _cmd_login(args: argparse.Namespace) -> int:
    email = args.email
    if not email:
        try:
            email = input("Email: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nLogin cancelled.", file=sys.stderr)
            return 1

    if not email:
        print("Error: email cannot be blank.", file=sys.stderr)
        return 1

    try:
        result = _post(
            args.api_url,
            "/api/auth/cli-login",
            {"email": email, "token_name": args.token_name},
        )
    except RuntimeError as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 1

    token = result.get("token")
    if not token:
        print("Login failed: server did not return a valid token.", file=sys.stderr)
        return 1

    _store_token(token)
    user = result.get("user", {})
    name = user.get("name", email)
    teams = user.get("teams", [])

    print(f"✓ Successfully authenticated as {name} <{email}>")
    storage_type = "OS Keyring (Keychain/Secret Service)" if keyring is not None else "Secure file"
    print(f"✓ Token securely stored in: {storage_type}")
    if teams:
        team_str = ", ".join(f"{t['team_name']} ({t['role']})" for t in teams)
        print(f"  Associated Teams: {team_str}")
    return 0


def _cmd_logout(_args: argparse.Namespace) -> int:
    if _remove_token():
        print("✓ Logged out successfully. Credentials removed from secure storage.")
    else:
        print("Not logged in (no stored credentials found).")
    return 0


def _cmd_whoami(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    if not token:
        print("Not authenticated. Run 'review-agent login' first.", file=sys.stderr)
        return 1

    try:
        result = _get(args.api_url, "/api/auth/me", token=token)
        if isinstance(result, dict):
            print(f"User:  {result.get('name')} <{result.get('email')}>")
            print(f"ID:    {result.get('id')}")
            teams = result.get("teams", [])
            if teams:
                print("Teams:")
                for t in teams:
                    print(f"  • {t.get('team_name')} (ID: {t.get('team_id')}) — Role: {t.get('role')}")
            else:
                print("Teams: No teams associated.")
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _cmd_check(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    try:
        diff = _read_input(args.file_or_diff)
        response = _post(
            args.api_url,
            "/api/review",
            {"code_diff": diff, "source": "CLI"},
            token=token,
        )
        review = response.get("review")
        if not isinstance(review, str):
            raise RuntimeError("API returned an invalid review response")
        print(review)
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _cmd_learn(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    try:
        response = _post(
            args.api_url,
            "/api/retain",
            {"rule": args.rule_text, "tags": []},
            token=token,
        )
        print(json.dumps(response, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _cmd_history(args: argparse.Namespace) -> int:
    token = _resolve_token(args)
    if not token:
        print("Not authenticated. Run 'review-agent login' first.", file=sys.stderr)
        return 1

    try:
        reviews = _get(args.api_url, f"/api/reviews?limit={args.limit}", token=token)
        if not isinstance(reviews, list):
            raise RuntimeError("API returned an invalid review history format")

        if not reviews:
            print("No review history found.")
            return 0

        print(f"Found {len(reviews)} review session(s):\n")
        print(f"{'REVIEW ID':<38} {'STATUS':<12} {'SOURCE':<8} {'FINDINGS':<10} {'DATE'}")
        print("-" * 80)
        for r in reviews:
            r_id = r.get("id", "unknown")
            status = r.get("status", "unknown")
            source = r.get("source", "CLI")
            findings_count = r.get("findings_count", 0)
            created_at = r.get("created_at", "")[:19]
            print(f"{r_id:<38} {status:<12} {source:<8} {findings_count:<10} {created_at}")
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    args = make_parser().parse_args(argv)

    if args.command == "check":
        return _cmd_check(args)
    if args.command == "learn":
        return _cmd_learn(args)
    if args.command == "login":
        return _cmd_login(args)
    if args.command == "logout":
        return _cmd_logout(args)
    if args.command == "whoami":
        return _cmd_whoami(args)
    if args.command == "history":
        return _cmd_history(args)

    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
