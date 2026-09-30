#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Offline regression tests for harness execution and evaluation integrity."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import aggregate_benchmark, harness, improve_description, run_eval, run_loop, run_task, utils


def jsonl(*events):
    return "\n".join(json.dumps(event, ensure_ascii=False) for event in events)


def result(backend="codex", status="completed", text="done", events=None):
    return harness.RunResult(backend, None, status, text, events or [], None, 25,
                             0 if status == "completed" else 1, "", "",
                             None if status == "completed" else "execution failed")


def installed(*names):
    return lambda name: str(Path("bin") / name) if name in names else None


class SelectionTests(unittest.TestCase):
    def select(self, env, binaries, requested="auto"):
        with patch.dict(os.environ, env, clear=True), patch.object(harness.shutil, "which", side_effect=installed(*binaries)):
            return harness.resolve_harness(requested)

    def test_explicit_overrides_environment_and_host(self):
        self.assertEqual(self.select({"SKILL_CONDUCTOR_HARNESS": "claude-code", "CLAUDECODE": "1"},
                                     ["codex", "claude"], "codex"), "codex")

    def test_environment_overrides_host(self):
        self.assertEqual(self.select({"SKILL_CONDUCTOR_HARNESS": "claude-code", "CODEX_THREAD_ID": "thread"},
                                     ["codex", "claude"]), "claude-code")

    def test_host_and_single_install_detection(self):
        for env, expected in [({"CODEX_THREAD_ID": "thread"}, "codex"),
                              ({"CLAUDECODE": "1"}, "claude-code"),
                              ({"CLAUDE_CODE_ENTRYPOINT": "cli"}, "claude-code")]:
            with self.subTest(env=env):
                self.assertEqual(self.select(env, ["codex", "claude"]), expected)
        self.assertEqual(self.select({}, ["codex"]), "codex")
        self.assertEqual(self.select({}, ["claude"]), "claude-code")

    def test_ambiguous_unknown_and_unavailable_fail_without_fallback(self):
        cases = [({}, ["codex", "claude"], "auto"), ({}, [], "auto"),
                 ({"CODEX_THREAD_ID": "x", "CLAUDECODE": "1"}, ["codex", "claude"], "auto"),
                 ({"SKILL_CONDUCTOR_HARNESS": "other"}, ["codex"], "auto"),
                 ({"CODEX_THREAD_ID": "x"}, ["claude"], "auto"),
                 ({}, ["claude"], "codex")]
        for env, binaries, requested in cases:
            with self.subTest(env=env, binaries=binaries, requested=requested):
                with self.assertRaises(harness.HarnessError):
                    self.select(env, binaries, requested)


