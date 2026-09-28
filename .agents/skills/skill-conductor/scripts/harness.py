"""CLI adapters for fresh Codex and Claude Code evaluation sessions."""

import json
import os
import shutil
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

HARNESSES = ("auto", "codex", "claude-code")
EXECUTABLES = {"codex": "codex", "claude-code": "claude"}


class HarnessError(RuntimeError):
    """Execution failed; this is not a negative skill evaluation."""


def resolve_harness(requested: str = "auto") -> str:
    choice = requested
    if choice == "auto":
        choice = os.environ.get("SKILL_CONDUCTOR_HARNESS", "auto")
    if choice not in HARNESSES:
        raise HarnessError(f"Unknown harness {choice!r}; choose {', '.join(HARNESSES)}")
    if choice == "auto":
        detected = []
        if os.environ.get("CODEX_THREAD_ID"):
            detected.append("codex")
        if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
            detected.append("claude-code")
        if len(detected) > 1:
            raise HarnessError("Conflicting host markers; pass --harness codex or --harness claude-code")
        if detected:
            choice = detected[0]
        else:
            installed = [name for name, exe in EXECUTABLES.items() if shutil.which(exe)]
            if len(installed) != 1:
                raise HarnessError("Cannot identify current harness; pass --harness codex or --harness claude-code")
            choice = installed[0]
    if not shutil.which(EXECUTABLES[choice]):
        raise HarnessError(f"Selected harness {choice}: {EXECUTABLES[choice]} CLI not found. Use native fresh subagents or install that CLI; no automatic provider fallback.")
    return choice


def build_command(harness: str, model: str | None, allow_writes: bool) -> list[str]:
    executable = shutil.which(EXECUTABLES[harness])
    if not executable:
        raise HarnessError(f"{EXECUTABLES[harness]} CLI not found")
    if harness == "codex":
        command = [executable, "exec", "--json", "--ephemeral", "--skip-git-repo-check",
                   "--color", "never", "--sandbox", "workspace-write" if allow_writes else "read-only"]
        if model:
            command += ["--model", model]
        command += ["-"]
    else:
        command = [executable, "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence"]
        if allow_writes:
            command += ["--permission-mode", "acceptEdits"]
        else:
            command += ["--tools", "Read,Glob,Grep,Skill"]
        if model:
            command += ["--model", model]
    return command


@dataclass
class RunResult:
    harness: str
    model: str | None
    status: str
    text: str
    events: list[dict]
    usage: dict | None
    duration_ms: int
    returncode: int | None
    stdout: str
    stderr: str
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def parse_output(stdout: str, harness: str) -> tuple[list[dict], str, dict | None, str | None]:
    """Require a successful terminal event; a broken stream is not non-invocation."""
    events, texts = [], []
    usage, error = None, None
    completed = False
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        kind = event.get("type")
        if harness == "codex":
            if kind == "item.completed" and event.get("item", {}).get("type") == "agent_message":
                texts.append(event["item"].get("text", ""))
            elif kind == "turn.completed":
                completed, usage = True, event.get("usage")
            elif kind in ("turn.failed", "error"):
                error = json.dumps(event.get("error", event.get("message", event)), ensure_ascii=False)
        elif kind == "result":
            if event.get("is_error") or event.get("subtype") != "success":
                error = str(event.get("errors") or event.get("result") or event.get("subtype"))
            else:
                completed, texts = True, [event.get("result", "")]
            usage = event.get("usage")
            if event.get("permission_denials"):
                error = "Claude Code reported permission denials; inspect the transcript"
    if not completed and not error:
        error = "CLI stream has no successful completion event; inspect stdout/stderr"
    return events, texts[-1] if texts else "", usage, error


def _stop_process(process: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired):
        pass
    finally:
        if process.poll() is None:
            process.kill()


def run_prompt(prompt: str, workspace: Path, harness: str = "auto", model: str | None = None,
               timeout: int = 120, allow_writes: bool = False) -> RunResult:
    selected = resolve_harness(harness)
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    workspace = Path(workspace).resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("workspace must be a directory")
    command = build_command(selected, model, allow_writes)
    env = os.environ.copy()
    for name in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CODEX_THREAD_ID", "SKILL_CONDUCTOR_HARNESS"):
        env.pop(name, None)
    start = time.monotonic()
    process = subprocess.Popen(command, cwd=workspace, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace",
                               start_new_session=os.name != "nt",
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    timed_out = False
    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop_process(process)
        stdout, stderr = process.communicate(timeout=10)
    except BaseException:
        _stop_process(process)
        process.communicate(timeout=10)
        raise
    events, text, usage, error = parse_output(stdout, selected)
    if timed_out:
        error = f"Evaluation timed out after {timeout}s"
    elif process.returncode:
        error = f"{selected} exited with code {process.returncode}: {stderr[-2000:] or error or 'inspect stdout'}"
    return RunResult(selected, model, "timeout" if timed_out else "error" if error else "completed",
                     text, events, usage, round((time.monotonic() - start) * 1000),
                     process.returncode, stdout, stderr, error)


def require_success(result: RunResult) -> str:
    if result.status != "completed":
        raise HarnessError(result.error or f"{result.harness} execution failed")
    return result.text


def save_run(result: RunResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "stdout.jsonl").write_text(result.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    (output_dir / "response.md").write_text(result.text, encoding="utf-8")
    metadata = result.to_dict()
    for key in ("stdout", "stderr", "events", "text"):
        metadata.pop(key)
    (output_dir / "run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    usage = result.usage or {}
    counts = [usage.get("input_tokens"), usage.get("output_tokens")]
    if result.harness == "claude-code":
        counts += [usage.get("cache_read_input_tokens", 0), usage.get("cache_creation_input_tokens", 0)]
    # Codex cached_input_tokens is a subset of input_tokens, not additional usage.
    total_tokens = sum(counts) if all(isinstance(n, int) and not isinstance(n, bool) for n in counts) else None
    timing = {"total_tokens": total_tokens, "duration_ms": result.duration_ms,
              "total_duration_seconds": result.duration_ms / 1000}
    (output_dir / "timing.json").write_text(json.dumps(timing, indent=2), encoding="utf-8")


def skill_was_used(result: RunResult, skill_name: str, marker: str) -> bool:
    """The marker is present only in the probe body, never in its query."""
    if marker in result.text:
        return True
    read_ids = set()
    for event in result.events:
        if result.harness == "claude-code" and event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "Skill":
                    if block.get("input", {}).get("skill", "").split(":")[-1] == skill_name:
                        return True
                if block.get("type") == "tool_use" and block.get("name") == "Read":
                    path = block.get("input", {}).get("file_path", "").replace("\\", "/")
                    if path.endswith(f"/{skill_name}/SKILL.md"):
                        read_ids.add(block.get("id"))
        if result.harness == "claude-code" and event.get("type") == "user":
            for block in event.get("message", {}).get("content", []):
                if (block.get("type") == "tool_result" and block.get("tool_use_id") in read_ids
                        and not block.get("is_error") and marker in json.dumps(block.get("content", ""))):
                    return True
        if result.harness == "codex" and event.get("type") == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "command_execution" and item.get("exit_code") == 0:
                if marker in item.get("aggregated_output", ""):
                    return True
            if item.get("type") == "mcp_tool_call" and item.get("status") == "completed":
                if marker in json.dumps(item.get("result", {}), ensure_ascii=False):
                    return True
    return False
