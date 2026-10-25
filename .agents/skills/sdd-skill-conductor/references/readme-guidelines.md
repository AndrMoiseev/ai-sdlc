# Skill README

Write for someone deciding when to use the skill and what to ask it to do.
Keep the README at the repository's established location; for a new skill,
place `README.md` beside `SKILL.md`. Installation instructions and implementation
details do not belong in this document: omit setup commands, dependency setup,
internal scripts, module layouts, algorithms, and evaluator mechanics.

## Content

1. Open with a short description of the skill's purpose and the result the user
   receives. One or two sentences are enough.
2. Explain its place in the AI SDLC ecosystem when repository evidence supports
   that relationship: which activity it supports, what inputs it receives, and
   which skills or artifacts use its results. Link to the relevant documentation.
   For a standalone skill with no such relationship, omit this section.
3. Give copyable prompts paired with the expected user-visible result. Derive the
   examples from the skill's actual modes and routing conditions. When prompt
   variants select different flows, cover every flow, including branches within
   a mode that change the action or result. Several paraphrases of one request
   do not cover different flows. A table with columns **Flow**, **Example prompt**,
   and **Expected result** works well; separate examples work too.

Before drafting examples, map each prompt-selected flow to at least one example.
Check the map against `SKILL.md` and the relevant references after editing.
Use concrete requests with enough context to select the intended flow; preserve
required arguments and explicit invocation syntax.

## Explanatory diagrams

Use `archify` when a diagram helps explain flow selection, a sequence of user
actions, or the skill's relationships in AI SDLC. Skip a diagram when the short
description and prompt examples already explain the behavior.

Read the available `archify` skill and follow its generation and validation
workflow. Show user-visible actions, results, and handoffs at the README's level
of detail. Embed a Markdown-compatible export with alt text and a short caption;
link to the interactive HTML when it is retained. Store published diagram assets
with the documentation, and keep temporary candidates and validation reports
outside the skill package. Verify relative links and the rendered diagram.

## Final editing and review

After content and diagrams are complete, apply `humanizer-ru` to Russian README
prose addressed to people. Follow its audit, editing and verification workflow;
preserve facts, skill names, links, prompt semantics and coverage of every flow.
This applies only to the README. Do not use `humanizer-ru` for other skill files,
including skill instructions, agent contracts and runtime documentation.
For a non-Russian README, edit for clarity in its established language.

If a required dependency skill is unavailable, report which step remains
incomplete; do not claim that diagram generation or final editing was performed.

Before delivery, check the purpose, any documented ecosystem relationships,
complete prompt-to-flow coverage, diagram links, and completion of final editing.
Confirm installation instructions and implementation details are absent.
