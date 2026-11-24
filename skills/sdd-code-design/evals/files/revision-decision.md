# Notebook publishing

These are the operations clients actually use and an excerpt from their implementation.

```ts
type Phase = "draft" | "imported-lock" | "published";
type Revision = { id: string; phase: Phase };
type Reply = { kind: "ok" | "locked" };
class Notebook {
  // Constructor hydrates persisted revisions, including old imported locks.
  constructor(private revisions: Revision[], private published: string[]) {}
  publish(id: string): Reply {
    const r = this.revisions.find(it => it.id === id)!;
    if (!permitted(r.phase)) return { kind: "locked" };
    r.phase = "published";
    this.published.push(id);
    return { kind: "ok" };
  }
  phaseOf(id: string): Phase { return this.revisions.find(it => it.id === id)!.phase; }
  feed(): readonly string[] { return this.published; }
}
function permitted(p: Phase): boolean { return p === "draft"; }
```

A persisted imported lock is valid. There is no user operation to create one. Clients rely on locked revisions staying locked, reporting `locked`, and never appearing in the publication feed. Draft publication must still work. The existing tests exercise the table in `permitted` and construct a synthetic expected publication feed. Those tests stay green if the conditional in `publish` is bypassed. The team has one focused test change available and doesn't want new product operations solely for fixtures.
