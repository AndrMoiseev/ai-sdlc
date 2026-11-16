# detekt measurement plugin

This module supplies complete Kotlin measurements to `sdd-architect` through the
detekt runtime already selected by the consuming project. It produces two thin
JARs in [`skills/sdd-architect/bin`](../../skills/sdd-architect/bin/).

`common/src` collects tokens, named functions, cognitive complexity and containers
from files parsed by detekt. `detekt1` and `detekt2` adapt `FileProcessListener`,
`OutputReport` and the host's cognitive-complexity implementation. Common Java
sources are compiled twice because detekt 1 relocates IntelliJ classes and detekt 2
uses a different API. No Kotlin compiler, detekt classes or third-party libraries
are bundled. The plugin neither creates a parser nor discovers source files.

## Supported runtimes

| Adapter | Minimum detekt | Delivered JAR |
| --- | --- | --- |
| 1.x | 1.23.8 | `detekt-measurements-1.jar` |
| 2.x | 2.0.0-alpha.6 | `detekt-measurements-2.jar` |

[`plugins.json`](../../skills/sdd-architect/bin/plugins.json) owns minimum versions,
artifact names, schema/profile and plugin version. Build dependencies use those
minimum versions to establish the API baseline. Runtime selection permits later
versions within the corresponding major; it does not pin an exact release or
promise untested future ABI compatibility. A loading or parsing failure is reported
without substituting another runtime.

## Build

Use JDK 17+ and a system Python 3.11+ through `uv`. Preserve `UV_CACHE_DIR` and
`UV_TOOL_DIR`; when absent, set them to absolute `uv-runtime/cache` and
`uv-runtime/tools` under the OS temporary directory and check write access.
Set `PYTHONDONTWRITEBYTECODE=1`. Find the interpreter once with
`uv python find --system --no-managed-python ">=3.11"`.

```text
uv run --python "<python>" --locked --script "<repo>/tools/detekt-measurements/build.py" --java-home "<jdk>"
```

The builder obtains baseline detekt CLI distributions from Maven Central under
`UV_TOOL_DIR/detekt-measurements`. To reuse existing distributions without downloading,
pass `--detekt1-jar <all.jar>` and `--detekt2-jar <all.jar>` for the listed minima.
These are build inputs only; audit execution downloads no detekt distribution.
The builder compiles with `--release 17`, generates report metadata from
`plugins.json`, and packages classes and service descriptors with stable timestamps.
Compiler output and temporary files stay outside the repository. Both adapters
must compile before either delivered JAR is replaced. Rebuild both after source
or metadata changes. Installation of skills is a separate operation.

## Invocation and report

The skill resolves the existing Gradle `detekt` configuration using an invocation-only
init script and launches its CLI, or accepts an explicitly supplied existing
CLI `all.jar`. It selects the adapter using the actual `--version` output.
See the [runtime contract](../../skills/sdd-architect/references/runtime.md) for
`--detekt-project`, `--detekt-jar`, prerequisites and failure behavior.

The CLI receives `--plugins <selected-jar>`, `--disable-default-rulesets` and
`--report sdd-architect-measurements:<output.json>`. The collector supplies:

| JVM property | Value |
| --- | --- |
| `sdd.architect.repository` | Absolute repository root |
| `sdd.architect.sourceManifest` | External UTF-8 file containing one repository-relative Kotlin path per line |
| `sdd.architect.detekt.version` | Version verified by invoking the host CLI |

The complete JSON report includes schema/profile, plugin version, actual detekt
and parser versions, and an exact inventory of measured files. Suppressions and
warning thresholds do not remove functions. Unknown, repeated or missing files
and parser errors fail the report. Tokens retain identifiers/literals and UTF-16
offsets after newline normalization. The measurement profile defines population
and output semantics; host version changes can still affect measured values.

## Validation

The mandatory sequential suite is `skills/sdd-architect/scripts/test.py`. Set:

- `ARCHITECT_TEST_JAVA`: absolute Java launcher path.
- `ARCHITECT_TEST_DETEKT1_JAR`, `ARCHITECT_TEST_DETEKT2_JAR`: existing baseline CLI distributions.
- `ARCHITECT_TEST_GRADLE_WRAPPER`: existing wrapper JAR with adjacent properties.

```text
uv run --python "<python>" --locked --script "<repo>/skills/sdd-architect/scripts/test.py"
```

It validates plugin packaging, selection boundaries, both actual host APIs,
suppressed and zero-complexity functions, nested functions, Unicode/CRLF positions,
new context parameters, and runtime discovery from a Gradle subproject. Other
metric and audit contracts run in the same suite. Keep fixtures and logs external.
The entire sequential run, including setup/build when performed together, must
finish within the repository's 120-second limit. Agent behavior evaluations
require separate user authorization.
