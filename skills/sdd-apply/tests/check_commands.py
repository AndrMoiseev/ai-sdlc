"""Execute fixture Python checks in process; process contracts use the real runner.

This is deliberately limited to Python -B scripts and -c snippets. Unsupported
commands fail the test instead of silently simulating success. Checks still run
their assertions and can change the working files inspected by the engine.
"""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
import sys
import time
import traceback

from lib.common import now


def run_command(command, cwd, timeout):
    assert command[:2] == [sys.executable, "-B"], "Use native_process for non-fixture commands"
    assert timeout >= 10, "Use native_process for timeout behavior"
    args = command[2:]
    inline = args[0] == "-c"
    filename = "<string>" if inline else str(Path(cwd, args[0]))
    source = args[1] if inline else Path(filename).read_bytes()
    previous_cwd, previous_argv = os.getcwd(), sys.argv
    stdout, stderr = StringIO(newline=os.linesep), StringIO(newline=os.linesep)
    started, stamp, code = time.monotonic(), now(), 0
    try:
        os.chdir(cwd)
        sys.argv = ["-c", *args[2:]] if inline else args
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                exec(compile(source, filename, "exec"), {"__name__": "__main__", "__file__": filename})
            except SystemExit as error:
                code = error.code or 0
                if not isinstance(code, int):
                    print(code, file=sys.stderr)
                    code = 1
            except Exception:
                traceback.print_exc()
                code = 1
    finally:
        os.chdir(previous_cwd)
        sys.argv = previous_argv
    return dict(command=command, cwd=str(cwd), started_at=stamp,
                duration_seconds=time.monotonic() - started, exit_code=code,
                stdout=stdout.getvalue(), stderr=stderr.getvalue(),
                outcome="passed" if code == 0 else "failed")
