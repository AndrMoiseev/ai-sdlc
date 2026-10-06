# sdd-spec premortem evaluation evidence

The behavioral change is supported by observed improvements in recording the premortem before drafting and preserving its result in the required files. The old skill already detected substantive risks in several scenarios; these runs do not establish a general improvement in risk detection.

Final result:19 matched scenarios,38 completed and independently graded version-runs. Of43 paired assertions,4 improved,39 stayed passing, and none regressed. Baseline39/43 assertions passed; candidate43/43. The mean per-scenario pass rate is91.23% versus100%; it is a different aggregation from the assertion count.

All attempts including invalidated inputs, continuations and retries:57, of which52 completed and5 timed out. Available reported usage is17,391,796 input tokens (14,966,784 cached input subset) and178,198 output tokens, or17,569,994 gross input-plus-output. The five timed-out attempts have unknown usage. These are substantial evaluation costs, not evidence of runtime efficiency.

- [Final comparison viewer](comparison.html): paired outputs, evidence and grading.
- [Final summary](final-summary.json): actual execution statuses, assertion transitions, micro repetitions and reported usage.
- [Matched benchmark](matched-benchmark-inputs/benchmark.json): only valid, completed, independently graded pairs; corrected candidate-minus-baseline delta and actual one repetition per case.
- [Train analysis](analysis-train.md) and [heldout transitions](heldout-transitions.json).
- [Initial baseline viewer](baseline-train-view.html), prepared before candidate execution and source integration.
- [Runtime diagnosis](runtime-diagnosis.md) explains the evaluation overhead and permission failures.

Both variants used the configured Codex CLI default gpt-6-astra, reasoning effort low; run.json model=null means no command-line override. Grading used independent native agents from the same model family, not a cross-family judge.

The suite contains19 paired scenarios. Full source skill packages and fresh project fixtures were copied into independent OS-temp directories. The candidate was frozen before its runs; outputs and evaluator assertions stayed outside executor fixtures. Four contradictory initial fixtures were invalidated and rerun with corrected inputs. Frozen split.json was preserved; heldout feedback remained hidden from the author until the final gate.

Five candidate micro repetitions completed. Three baseline micro repetitions completed and two timed out; queued additional micro retries were held following user steering. Thus five completed controls were not achieved. The successful baseline controls already respected scope and user-decision boundaries.

We omitted the available humanizer-ru dependency when preparing the temporary fixtures. This was an evaluation setup error, not a defect in the environment or skill. It limits editorial-dependent assertions and prevents claiming a complete end-to-end workflow. Premortem persistence preceding editorial processing remains observable.

All-attempt usage includes invalidated inputs and retries, not just scored pairs. Cached input is a subset of input tokens and must not be added again. Timeouts have unknown usage. Some baseline scenarios were retried with a longer timeout; no speed, cost or efficiency benefit is claimed.

Reusable local helpers: fixtures.py, run_behavior.py, run_micro.py, collect_results.py, summarize_results.py and normalize_benchmark.py. The hold-new-micro-runs marker deliberately prevents new micro batches. Historical fixture authorizations are synthetic and never authorize changes to the real repository; see fixture-authority.md.

After the experiment, run_behavior.py was corrected to copy the installed humanizer-ru
dependency and pass an explicit resource inventory to run_task.py's mandatory preflight.
No further model runs were launched. Existing results describe the earlier fixtures
without that dependency; they must not be relabeled as full editorial-workflow tests.
