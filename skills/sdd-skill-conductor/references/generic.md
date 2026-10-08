# Arbitrary agent path

Use this branch when the current agent is neither Codex nor Claude Code, or the host is unknown. Describe the requested skill behavior, inputs, constraints, and completion evidence in prose. Preserve the skill's invocation policy: explicit-only skills start from an explicit request to use them, without assuming slash commands or enforced host metadata.

Establish only the capabilities needed by the selected mode from the actual environment: reading supplied resources, editing files, executing commands, starting independent contexts, isolating workspaces, or observing traces. Neither a familiar model name nor an installed CLI establishes the current host's capabilities. If files cannot be read or written, work from supplied text and return proposed content clearly marked as unsaved.

For evaluations, assign the same task and fixture state to independent baseline and candidate contexts, with only the intended skill difference. Give executors task material without author history, grading answers, or earlier results. Confirm context and workspace isolation before treating the comparison as independent. Use the environment's actual mechanisms; no particular tool names, model controls, or telemetry fields are assumed.

If independent execution is unavailable, prepare manual scenarios with expected evidence and report behavioral evaluation as not run. Perform structural checks only with available tools; a prose inspection is not a successful script run. Record missing telemetry as unavailable. Preserve required review gates and do not claim a tested or packaged result without its evidence.

The bundled CLI adapter supports only `auto|codex|claude-code`; `generic` is not a CLI argument. Use that adapter only when a supported CLI is deliberately selected and passes runtime preflight. Such a run validates the selected CLI, not the arbitrary host. If no supported execution path exists, continue the prose workflow and disclose the remaining checks.
