# Test scope and execution budgets

## Choose meaningful coverage

Tie each new test to an explicit acceptance scenario, a typical supported workflow, or a demonstrated regression within scope. Use the smallest fixture that still distinguishes correct behavior from the relevant failure. Cover required error paths and boundaries, but justify additional volume, repetitions, concurrency, or fault combinations by what they prove.

Create, expand, or separately launch load, stress, soak, throughput, capacity, memory-scaling tests, and performance benchmarks only when the user explicitly requests that testing. General requirements for performance, recovery, streaming, or robustness, observed workload size, and reviewer recommendations do not provide this authorization. Without an explicit request, use functional regression tests with minimal sufficient fixtures and record potential performance concerns in technical debt. Do not proactively ask for load testing merely because a hypothetical concern arose.

Separate functional correctness from capacity and performance claims. For example, verify journal replay order and restoration of the latest state using a few distinct records; do not generate hundreds of large snapshots to measure memory consumption without the explicit request above. A small functional fixture does not prove bounded memory or throughput; report that limit honestly. If an explicit acceptance criterion cannot be verified without unrequested load testing, record the verification gap and follow the requirement-blocker workflow rather than inventing testing authorization.

When the user explicitly requests such testing, establish its scope, scale, assertions, and runtime/resource budget. Keep it in a separately invoked target using repository conventions unless the user requests default-suite inclusion. Measure its actual cost under a deadline.

Run new or materially changed tests individually under a deadline before the full required suite. Inspect disproportionate cost, including fixture setup, repeated database writes, subprocesses, and logging. Prefer reducing setup cost or fixture size while preserving the assertion. Preserve required coverage and required suite membership; an existing slow test is a diagnostic issue, not permission to silently skip it, weaken its assertions, or move a required check out of the suite.

Running an existing required suite remains authorized even if it already contains load tests; the explicit-request rule governs adding or expanding those tests and launching them separately. Apply the suite deadline and report any existing load test that prevents completion. Do not remove or disable existing tests automatically.

## Bound check execution

Set a finite wall-clock deadline before launching each check, including the complete suite. Use explicit project/user budgets when available; otherwise derive a budget with headroom from a comparable successful run. When neither exists, use initial diagnostic limits of 2 minutes for a focused test and 10 minutes for a full check command, including build/setup time. These are investigation thresholds, not product performance requirements. Adjust them when measured baseline or workload evidence supports a different duration, and record the reason before rerunning.

Use runner-native timeouts for diagnostic output where available, plus a watchdog covering the whole command and its owned child processes. A tool's output-yield interval is not a process timeout; a per-test or per-package timeout is not a whole-suite deadline. Retain bounded output sufficient to identify the active test/package and failures; avoid unbounded verbose tracing by default.

When a deadline expires, capture available diagnostics and terminate only that check's owned process tree, preserving implementation files. Record the check as timed out, never passed. File/log activity or CPU usage alone does not justify extending the deadline. Diagnose the slow test/package with a bounded focused run, separating test setup, instrumentation overhead, and actual product behavior. Retry the full suite after a concrete correction or evidence-based budget adjustment, rather than repeating unchanged waits or raising limits merely to obtain a pass.

An interrupted required suite remains unverified and blocks its implementation/correction commit. Follow the ordinary blocker workflow if the cause cannot be resolved within authorized scope; retain unfinished changes and the next diagnostic action. Optional performance experiments do not replace required checks.
