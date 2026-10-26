"""The fast check runner executes fixture code and retains observable results."""
import json
import os
import sys

import pytest

from check_commands import run_command
from lib.verification import run_command as process_command


@pytest.mark.parametrize("source", [
    "print('checked')",
    "import sys; print('error', file=sys.stderr); raise SystemExit(7)",
    "assert False, 'fixture defect'",
    "raise SystemExit('fixture unavailable')",
])
def test_fixture_check_agrees_with_python_process(tmp_path, source):
    command = [sys.executable, "-B", "-c", source]
    expected = process_command(command, tmp_path, 10)
    actual = run_command(command, tmp_path, 10)
    for field in ("command", "cwd", "exit_code", "stdout", "outcome"):
        assert actual[field] == expected[field]
    assert actual["stderr"].splitlines()[-1:] == expected["stderr"].splitlines()[-1:]


def test_fixture_check_preserves_arguments_files_and_host_context(tmp_path):
    script = tmp_path / "check arguments.py"
    script.write_text("import json, sys\nfrom pathlib import Path\n"
                      "Path('result.txt').write_text('ran')\nprint(json.dumps(sys.argv[1:]))\n")
    command = [sys.executable, "-B", script.name, "two words", "", "$(literal)"]
    previous = os.getcwd(), sys.argv[:]
    expected = process_command(command, tmp_path, 10)
    (tmp_path / "result.txt").unlink()
    actual = run_command(command, tmp_path, 10)
    assert actual["stdout"] == expected["stdout"]
    assert json.loads(actual["stdout"]) == command[3:]
    assert (tmp_path / "result.txt").read_text() == "ran"
    assert (os.getcwd(), sys.argv) == previous


def test_fixture_check_rejects_unsupported_runner(tmp_path):
    with pytest.raises(AssertionError, match="native_process"):
        run_command(["another-runner"], tmp_path, 10)
