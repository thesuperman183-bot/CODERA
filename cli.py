"""CLI client for a running Code Review Agent FastAPI server."""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

import httpx


def _post(base_url: str, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
    try:
        timeout = float(os.getenv("REVIEW_AGENT_TIMEOUT_SECONDS", "30"))
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        response = httpx.post(
            base_url.rstrip("/") + endpoint,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("API returned an invalid response")
    return result


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


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="review-agent")
    parser.add_argument(
        "--api-url",
        default=os.getenv("REVIEW_AGENT_API_URL", "http://127.0.0.1:8000"),
        help="FastAPI base URL",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="review a file or stdin diff")
    check.add_argument("file_or_diff", help="UTF-8 file path, or - to read stdin")
    learn = commands.add_parser("learn", help="save a review rule")
    learn.add_argument("rule_text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        if args.command == "check":
            response = _post(
                args.api_url,
                "/api/review",
                {"code_diff": _read_input(args.file_or_diff)},
            )
            review = response.get("review")
            if not isinstance(review, str):
                raise RuntimeError("API returned an invalid review")
            print(review)
        else:
            response = _post(
                args.api_url,
                "/api/retain",
                {"rule": args.rule_text, "tags": []},
            )
            print(json.dumps(response, ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
