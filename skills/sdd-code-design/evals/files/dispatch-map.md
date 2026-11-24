# Dispatch service snapshot

This is the service owner's inventory for release 41. Paths and snippets show
the deployed composition and the tests in the same revision.

| Path | Excerpt |
| --- | --- |
| `app/boot.ts` | `register("/dispatch", new DispatchHandler(new QueueDispatch(queue, settings)))` |
| `app/dispatch-handler.ts` | `post(req) { return this.dispatch.schedule(req.ticket) }` |
| `queue/dispatch.ts` | `schedule(ticket) { return this.queue.put(ticket, SystemClock.now() + this.settings.delay) }` |
| `legacy/dispatch.ts` | `LegacyDispatch.schedule(ticket)` puts the ticket on a different queue immediately. The migration inventory lists no registered route using this implementation. |
| `test/dispatch-window.spec.ts` | `"POST /dispatch schedules ten minutes after acceptance"` posts a ticket and compares its visible due time with the acceptance instant plus ten minutes. |
| `test/app-fixture.ts` | The public test constructs seven shared infrastructure objects and replaces the global clock. The on-call log records intermittent cross-test clock changes. |
| `git log -- queue/dispatch.ts test/dispatch-window.spec.ts` | `b61 Make the acceptance clock determine dispatch time (OPS-18)`. The issue copy in the inventory only contains the title. |

The search index also contains 90 unrelated handlers and an unused draft for a
new dispatcher. The incident ticket says the actual scheduled time was late. It
does not contain an acceptance timestamp, a due timestamp or a clock trace.
