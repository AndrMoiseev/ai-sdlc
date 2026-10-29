"""Exact argument-array command execution; no execution-state dependencies."""
import base64
import os
import signal
import subprocess
import time
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def valid_command(command):
    return (isinstance(command, list) and bool(command)
            and all(isinstance(arg, str) and "\0" not in arg for arg in command)
            and bool(command[0].strip()))


COMMAND_FORMAT = "command must be an argument array, e.g. ['pytest', '-q']; migrate legacy strings explicitly without changing approved checks"


def command_result(command, cwd, started, stamp, stdout, stderr, code, outcome, limitation=None):
    return {"command": command, "cwd": str(cwd), "started_at": stamp,
            "duration_seconds": time.monotonic() - started, "exit_code": code,
            "stdout_base64": base64.b64encode(stdout).decode("ascii"),
            "stdout": stdout.decode("utf-8", "replace"),
            "stderr_base64": base64.b64encode(stderr).decode("ascii"),
            "stderr": stderr.decode("utf-8", "replace"), "outcome": outcome, "limitation": limitation}


def run_command(command, cwd, timeout):
    started, stamp = time.monotonic(), now()
    if not valid_command(command):
        return command_result(command, cwd, started, stamp, b"", COMMAND_FORMAT.encode(),
                              None, "unavailable", "command_format")
    limitation = None
    try:
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(command, shell=False, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], shell=False, capture_output=True)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(timeout=10)
            return command_result(command, cwd, started, stamp, stdout, stderr, None, "unavailable", "timeout")
        code = process.returncode
        outcome = "passed" if code == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code, outcome = exc.stdout or b"", exc.stderr or b"", None, "unavailable"
        limitation = "process_cleanup_timeout"
    except OSError as exc:
        stdout, stderr, code, outcome = b"", str(exc).encode(), None, "unavailable"
        limitation = "process_launch_error"
    return command_result(command, cwd, started, stamp, stdout, stderr, code, outcome, limitation)