class ExecutionTests(unittest.TestCase):
    def test_windows_cleanup_kills_process_when_taskkill_fails(self):
        for failure in (OSError("taskkill unavailable"), subprocess.TimeoutExpired("taskkill", 10)):
            with self.subTest(failure=type(failure).__name__):
                process = Mock(pid=4321)
                process.poll.return_value = None
                with patch.object(harness.os, "name", "nt"), \
                        patch.object(harness.subprocess, "CREATE_NO_WINDOW", 0, create=True), \
                        patch.object(harness.subprocess, "run", side_effect=failure):
                    harness._stop_process(process)
                process.kill.assert_called_once_with()

    def test_codex_response_uses_final_message_and_preserves_commentary_in_trace(self):
        stream = jsonl(
            {"type": "item.completed", "item": {"type": "agent_message", "text": "Inspecting source files."}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "Глоссарий обновлён."}},
            {"type": "turn.completed"},
        )
        events, text, _, error = harness.parse_output(stream, "codex")
        self.assertIsNone(error)
        self.assertEqual(text, "Глоссарий обновлён.")
        self.assertEqual(events[0]["item"]["text"], "Inspecting source files.")
        self.assertEqual(len(events), 3)

    def test_claude_read_counts_only_matching_successful_skill_body(self):
        marker = "SKILL_CONDUCTOR_PROBE_read"
        for is_error, result_id, path, expected in [
            (False, "read-1", "C:\\fixtures\\glossary\\SKILL.md", True),
            (True, "read-1", "/fixtures/glossary/SKILL.md", False),
            (False, "other-tool", "/fixtures/glossary/SKILL.md", False),
            (False, "read-1", "/fixtures/another-skill/SKILL.md", False),
        ]:
            with self.subTest(is_error=is_error, result_id=result_id, path=path):
                events = [
                    {"type": "assistant", "message": {"content": [
                        {"type": "tool_use", "id": "read-1", "name": "Read", "input": {"file_path": path}}
                    ]}},
                    {"type": "user", "message": {"content": [
                        {"type": "tool_result", "tool_use_id": result_id, "is_error": is_error,
                         "content": [{"type": "text", "text": f"Skill instructions: {marker}"}]}
                    ]}},
                ]
                outcome = result("claude-code", text="Final answer without marker", events=events)
                self.assertEqual(harness.skill_was_used(outcome, "glossary", marker), expected)

    def test_commands_restrict_permissions_and_use_configured_model_by_default(self):
        with patch.object(harness.shutil, "which", side_effect=installed("codex", "claude")):
            for backend in ("codex", "claude-code"):
                for writes in (False, True):
                    command = harness.build_command(backend, None, writes)
                    with self.subTest(backend=backend, writes=writes):
                        self.assertNotIn("--model", command)
                        self.assertFalse(any("bypass" in arg or "dangerously" in arg or "skip-permissions" in arg for arg in command))
                        if backend == "codex":
                            self.assertEqual(command[command.index("--sandbox") + 1], "workspace-write" if writes else "read-only")
                            self.assertEqual(command[-1], "-")
                        elif writes:
                            self.assertEqual(command[command.index("--permission-mode") + 1], "acceptEdits")
                        else:
                            tools = command[command.index("--tools") + 1].split(",")
                            self.assertIn("Read", tools)
                            self.assertNotIn("Bash", tools)
                            self.assertNotIn("Write", tools)
                command = harness.build_command(backend, "selected-model", False)
                self.assertEqual(command[command.index("--model") + 1], "selected-model")

    def test_unicode_prompt_uses_stdin_and_real_workspace(self):
        process = Mock(returncode=0)
        process.communicate.return_value = (jsonl({"type": "item.completed", "item": {"type": "agent_message", "text": "Готово"}},
                                                 {"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 2}}), "")
        prompt = "Обнови глоссарий; $(never execute) `literal`"
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CODEX_THREAD_ID": "host"}), \
                patch.object(harness.shutil, "which", side_effect=installed("codex")), \
                patch.object(harness.subprocess, "Popen", return_value=process) as popen:
            outcome = harness.run_prompt(prompt, Path(directory), timeout=8)
            args, kwargs = popen.call_args
            self.assertNotIn(prompt, args[0])
            self.assertEqual(kwargs["cwd"], Path(directory).resolve())
            self.assertEqual(kwargs["encoding"], "utf-8")
            self.assertNotIn("CODEX_THREAD_ID", kwargs["env"])
            process.communicate.assert_called_once_with(prompt, timeout=8)
            self.assertEqual(outcome.status, "completed")
            self.assertEqual(outcome.text, "Готово")
            self.assertEqual(outcome.usage["output_tokens"], 2)

    def test_timeout_and_nonzero_exit_are_execution_errors(self):
        success = jsonl({"type": "turn.completed"})
        for timeout in (True, False):
            process = Mock(returncode=1)
            process.communicate.side_effect = [subprocess.TimeoutExpired("codex", 1), (success, "")] if timeout else [(success, "login failed")]
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as directory, \
                    patch.object(harness.shutil, "which", side_effect=installed("codex")), \
                    patch.object(harness.subprocess, "Popen", return_value=process), \
                    patch.object(harness, "_stop_process") as stop:
                outcome = harness.run_prompt("test", Path(directory), "codex", timeout=1)
                self.assertEqual(outcome.status, "timeout" if timeout else "error")
                self.assertEqual(stop.call_count, int(timeout))
                with self.assertRaises(harness.HarnessError):
                    harness.require_success(outcome)

    def test_parse_complete_broken_and_permission_streams(self):
        cases = [
            ("codex", [{"type": "turn.completed", "usage": {"output_tokens": 1}}], False),
            ("codex", [{"type": "turn.failed", "error": {"message": "permission denied"}}], True),
            ("codex", [{"type": "error", "message": "authentication failed"}, {"type": "turn.completed"}], True),
            ("claude-code", [{"type": "result", "subtype": "success", "result": "Готово"}], False),
            ("claude-code", [{"type": "result", "subtype": "success", "permission_denials": [{"tool_name": "Write"}]}], True),
            ("claude-code", [{"type": "result", "subtype": "error_during_execution", "is_error": True}], True),
        ]
        for backend, events, failed in cases:
            with self.subTest(backend=backend, events=events):
                _, _, _, error = harness.parse_output(jsonl(*events), backend)
                self.assertEqual(error is not None, failed)
        for backend in ("codex", "claude-code"):
            self.assertIsNotNone(harness.parse_output("not json\n{}\n[]", backend)[3])

    def test_skill_evidence_excludes_name_narration_and_unexecuted_commands(self):
        marker = "SKILL_CONDUCTOR_PROBE_123"
        narration = result(text="I will use glossary and read SKILL.md.", events=[
            {"type": "item.completed", "item": {"type": "command_execution", "command": f"echo {marker}", "exit_code": 1, "aggregated_output": ""}}])
        self.assertFalse(harness.skill_was_used(narration, "glossary", marker))
        for event in [
            {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0, "aggregated_output": f"skill body: {marker}"}},
            {"type": "item.completed", "item": {"type": "mcp_tool_call", "status": "completed", "result": {"text": marker}}},
        ]:
            self.assertTrue(harness.skill_was_used(result(events=[event]), "glossary", marker))
        event = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "glossary"}}]}}
        self.assertTrue(harness.skill_was_used(result("claude-code", events=[event]), "glossary", marker))


