"""Parser for extracting structured review findings from LLM review text."""
from __future__ import annotations

import re
from typing import List
from backend.schemas import FindingItem


SEVERITY_PATTERN = re.compile(r"\[?(CRITICAL|HIGH|MEDIUM|LOW|INFO)\]?", re.IGNORECASE)
FILE_LINE_PATTERN = re.compile(
    r"(?:file|location|path|in)?\s*[:`]?\s*([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9_]+)(?::(\d+))?",
    re.IGNORECASE,
)


def parse_review_findings(review_text: str) -> List[FindingItem]:
    """Parse actionable findings from LLM markdown review output."""
    findings: List[FindingItem] = []
    lines = review_text.splitlines()

    current_title = ""
    current_desc: List[str] = []
    current_severity = "medium"
    current_file = None
    current_line = None
    current_rec = None

    def flush_finding():
        nonlocal current_title, current_desc, current_severity, current_file, current_line, current_rec
        if current_title:
            desc_text = " ".join(current_desc).strip() or current_title
            findings.append(
                FindingItem(
                    title=current_title[:250],
                    description=desc_text,
                    severity=current_severity.lower(),
                    file_path=current_file,
                    line_number=current_line,
                    recommendation=current_rec,
                )
            )
        current_title = ""
        current_desc = []
        current_severity = "medium"
        current_file = None
        current_line = None
        current_rec = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # Look for headers or bullet list items introducing an issue
        is_heading_or_bullet = (
            line.startswith(("#", "-", "*", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."))
        )

        sev_match = SEVERITY_PATTERN.search(line)
        if is_heading_or_bullet and (sev_match or any(k in line.lower() for k in ["bug", "issue", "vulnerability", "risk", "security", "warning", "fix", "error"])):
            flush_finding()
            
            if sev_match:
                current_severity = sev_match.group(1).lower()

            # Clean line for title
            cleaned = re.sub(r"^([#\-\*\d\.]+\s*)", "", line)
            cleaned = re.sub(r"\[?(CRITICAL|HIGH|MEDIUM|LOW|INFO)\]?[:\s\-]*", "", cleaned, flags=re.IGNORECASE).strip()
            # Remove markdown bolding
            cleaned = cleaned.replace("**", "").replace("__", "")
            current_title = cleaned[:100]

            # Try to extract file and line number
            fl_match = FILE_LINE_PATTERN.search(line)
            if fl_match:
                current_file = fl_match.group(1)
                if fl_match.group(2):
                    try:
                        current_line = int(fl_match.group(2))
                    except ValueError:
                        pass
        elif current_title:
            if any(line.lower().startswith(p) for p in ["recommendation:", "suggestion:", "fix:"]):
                current_rec = re.sub(r"^(recommendation|suggestion|fix):\s*", "", line, flags=re.IGNORECASE).strip()
            else:
                current_desc.append(line)

    flush_finding()

    # If no structured findings were detected, extract at least one summary finding if review contains content
    if not findings and review_text.strip():
        first_line = next((l.strip("#-* ") for l in review_text.splitlines() if l.strip()), "General Review Feedback")
        findings.append(
            FindingItem(
                title=first_line[:100],
                description=review_text[:500],
                severity="info",
                recommendation=None,
            )
        )

    return findings

