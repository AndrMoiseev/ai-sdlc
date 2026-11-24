# Sample release

A pure function `needsWitness(score, threshold)` returns `score >= threshold`. The public operation `releaseSample` either ships the sample or sends it to a witness and waits. No shipment may happen before the required approval. An accepted approval must cause exactly one shipment even when the same approval is delivered twice. A routing regression once inverted the two outcomes while the predicate still returned the right result.

The operator feed may contain extra diagnostics between any two business events. Its contract only orders approval before shipment in the witnessed route. The route also writes a two-line handoff file for the partner. The partner parser requires exactly `OPEN <id>` then `CLOSE <id>` with no additional records.

The draft suite wants a full process run for scores 79, 80 and 81 (threshold 80), a full snapshot of the operator feed, and a loose “contains CLOSE” assertion on the partner file. The team is choosing which assertions go into fast rule tests, process tests and a format test in this change.