class EvaluationTests(unittest.TestCase):
    def test_negative_query_never_passes_on_error_or_timeout(self):
        for status in ("error", "timeout"):
            with self.subTest(status=status), patch.object(run_eval, "resolve_harness", return_value="codex"), \
                    patch.object(run_eval, "run_single_query", return_value={"status": status, "triggered": None, "error": "failed"}):
                output = run_eval.run_eval([{"query": "unrelated task", "should_trigger": False}], "glossary", "desc", 1, 1, Path.cwd())
                self.assertFalse(output["results"][0]["pass"])
                self.assertIsNone(output["results"][0]["trigger_rate"])
                self.assertEqual(output["summary"]["errors"], 1)

    def test_probes_use_distinct_workspaces_and_preserve_project(self):
        workspaces = []
        def execute(prompt, workspace, backend, model, timeout):
            workspaces.append(workspace)
            expected = workspace / (".agents" if backend == "codex" else ".claude") / "skills" / "glossary" / "SKILL.md"
            body = expected.read_text(encoding="utf-8")
            self.assertIn("Создай глоссарий", body)
            marker = body.split("Reply with `", 1)[1].split("`", 1)[0]
            self.assertNotIn(marker, prompt)
            return result(backend, text=marker)
        with tempfile.TemporaryDirectory() as project, patch.object(run_eval, "run_prompt", side_effect=execute):
            sentinel = Path(project) / "notes.txt"
            sentinel.write_text("original", encoding="utf-8")
            for backend in ("codex", "claude-code"):
                with patch.object(run_eval, "resolve_harness", return_value=backend):
                    output = run_eval.run_single_query("make glossary", "glossary", "Создай глоссарий", 10, project)
                    self.assertTrue(output["triggered"])
            self.assertEqual(list(Path(project).iterdir()), [sentinel])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "original")
        self.assertNotEqual(workspaces[0], workspaces[1])
        self.assertTrue(all(not path.exists() for path in workspaces))

    def test_utf8_and_explicit_only_policies(self):
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory)
            content = "---\nname: glossary\ndescription: >\n  Создай глоссарий\n  проекта.\n---\n# Термины\n"
            (skill / "SKILL.md").write_text(content, encoding="utf-8-sig")
            self.assertEqual(utils.parse_skill_md(skill)[:2], ("glossary", "Создай глоссарий проекта."))
            utils.ensure_implicit_allowed(skill, "codex")
            (skill / "agents").mkdir()
            (skill / "agents" / "openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "explicit-only"):
                utils.ensure_implicit_allowed(skill, "codex")
            utils.ensure_implicit_allowed(skill, "claude-code")
            (skill / "SKILL.md").write_text(content.replace("name: glossary", "name: glossary\ndisable-model-invocation: true"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "explicit-only"):
                utils.ensure_implicit_allowed(skill, "claude-code")

    def test_task_failure_is_nonzero_and_existing_artifacts_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            prompt = base / "prompt.txt"
            prompt.write_text("Создай глоссарий", encoding="utf-8")
            output = base / "run"
            argv = ["run_task.py", "--harness", "codex", "--prompt-file", str(prompt), "--workspace", str(base), "--output-dir", str(output)]
            with patch.object(sys, "argv", argv), patch.object(run_task, "run_prompt", return_value=result(status="error")) as execute, \
                    patch("builtins.print"):
                self.assertEqual(run_task.main(), 1)
                self.assertEqual(json.loads((output / "run.json").read_text(encoding="utf-8"))["status"], "error")
                self.assertEqual(run_task.main(), 1)
                self.assertEqual(execute.call_count, 1)


class OptimizationTests(unittest.TestCase):
    def test_oversize_improvement_gets_one_retry_then_fails(self):
        row = {"query": "train", "should_trigger": True, "pass": False, "triggers": 0, "runs": 1}
        evidence = {"summary": {"passed": 0, "total": 1}, "results": [row]}
        with patch.object(improve_description, "resolve_harness", return_value="claude-code"), \
                patch.object(improve_description, "run_prompt", return_value=result("claude-code", text="x" * 1025)) as execute:
            with self.assertRaisesRegex(ValueError, "1024"):
                improve_description.improve_description("glossary", "body", "old", evidence, [],
                                                        harness="claude-code", model="selected-model")
        self.assertEqual(execute.call_count, 2)
        for call in execute.call_args_list:
            self.assertEqual(call.kwargs["harness"], "claude-code")
            self.assertEqual(call.kwargs["model"], "selected-model")
            self.assertFalse(call.kwargs["allow_writes"])

    def test_editor_sees_training_only_and_uses_selected_harness(self):
        row = {"query": "TRAIN", "should_trigger": True, "pass": False, "triggers": 0, "runs": 1}
        evidence = {"summary": {"passed": 0, "total": 1}, "results": [row]}
        history = [{"description": "old", "train_results": [row], "train_passed": 0, "train_total": 1,
                    "test_results": [{"query": "HELD_OUT_SECRET"}], "notes": "HELD_OUT_SECRET"}]
        with patch.object(improve_description, "resolve_harness", return_value="codex"), \
                patch.object(improve_description, "run_prompt", return_value=result(text="<new_description>Новый глоссарий</new_description>")) as execute:
            answer = improve_description.improve_description("glossary", "body", "old", evidence, history, harness="auto")
        self.assertEqual(answer, "Новый глоссарий")
        request = execute.call_args.kwargs
        self.assertEqual(request["harness"], "codex")
        self.assertIsNone(request["model"])
        self.assertFalse(request["allow_writes"])
        self.assertIn("TRAIN", request["prompt"])
        self.assertNotIn("HELD_OUT_SECRET", request["prompt"])

    def test_loop_preserves_backend_and_blinds_holdout(self):
        queries = [{"query": f"query-{n}", "should_trigger": n % 2 == 0} for n in range(8)]
        def evaluate(**kwargs):
            return {"summary": {"errors": 0}, "results": [dict(row, **{"pass": False, "triggers": 0, "runs": 1}) for row in kwargs["eval_set"]]}
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory)
            (skill / "SKILL.md").write_text("---\nname: glossary\ndescription: old\n---\nbody", encoding="utf-8")
            with patch.object(run_loop, "resolve_harness", return_value="codex"), \
                    patch.object(run_loop, "run_eval", side_effect=evaluate) as evaluator, \
                    patch.object(run_loop, "improve_description", return_value="new") as editor:
                report = run_loop.run_loop(queries, skill, None, 1, 10, 2, 1, .5, .4, harness="auto")
            self.assertEqual(report["harness"], "codex")
            self.assertEqual(evaluator.call_count, 2)
            self.assertTrue(all(call.kwargs["harness"] == "codex" for call in evaluator.call_args_list))
            request = editor.call_args.kwargs
            self.assertEqual(request["harness"], "codex")
            held_out = {row["query"] for row in report["history"][0]["test_results"]}
            training = {row["query"] for row in request["eval_results"]["results"]}
            self.assertTrue(held_out)
            self.assertTrue(held_out.isdisjoint(training))
            self.assertTrue(all(not key.startswith("test_") for entry in request["history"] for key in entry))
            with patch.object(run_loop, "resolve_harness", return_value="codex"), \
                    patch.object(run_loop, "run_eval", return_value={"summary": {"errors": 1}, "results": []}), \
                    patch.object(run_loop, "improve_description") as editor:
                with self.assertRaises(harness.HarnessError):
                    run_loop.run_loop(queries, skill, None, 1, 10, 2, 1, .5, .4)
                editor.assert_not_called()


class TelemetryTests(unittest.TestCase):
    def test_run_artifacts_count_reported_tokens_without_double_counting_codex_cache(self):
        cases = [
            ("codex", {"input_tokens": 20, "cached_input_tokens": 15, "output_tokens": 3}, 23),
            ("claude-code", {"input_tokens": 20, "cache_read_input_tokens": 15,
                             "cache_creation_input_tokens": 7, "output_tokens": 3}, 45),
            ("codex", None, None),
        ]
        for backend, usage, expected in cases:
            with self.subTest(backend=backend, usage=usage), tempfile.TemporaryDirectory() as directory:
                outcome = result(backend)
                outcome.usage = usage
                harness.save_run(outcome, Path(directory))
                timing = json.loads((Path(directory) / "timing.json").read_text(encoding="utf-8"))
                self.assertEqual(timing["total_tokens"], expected)
                self.assertEqual(timing["duration_ms"], 25)
                self.assertEqual(timing["total_duration_seconds"], .025)

    def test_missing_metrics_are_excluded_from_means_and_deltas(self):
        stats = aggregate_benchmark.calculate_stats([None, 10, 20])
        self.assertEqual(stats["mean"], 15)
        self.assertEqual(stats["n"], 2)
        self.assertIsNone(aggregate_benchmark.calculate_stats([None])["mean"])
        summary = aggregate_benchmark.aggregate_results({
            "with_skill": [{"pass_rate": 1, "time_seconds": 2, "tokens": 10}],
            "without_skill": [{"pass_rate": 1, "time_seconds": None, "tokens": None}],
        })
        self.assertIsNone(summary["delta"]["tokens"])
        self.assertIsNone(summary["delta"]["time_seconds"])

    def test_output_characters_are_not_substituted_for_missing_token_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            benchmark = Path(directory)
            run = benchmark / "eval-glossary" / "with_skill" / "run-1"
            run.mkdir(parents=True)
            grading = {"summary": {"pass_rate": 1, "passed": 1, "failed": 0, "total": 1},
                       "execution_metrics": {"output_chars": 9999}, "expectations": []}
            (run / "grading.json").write_text(json.dumps(grading), encoding="utf-8")
            loaded = aggregate_benchmark.load_run_results(benchmark)
            self.assertIsNone(loaded["with_skill"][0]["tokens"])
            self.assertIsNone(loaded["with_skill"][0]["time_seconds"])
            generated = aggregate_benchmark.generate_benchmark(benchmark)
            self.assertIsNone(generated["run_summary"]["with_skill"]["tokens"]["mean"])
            self.assertIn("Tokens", aggregate_benchmark.generate_markdown(generated))


if __name__ == "__main__":
    unittest.main()
