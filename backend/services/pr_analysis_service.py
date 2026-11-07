"""Pull Request Intelligence and recommendation analysis service.

Evaluates PRs based on:
- Technology stack, framework, and language match
- Security impact and risk level
- Test coverage changes
- Team coding rules and Hindsight memory alignment
- Explanatory recommendation ranking
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# Language extensions mapping
EXT_TO_LANGUAGE = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".rb": "Ruby",
    ".php": "PHP",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".sh": "Shell",
}


def detect_pr_languages(files: List[Dict[str, Any]]) -> List[str]:
    """Identify languages modified in the PR."""
    languages = set()
    for f in files:
        name = f.get("filename", "")
        for ext, lang in EXT_TO_LANGUAGE.items():
            if name.endswith(ext):
                languages.add(lang)
    return sorted(list(languages))


def detect_test_coverage_presence(files: List[Dict[str, Any]]) -> bool:
    """Check if test files are added or modified in the pull request."""
    for f in files:
        name = f.get("filename", "").lower()
        if "test" in name or "spec" in name or "__tests__" in name:
            return True
    return False


def score_pr_recommendation(
    pr: Dict[str, Any],
    files: List[Dict[str, Any]],
    team_rules: List[str],
    language_filter: Optional[str] = None,
    framework_filter: Optional[str] = None,
) -> Tuple[int, List[str]]:
    """Rank a Pull Request with explicit human-readable reasons."""
    reasons: List[str] = []
    score = 50  # Base neutral score

    title = pr.get("title", "").lower()
    body = (pr.get("body") or "").lower()
    pr_languages = detect_pr_languages(files)
    has_tests = detect_test_coverage_presence(files)

    # 1. Security / Critical Keywords
    security_terms = ["auth", "security", "token", "password", "crypto", "sql", "injection", "cors", "jwt", "key"]
    matched_security = [term for term in security_terms if term in title or term in body]
    if matched_security:
        score += 25
        reasons.append(f"Contains security-sensitive changes touching {', '.join(matched_security)}")

    # 2. Bugfix / Production Hotfix urgency
    if any(k in title for k in ["fix", "bug", "patch", "hotfix", "issue"]):
        score += 15
        reasons.append("Addresses a bug or defect resolution")

    # 3. Test Coverage evaluation
    if not has_tests:
        score += 10  # higher review priority because test coverage is missing
        reasons.append("Missing test updates — requires manual verification of test coverage")
    else:
        reasons.append("Includes dedicated automated test coverage")

    # 4. Scope & Size evaluation
    total_changes = pr.get("additions", 0) + pr.get("deletions", 0)
    if total_changes > 500:
        score += 15
        reasons.append(f"Large changeset ({total_changes} lines across {len(files)} files) requiring careful architectural review")
    elif total_changes < 50:
        reasons.append("Focused atomic changeset")

    # 5. Language and Framework Filtering
    if language_filter:
        if language_filter.lower() in [l.lower() for l in pr_languages]:
            score += 20
            reasons.append(f"Matches requested target language: {language_filter}")
        else:
            score -= 30

    if framework_filter:
        if framework_filter.lower() in title or framework_filter.lower() in body:
            score += 20
            reasons.append(f"Matches requested framework context: {framework_filter}")

    # 6. Team Rules Alignment
    matched_rules = 0
    for rule in team_rules:
        # Check rule keywords in title or diff
        rule_words = set(re.findall(r"\w{4,}", rule.lower()))
        if any(w in title or w in body for w in rule_words):
            matched_rules += 1

    if matched_rules > 0:
        score += 10 * min(matched_rules, 3)
        reasons.append(f"Directly intersects with {matched_rules} organizational coding standard(s)")

    return max(0, min(100, score)), reasons


class PRAnalysisService:
    """Analyzes and ranks PRs for engineering quality, correctness, and review suitability."""

    def analyze_and_rank_pull_requests(
        self,
        pull_requests: List[Dict[str, Any]],
        files_by_pr: Dict[int, List[Dict[str, Any]]],
        team_rules: List[str],
        language_filter: Optional[str] = None,
        framework_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Rank pull requests with clear explanation reasons."""
        ranked_prs = []

        for pr in pull_requests:
            pr_num = pr.get("number")
            pr_files = files_by_pr.get(pr_num, [])
            languages = detect_pr_languages(pr_files)
            has_tests = detect_test_coverage_presence(pr_files)
            score, reasons = score_pr_recommendation(
                pr=pr,
                files=pr_files,
                team_rules=team_rules,
                language_filter=language_filter,
                framework_filter=framework_filter,
            )

            # Determine recommendation priority label
            if score >= 75:
                recommendation_priority = "high"
            elif score >= 50:
                recommendation_priority = "medium"
            else:
                recommendation_priority = "low"

            ranked_prs.append(
                {
                    "number": pr_num,
                    "title": pr.get("title"),
                    "author": pr.get("user", {}).get("login"),
                    "author_avatar": pr.get("user", {}).get("avatar_url"),
                    "state": pr.get("state"),
                    "html_url": pr.get("html_url"),
                    "base_branch": pr.get("base", {}).get("ref"),
                    "head_branch": pr.get("head", {}).get("ref"),
                    "head_sha": pr.get("head", {}).get("sha"),
                    "created_at": pr.get("created_at"),
                    "updated_at": pr.get("updated_at"),
                    "additions": pr.get("additions", 0),
                    "deletions": pr.get("deletions", 0),
                    "changed_files_count": len(pr_files),
                    "languages": languages,
                    "has_tests": has_tests,
                    "recommendation_score": score,
                    "recommendation_priority": recommendation_priority,
                    "recommendation_reasons": reasons,
                }
            )

        # Sort by recommendation priority score descending
        ranked_prs.sort(key=lambda x: x["recommendation_score"], reverse=True)
        return ranked_prs


pr_analysis_service = PRAnalysisService()

