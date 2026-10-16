"""Run Ruff in JSON mode and return parsed, tool-native findings."""

import json
import subprocess
from pathlib import Path
from typing import Any, Sequence


class ToolExecutionError(RuntimeError):
    """A static-analysis tool could not run or returned invalid output."""


def run_ruff(paths: Sequence[str], timeout: float = 30, executable: str = "ruff") -> list[dict[str, Any]]:
    """Run Ruff without a shell. Ruff exit 1 means findings were detected."""
    command = [executable, "check", "--output-format", "json", *map(str, paths)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise ToolExecutionError(f"Ruff executable not found: {executable}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolExecutionError(f"Ruff timed out after {timeout} seconds") from exc
    if completed.returncode not in (0, 1):
        raise ToolExecutionError(f"Ruff failed with exit code {completed.returncode}: {completed.stderr.strip()}")
    try:
        data = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ToolExecutionError("Ruff returned malformed JSON") from exc
    if not isinstance(data, list):
        raise ToolExecutionError("Ruff JSON output must be a list")
    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        location = item.get("location") or {}
        results.append({
            "file_path": str(Path(item.get("filename", "")).as_posix()),
            "line": location.get("row"),
            "rule_id": item.get("code"),
            "message": item.get("message", ""),
            "evidence": item.get("source_code") or item.get("cell"),
        })
    return results
