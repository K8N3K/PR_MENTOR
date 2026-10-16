"""Run Bandit in JSON mode and return parsed, tool-native findings."""

import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

from .ruff_runner import ToolExecutionError


def run_bandit(paths: Sequence[str], timeout: float = 30, executable: str = "bandit") -> list[dict[str, Any]]:
    """Run Bandit without a shell. Exit 1 is a normal findings result."""
    command = [executable, "-f", "json", *map(str, paths)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise ToolExecutionError(f"Bandit executable not found: {executable}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolExecutionError(f"Bandit timed out after {timeout} seconds") from exc
    if completed.returncode not in (0, 1):
        raise ToolExecutionError(f"Bandit failed with exit code {completed.returncode}: {completed.stderr.strip()}")
    try:
        data = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ToolExecutionError("Bandit returned malformed JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ToolExecutionError("Bandit JSON output must contain a results list")
    results = []
    for item in data["results"]:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        if isinstance(code, str):
            evidence = code.rstrip("\r\n") or None
        elif isinstance(code, list):
            evidence = "\n".join(line for line in code if isinstance(line, str)).rstrip("\r\n") or None
        else:
            evidence = None
        results.append({
            "file_path": str(Path(item.get("filename", "")).as_posix()),
            "line": item.get("line_number"),
            "rule_id": item.get("test_id"),
            "message": item.get("issue_text", ""),
            "severity": item.get("issue_severity"),
            "evidence": evidence,
        })
    return results
