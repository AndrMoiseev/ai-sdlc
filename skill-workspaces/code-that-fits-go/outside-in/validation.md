# Outside-in Go example validation

- Runtime: go1.26.5 windows/amd64, GOTOOLCHAIN=local, each fixture module declares go 1.22. Go 1.22 itself was not installed/executed.
- Package changes: only references/outside-in-tdd/examples/go-testing.md and go-net-http-testing.md.
- Published Go fences formatted with gofmt, then extracted again for execution.
- Green fixtures: unit (Examples 3/4), spy-before, spy-middle (representation refactor only), spy-after, http-before, http-after. All `go test -count=1 ./...` commands passed.
- Supplemental unit checks: exact capacity, excessive quantity, zero/negative quantity, full day, invalid date, blank email, different day, read/add errors and no write after failed read.
- Supplemental HTTP checks: malformed JSON, JSON null, empty object, zero/negative/fractional/null quantity, invalid date, blank email, nonstring name, trailing JSON object, valid stored result, nil-name normalization, exact capacity, over capacity.
- Red probes: home-only route fails POST boundary test (404); deliberate shli@example.org branch fails fourth table row; unrelated 409 passes original status-only test and fails strengthened cause-specific test. Logs saved beside this report.
- The expected red stages are isolated fixtures; they are not broken shipped examples.
- SHA256 source contents unchanged from pre-edit capture:
  - csharp-aspnetcore-xunit.md: F6A1B5405D18A67E271291B0E0D9A9EA384A76C6F338ABADDF25B92A833A2840
  - kotlin-junit5.md: C9ADDA654A19981FEEDC47E98BB3CBAEDBDC5A4B52BE4C46F1290C22A74E7668
  - kotlin-ktor-junit5.md: BF4DBCAE588CB216E255BC0DD756FA7D9FB6744716FDEDC4B6FE15BBB6F7E41E
- Outline preserves source Examples 3/4/6 in unit file and 1/2/5 plus Changes Made in HTTP file. Source bad/good progression, AAA, parameter rows, and before/after postconditions and spy remain.
- Fixtures/build data outside skill. Go caches in system temporary code-that-fits-go-cache and code-that-fits-go-modcache. No Python execution added.
- Environment limitation: Go reports access denied writing its pre-existing user telemetry upload token even with process GOTELEMETRY=off. Green command exit status remains zero; tests run successfully. No global setting changed.
- Concurrency/persistence limitation explicitly documented: sequential fakes; no production database, deployment smoke test, or real atomic capacity transaction claimed.

Independent read-only review of API and encapsulation Go additions: no blocking issue found. Source heading hierarchy is preserved, with the encapsulation parameterized test explicitly routed to its companion file. Package/import assembly instructions are complete. Go zero values, same-package mutation, discarded errors, optional lookup protocol, nil dependency contracts, slice ownership, and conservative scheduler limits are explicitly described.
