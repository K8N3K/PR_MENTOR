"""Convert static-analysis output to the shared Finding schema.

Ruff has no severity rating, so its findings use medium. Bandit HIGH, MEDIUM,
and LOW map directly; unknown values also map to medium. This is a priority
mapping only: every result remains tool_flagged until separately reproduced.
"""

from typing import Any, Iterable

from app.schemas.finding import Finding


def _severity(value: Any) -> str:
    normalized = str(value or "").lower()
    return normalized if normalized in {"info", "low", "medium", "high", "critical"} else "medium"


def normalize_ruff(results: Iterable[dict[str, Any]]) -> list[Finding]:
    return [Finding(
        file_path=str(result.get("file_path", "")),
        line=result.get("line"),
        rule_id=result.get("rule_id"),
        severity="medium",
        message=str(result.get("message", "")),
        source="ruff",
        evidence=result.get("evidence"),
        verification_status="tool_flagged",
    ) for result in results]


def normalize_bandit(results: Iterable[dict[str, Any]]) -> list[Finding]:
    return [Finding(
        file_path=str(result.get("file_path", "")),
        line=result.get("line"),
        rule_id=result.get("rule_id"),
        severity=_severity(result.get("severity")),
        message=str(result.get("message", "")),
        source="bandit",
        evidence=result.get("evidence"),
        verification_status="tool_flagged",
    ) for result in results]
