from typing import Literal, Optional

from pydantic import BaseModel


class Finding(BaseModel):
    """Shared representation of an AI or tool-reported code finding."""

    file_path: str
    line: Optional[int] = None
    rule_id: Optional[str] = None
    severity: Literal["info", "low", "medium", "high", "critical"]
    message: str
    source: Literal["ruff", "bandit", "test", "ai"]
    evidence: Optional[str] = None
    verification_status: Literal["tool_flagged", "reproduced", "unverified"] = "tool_flagged"
    explanation: Optional[str] = None
    suggested_fix: Optional[str] = None
