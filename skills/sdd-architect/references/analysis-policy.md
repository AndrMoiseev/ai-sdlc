# Resolve the analysis policy through the script

Before using a threshold, weight, budget, formula parameter or command limit, obtain
the effective policy through `metrics.py policy`. Use its output in assignments and
decisions. Project policy files remain read-only throughout this workflow; do not infer
effective values by reading defaults, copying a documentation example or merging
project overrides by hand. `collect` and `rank` use the same Python resolver.

Follow [runtime](runtime.md#execution-environment) before executing these commands:

```text
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" policy --repository "<project-root>"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" policy --collection "<report-dir>/collection.json"
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" policy --repository "<project-root>" --get signals.shape.parameter_list_minimum
uv run --python "<python>" --locked --script "<skill>/scripts/metrics.py" policy --defaults
```

The command prints JSON and writes nothing. `--get` selects a dotted key. Use the
project form before collection and the collection form throughout an existing
audit, including diagnosis, ranking and final report. `--defaults` displays the
bundled policy without creating project settings.

## Files and precedence

| File | Role |
| --- | --- |
| `<skill>/assets/analysis-policy.json` | Complete numerical defaults shipped with the skill |
| `<project-root>/.sdd/architect/analysis-policy.json` | Optional project overrides |
| `<skill>/assets/analysis-policy.schema.json` | One schema for both documents |
| `<report-dir>/collection.json`, field `analysis_policy` | Complete resolved values used by this audit |

Both input files have the same nested object structure. A project can supply a
full document or only the leaves it changes. The script merges objects recursively;
a supplied leaf replaces its default. An absent project file uses defaults. A
present malformed file, unknown key, invalid type, non-finite number or invalid
range fails explicitly. Numeric strings, booleans and null are not numbers here.
Defaults and saved audit values must be complete; project overrides may be partial.

Keep collection scope, source paths and tool/report configuration in the audit's
`collection-input.json`. Numerical policy, including `investigation.candidate_group_limit`,
is read from the separate project file. All audit participants preserve that file.
Changing project policy belongs to a separate user-initiated `sdd-setup` process;
approval within the audit does not authorize this workflow to edit it. Do not
invoke setup automatically or work around an option it does not yet support.
No project override file is needed to run with defaults.

`collect` resolves policy before writing results and saves it with the collection.
`rank` validates and uses that saved policy even if project settings have since
changed. To apply a changed policy to measurements and selections, create a new
collection and link the earlier audit. Retain the policy of earlier materials;
policy changes alone do not establish a code improvement.

## Parameter groups

| Group | Meaning |
| --- | --- |
| `signals` | Analyzer thresholds for cycles, complexity, declaration shape, Martin distance, coupling, hotspots, coverage and file CRAP |
| `measurements` | History filtering/window, Martin applicability, affinity labels, changes-per-code population/unit and CRAP exponents |
| `measurements.quality_indicators` | Cognitive/size limits, clone length/reference fraction, DL small-group limit and aggregate history window/support filters |
| `evidence` | Per-signal diagnostic weights and the cap for limited evidence |
| `investigation` | Automatic candidate-group budget and capped points for usable/limited evidence families |
| `recommendations` | Effect-category points, criterion weights and report display limit |
| `runtime` | Collector subprocess timeout and retained error-tail length |

All configurable numeric choices live in defaults. Structural definitions remain
in code: empty counts, arithmetic identities, graph pairs, percentage conversion,
JVM format tags, source coordinates and the fixed recommendation-card sections.
They do not change when a project tunes its analysis policy. Fixture measurements
and expected test results describe test cases, not operational defaults.
The [aggregate profile](quality-indicators.md) records its resolved parameters in
status.json. Changes to those definitions or parameters create a different comparison
basis; do not tune them merely to obtain a desired project score. Catalog history
filters and aggregate-history filters have distinct documented populations.

## Parameter counts and collection thresholds

Keep a detector's collection threshold low enough to supply the required population.
It describes which observations reached SARIF; it does not replace the analyzer's
`signals.shape.parameter_list_minimum` or its other selection thresholds.

For `LongParameterList`, the adapter counts parameters in the complete declaration
retained by the supported detekt message. It distinguishes outer separators from
generic arguments, function-type arguments, annotations and grouped default values.
The same analyzer threshold applies to function and constructor parameter lists.
Selection is inclusive at the configured minimum. A detector warning below this
minimum remains a measurement and does not seed a candidate group.

Unsupported or ambiguous declarations retain an unknown count and a collection gap;
they do not satisfy a numeric threshold. Obtain a supported complete declaration
if resolving the gap can change the diagnosis. The script never substitutes the
detector's threshold or guesses by splitting the message on every comma.

## Interpretation

Configuration changes selection policy, not the strength of the resulting claim.
Keep the [measurement limits](measurements.md), [family caps](candidate-groups.md)
and [grounded effect categories](decision-output.md) when using overrides. Diagnostic
weights, investigation points and recommendation effect points remain separate.
In a card, explain the actual policy returned by the script and any sensitivity to
it. An overridden CRAP formula or history population also changes comparability.
