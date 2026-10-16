import json
import subprocess
from unittest.mock import patch

import pytest

from app.schemas.finding import Finding
from app.verification.bandit_runner import run_bandit
from app.verification.normalizer import normalize_bandit, normalize_ruff
from app.verification.ruff_runner import ToolExecutionError, run_ruff
from app.verification.test_runner import run_tests


def completed(stdout, returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_ruff_json_parsing_and_findings_exit_code():
    payload = [{"filename": "src/a.py", "location": {"row": 7, "column": 2}, "code": "F401", "message": "unused import", "source_code": "import os"}]
    with patch("app.verification.ruff_runner.subprocess.run", return_value=completed(json.dumps(payload), 1)) as call:
        result = run_ruff(["src/a.py"])
    assert result == [{"file_path": "src/a.py", "line": 7, "rule_id": "F401", "message": "unused import", "evidence": "import os"}]
    assert call.call_args.args[0][:4] == ["ruff", "check", "--output-format", "json"]
    assert call.call_args.kwargs["shell"] is not True if "shell" in call.call_args.kwargs else True


def test_bandit_json_parsing_and_findings_exit_code():
    payload = {"results": [{"filename": "src/a.py", "line_number": 9, "test_id": "B602", "issue_severity": "HIGH", "issue_text": "subprocess call", "code": "  eval(input())\n"}]}
    with patch("app.verification.bandit_runner.subprocess.run", return_value=completed(json.dumps(payload), 1)):
        assert run_bandit(["src/a.py"]) == [{"file_path": "src/a.py", "line": 9, "rule_id": "B602", "message": "subprocess call", "severity": "HIGH", "evidence": "  eval(input())"}]


def test_normalizers_use_shared_schema_and_preserve_provenance():
    ruff = normalize_ruff([{"file_path": "a.py", "line": 2, "rule_id": "F401", "message": "unused", "evidence": "import os"}])[0]
    bandit = normalize_bandit([{"file_path": "b.py", "line": 3, "rule_id": "B101", "message": "assert", "severity": "LOW", "evidence": "assert True"}])[0]
    assert isinstance(ruff, Finding) and ruff.source == "ruff" and ruff.severity == "medium"
    assert ruff.evidence == "import os" and ruff.verification_status == "tool_flagged"
    assert bandit.source == "bandit" and bandit.severity == "low" and bandit.rule_id == "B101"
    assert bandit.evidence == "assert True" and bandit.verification_status == "tool_flagged"


@pytest.mark.parametrize("module,func", [("app.verification.ruff_runner", run_ruff), ("app.verification.bandit_runner", run_bandit)])
def test_missing_executable(module, func):
    with patch(f"{module}.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(ToolExecutionError, match="not found"):
            func(["a.py"])


@pytest.mark.parametrize("module,func", [("app.verification.ruff_runner", run_ruff), ("app.verification.bandit_runner", run_bandit)])
def test_timeout(module, func):
    with patch(f"{module}.subprocess.run", side_effect=subprocess.TimeoutExpired("tool", 1)):
        with pytest.raises(ToolExecutionError, match="timed out"):
            func(["a.py"], timeout=1)


@pytest.mark.parametrize("module,func", [("app.verification.ruff_runner", run_ruff), ("app.verification.bandit_runner", run_bandit)])
def test_malformed_json(module, func):
    with patch(f"{module}.subprocess.run", return_value=completed("not json")):
        with pytest.raises(ToolExecutionError, match="malformed JSON"):
            func(["a.py"])


def test_invalid_tool_exit_code_is_execution_error():
    with patch("app.verification.ruff_runner.subprocess.run", return_value=completed("[]", 2, "bad args")):
        with pytest.raises(ToolExecutionError, match="exit code 2"):
            run_ruff(["a.py"])


def test_test_runner_never_executes_supplied_target_or_command():
    with patch("subprocess.run") as run:
        result = run_tests(target="untrusted/path", command="malicious command")
    run.assert_not_called()
    assert result["status"] == "unavailable"
    assert result["executed"] is False
    assert "isolated" in result["message"]

@pytest.mark.parametrize("module,func,stdout", [
    ("app.verification.ruff_runner", run_ruff, "{}"),
    ("app.verification.bandit_runner", run_bandit, '{"results": {}}'),
])
def test_invalid_json_structure_is_reported(module, func, stdout):
    with patch(f"{module}.subprocess.run", return_value=completed(stdout)):
        with pytest.raises(ToolExecutionError):
            func(["a.py"])


def test_ruff_skips_non_objects_and_sanitizes_malformed_fields():
    payload = [None, {
        "filename": 42,
        "location": ["bad"],
        "code": 17,
        "message": {"bad": "type"},
        "source_code": ["not", "text"],
    }, {
        "filename": "src\\nested\\a.py",
        "location": {"row": "8"},
        "code": "F401",
        "message": "unused",
        "cell": "  import os",
    }]
    with patch("app.verification.ruff_runner.subprocess.run", return_value=completed(json.dumps(payload))):
        result = run_ruff(["a.py"])
    assert result == [
        {"file_path": "", "line": None, "rule_id": None, "message": "", "evidence": None},
        {"file_path": "src/nested/a.py", "line": None, "rule_id": "F401", "message": "unused", "evidence": "  import os"},
    ]


def test_bandit_sanitizes_malformed_fields_and_code_formats():
    payload = {"results": [
        None,
        {"filename": "src\\bad.py", "line_number": True, "test_id": [], "issue_severity": {}, "issue_text": 3, "code": 5},
        {"filename": "src\\lines.py", "line_number": 4, "test_id": "B101", "issue_severity": "LOW", "issue_text": "assert", "code": ["  first\n", None, "second\r\n"]},
        {"filename": "src\\missing.py", "code": None},
    ]}
    with patch("app.verification.bandit_runner.subprocess.run", return_value=completed(json.dumps(payload))):
        result = run_bandit(["a.py"])
    assert result == [
        {"file_path": "src/bad.py", "line": None, "rule_id": None, "message": "", "severity": None, "evidence": None},
        {"file_path": "src/lines.py", "line": 4, "rule_id": "B101", "message": "assert", "severity": "LOW", "evidence": "  first\nsecond"},
        {"file_path": "src/missing.py", "line": None, "rule_id": None, "message": "", "severity": None, "evidence": None},
    ]


def test_normalizers_sanitize_malformed_records_into_valid_findings():
    for findings in (
        normalize_ruff([None, {"file_path": [], "line": True, "rule_id": {}, "message": None, "evidence": 4}]),
        normalize_bandit([None, {"file_path": None, "line": "4", "rule_id": [], "severity": [], "message": {}, "evidence": {}}]),
    ):
        assert all(isinstance(finding, Finding) for finding in findings)
        assert findings[0].file_path == ""
        assert findings[0].line is None
        assert findings[0].rule_id is None
        assert findings[0].message == ""
        assert findings[0].evidence is None
        assert findings[0].verification_status == "tool_flagged"


def test_normalizers_accept_non_iterable_input_safely():
    assert normalize_ruff(None) == []
    assert normalize_bandit(None) == []


def test_bandit_invalid_exit_code_is_execution_error():
    with patch("app.verification.bandit_runner.subprocess.run", return_value=completed("{}", 2, "bad args")):
        with pytest.raises(ToolExecutionError, match="exit code 2"):
            run_bandit(["a.py"])
