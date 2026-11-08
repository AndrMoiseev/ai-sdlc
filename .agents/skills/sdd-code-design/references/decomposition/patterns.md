# Decomposition Patterns

Recomposition strategies: once you split a block, how do you put the pieces back together so the whole still fits in your head?

## Pattern: Sequential Composition

### Intent

Chain pure transformations so the output of one becomes the input of the next. Make the data flow visible without hidden effects or time-dependent reads.

### When to Use

- The method performs a pipeline of transformations over data.
- Each step computes deterministically from explicit inputs without observable side effects.
- You want the reader to see the full pipeline without drilling into dependencies.

### Structure

```csharp
var a = StepOne(input);
var b = StepTwo(a);
var c = StepThree(b);
return Finalise(c);
```

### Example

```csharp
// From the restaurant code base: WillAccept composed sequentially from
// constructor, Where + Overlaps, Allocate, Any + Fits — pure transformations.
var seating = new Seating(SeatingDuration, candidate);
var relevantReservations = existingReservations.Where(seating.Overlaps);
var availableTables = Allocate(relevantReservations);
return availableTables.Any(t => t.Fits(candidate.Quantity));
```

### Benefits

- The reader can trace data flow top-to-bottom.
- Each step is testable in isolation.
- Deterministic steps can be reasoned about from their explicit inputs.

### Considerations

- A CQS Query does not change observable state, but it can read a database or clock. Its result can depend on when it runs; absence of writes does not establish purity. Keep such reads explicit in the effectful orchestration and pass their results to pure transformations.
- When moving a read or effect, apply [Preserve behavior when moving effects](#preserve-behavior-when-moving-effects).
- Works best when types chain cleanly; introduce small value objects when signatures don't line up.

---

## Pattern: Nested Composition (Use Sparingly)

### Intent

Compose objects by embedding one inside another (Composite, most Gang-of-Four patterns). Shown here so you recognise it and know when *not* to reach for it.

### Why It's Problematic

Every nested object adds side effects to what the reader must remember. By the outer shell you are tracking eight or nine chunks — past the memory limit. Query-looking methods at the top may hide Commands deep in the tree (smell D6).

### When It Is Acceptable

- Domain *is* a tree (UI widgets, filter chains, AST nodes).
- You deliberately want polymorphic substitution at a node.
- Otherwise prefer sequential composition and keep any tree shallow.

---

## Pattern: Functional Core, Imperative Shell

### Intent

Implement complex logic as pure functions; concentrate nondeterminism (time, GUIDs, random, I/O) and side effects at the system's edge.

### When to Use

- Any non-trivial domain logic.
- Controllers, message handlers, and `Main` — these are the shell.
- Whenever you want a function to be easy to test and free of mocks.

### Structure

```csharp
// Shell: gather inputs (nondeterministic), call pure core, apply side effect.
public async Task<ActionResult> Handle(SomeDto dto)
{
    var now = DateTime.Now;                       // nondeterministic
    var id = Guid.NewGuid();                      // nondeterministic
    var state = await repo.Read(...);              // I/O

    var decision = PureCore(now, id, state, dto); // pure

    if (decision.IsAccepted)
        await repo.Write(decision.Result);         // side effect
    return decision.ToResponse();
}
```

### Example

```csharp
// The WillAccept pure function decides; the Post shell performs the I/O.
[HttpPost]
public async Task<ActionResult> Post(ReservationDto dto)
{
    if (dto is null) throw new ArgumentNullException(nameof(dto));
    var id = dto.ParseId() ?? Guid.NewGuid();
    Reservation? r = dto.Validate(id);
    if (r is null) return new BadRequestResult();

    var reservations = await Repository
        .ReadReservations(r.At)
        .ConfigureAwait(false);

    if (!MaitreD.WillAccept(DateTime.Now, reservations, r))
        return NoTables500InternalServerError();

    await Repository.Create(r).ConfigureAwait(false);
    return Reservation201Created(r);
}
```

### Benefits

- Pure core is trivial to test (no mocks, no fakes).
- The shell exposes the effect protocol; its size follows the ordering and recovery responsibilities it owns.
- Aligns with fractal architecture — the shell is the trunk, the core is where the branches live.

### Considerations

- Requires discipline to keep the core pure; resist injecting clocks or random generators into it — pass those values in.
- Works in C# just as well as in functional languages.

### Preserve behavior when moving effects

When extracting a calculation moves a read, write or resource boundary, trace
the affected path before and after. Preserve the behavior required by the task:

- **Conditional and lazy reads:** keep short-circuiting, streaming and the point
  at which the next input is consumed. Reading all inputs first can change failure
  order, memory use and I/O cost.
- **Failure handling:** keep each operation under the handler that owns its retry,
  translation or propagation. Moving a read across a handler can change the result.
- **Resource ownership:** identify who acquires, uses and releases each resource.
  A helper must not close a stream before its consumer finishes or move cleanup
  outside the required scope.
- **Consistency and recovery:** retain required atomic checks, transaction
  boundaries, acknowledgement order, cancellation and recovery behavior. A value
  read earlier may be stale when the decision is applied.

For example, an operation reads one input record, computes a publication decision,
and publishes it before reading the next record. Publication failure must stop
consumption. Materializing every record before calling the pure calculation would
violate that contract. Keep consumption and publication interleaved; extract the
decision over the current record. An acceptance check can make publication fail
and verify that no subsequent record is consumed and the required error escapes.

Choose checks for the contract at risk, including resource cleanup or transaction
behavior when applicable. Private helper-call order needs no assertion unless it
protects required behavior. The shell may still own substantial retry or recovery
logic; removing domain decisions does not remove those responsibilities.

---

## Pattern: Referential Transparency Replacement

### Intent

Reason about a pure function call by mentally replacing it with its return value, collapsing arbitrary internal complexity to a single chunk.

### When to Use

- Reading or reviewing code that calls a pure function.
- Deciding whether a helper can be treated as one chunk — it can, if it is pure.

### Structure

```csharp
// Once you know Foo(x, y) returns 42, treat the expression as 42.
var result = Bar(Foo(x, y), z);   // in your head: Bar(42, z)
```

### Benefits & Considerations

- Works only if the function is deterministic *and* side-effect-free.
- Breaks the moment a "pure" function starts reading wall-clock time or mutating shared state.
- Pure functions always compose when output and input types line up.

---

## Pattern: Concept Inventory (Decomposition Heuristic)

### Intent

A thinking tool: list the independent decisions, state transitions, dependencies, and hidden effects a reader must track at one zoom level. When unrelated concepts compete for attention, decompose by responsibility.

### When to Use

- Before adding a branch to an already dense method.
- When a method feels heavy but the metric is still within limits.
- When picking the first block to extract.

### Example

For the `Post` method after extracting `Validate()`, the caller exposes four concepts: `dto NULL`, `Validate NULL`, `TOO LITTLE CAPACITY`, and `HAPPY PATH`. The input-validation details remain at the lower zoom level.

### Considerations

- Heuristic, not a metric or a fixed item limit. Use alongside cyclomatic complexity, state interaction, and coupling.
- Catches hidden chunks (side effects buried in Queries) that metrics miss.

---

## Pattern Selection Guide

| Situation | Recommended Pattern |
|-----------|--------------------|
| Pipeline of data transformations | Sequential Composition |
| Controller or message handler | Functional Core, Imperative Shell |
| Complex domain logic | Pure functions + Referential Transparency Replacement |
| Method feels crowded | Concept Inventory diagnosis |
| Domain operations expose data representation | [Stratified Design](stratified-design.md) |
| You are tempted to nest objects deeply | Reconsider — prefer sequential |
