# Analysis of native execution evidence

The sequential run satisfies five recorded assertions. Each assertion points to actual host launches, CLI events, raw verification output or the final commit. These results support successful execution of that fixture. They do not establish a comparative improvement: no matching without-skill run is present, and the earlier baseline uses a different task runner and procedure.

The 100% figure in benchmark.json means five assertions passed in one run. It is not an estimate of reliability across requests. There is no variance estimate across repeated native runs. Token cost is unavailable and remains null. The measured 1492.745964 seconds covers initialization through finalization, excludes preparation, and includes debugging a real CRLF ownership failure. Comparing this duration with the baseline would be misleading.

The premature-acceptance rejection is discriminating evidence for the deterministic gate. It is not by itself evidence that an unconstrained agent would resist pressure to bypass that gate. Unit tests deliberately fabricate role attestations to isolate transition logic; the native run supplies actual independent roles for the end-to-end claim. Those evidence classes remain separate.

The native run exposed a concrete platform defect, subsequently fixed and regression-tested. Its source snapshot representation changed during evaluation to include Git modes; the report preserves this fact. Final verification captured a fresh snapshot and did not rewrite old evidence. This is a development run, not a frozen-version benchmark.

The independent parallel run adds seven passing assertions, including two concurrent authors, serialized integration with renewed independent checks/review, final acceptance and a separate expected unavailable-runner failure. Its complete success archive is separate from the deliberately blocked post-success state. The 1570.0479-second success duration includes fixture preparation but excludes the later negative scenario, so even these two successful execution timings have different boundaries. No throughput or speedup claim is justified.

Ten separate decision micro-tests (five guided, five control) all preserved the exhausted budget. Their action was invariant, but the control also passed. This is non-discriminating evidence for wording efficacy; do not add guidance based on it. Those samples are outside the execution benchmark and are documented under microtests/.

Do not optimize wording from these scores. Retain the existing explicit-only invocation policy. Claude Code behavior and a full hermetic paired suite remain unmeasured in this environment.
