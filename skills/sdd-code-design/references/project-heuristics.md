# Project heuristic files

Resolve these paths from the project or worktree whose code is being considered.
Create the entry point when the first heuristic is accepted for recording.
Keep open questions and case-specific conclusions in the discussion.

| Project path | Contents |
| --- | --- |
| `memory/code-design/heuristics.md` | A Markdown title and the accepted entries. After grouping, a title and a short index of situations linking to group files. |
| `memory/code-design/groups/<group>.md` | A Markdown title and the entries used for a related set of decisions. Choose a descriptive kebab-case file name. |

## Entry

Use one level-two heading per heuristic and the five labels below. Write the
title and field values in the project's working language.

```markdown
## <Короткое название решения>

- **Когда применять** — <признак, видимый до принятия решения, и область применения>.
- **Что делать** — <какой выбор или проверку сделать>.
- **Почему** — <за счёт чего выбор существенно влияет на качество и для кого>.
- **Граница** — <условие, при котором совет теряет силу или требует другого выбора>.
- **Основание** — <краткий вывод разбора и ссылка на код, контракт или ревью, если доступна>.
```

Keep the basis understandable to someone without the original conversation.
When specializing a shared heuristic, identify the skill-relative reference path
and section in **Основание** and explain what the project condition adds.

## Grouping and edits

Keep a small set inline. Split it when an agent can routinely use the task or an
observable symptom to choose one group and skip another without losing a needed
exception. Keep decisions used together, their rationale and their exceptions in
the same group. File length is a prompt to examine actual use.

When splitting, move each complete entry to one group and replace the inline
entries with relative links. Write one index line per observable situation.

```markdown
- <Наблюдаемая ситуация> — [<Название группы>](groups/<group>.md)
```

Several situations can lead to the same group. Each heuristic has one full text.
In ordinary work open only matching groups. If a relevant link is broken, report
the missing guidance for that decision.

Before saving an agreed edit, reread the entry point and the affected group.
Update an equivalent entry in place. Change group contents and their index links
together, preserving other entries and resolving links from their new locations.
When an approved retirement empties a group, remove the empty group and its links.
Check that every retained entry is reachable and each index link opens its group.
