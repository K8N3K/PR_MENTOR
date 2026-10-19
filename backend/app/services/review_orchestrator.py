"""Coordinate the AI review engine with the shared PR-ingestion payload."""

from collections.abc import Mapping

from app.ai_review.client import AIProvider
from app.ai_review.reviewer import review_pull_request_payload
from app.schemas.finding import Finding


def run_ai_review(
    pull_request_payload: Mapping[str, object],
    *,
    provider: AIProvider | None = None,
) -> list[Finding]:
    """Run the AI review against an ingestion payload and return shared findings.

    Member 1's ingestion layer can pass its payload directly. The reviewer
    extracts reviewable patches and rejects truncated payloads,
    validates model output, and marks each finding as an unverified AI
    suggestion. Ruff/Bandit findings remain the responsibility of the
    verification pipeline and are not changed here.
    """
    return review_pull_request_payload(pull_request_payload, provider=provider)


def run_review(
    pull_request_payload: Mapping[str, object],
    *,
    provider: AIProvider | None = None,
) -> dict[str, object]:
    """Return a completed review in the frontend's existing response shape."""
    pull_request = pull_request_payload.get("pull_request")
    if not isinstance(pull_request, Mapping):
        raise TypeError("The payload must contain pull_request metadata.")

    owner = pull_request.get("owner")
    repo = pull_request.get("repo")
    title = pull_request.get("title")
    number = pull_request.get("number")
    url = pull_request.get("html_url")
    if not all(isinstance(value, str) and value.strip() for value in (owner, repo, title, url)):
        raise ValueError("The pull request metadata is incomplete.")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError("The pull request number must be a positive integer.")

    findings = run_ai_review(pull_request_payload, provider=provider)
    severity_labels = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
        "info": "Informational",
    }
    api_findings = []
    for finding in findings:
        explanation = finding.explanation or finding.message
        if finding.suggested_fix:
            explanation = f"{explanation}\n\nSuggested improvement: {finding.suggested_fix}"
        api_findings.append(
            {
                "severity": severity_labels[finding.severity],
                "title": finding.message,
                "file": finding.file_path,
                "line": finding.line if finding.line is not None else "Not located in diff",
                "text": explanation,
                "proof": finding.evidence,
                "status": "unverified AI suggestion",
            }
        )

    return {
        "repository": f"{owner}/{repo}",
        "pull_request_title": title,
        "pull_request_number": number,
        "url": url,
        "findings": api_findings,
        "status": "completed",
    }
