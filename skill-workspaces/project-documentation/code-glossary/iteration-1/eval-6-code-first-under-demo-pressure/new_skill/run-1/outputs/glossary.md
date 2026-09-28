# Glossary

Terms for Service. Reviewed domains: Sales, Transport, Inventory, and Fulfillment. All supplied implementation in [src/model.ts](../src/model.ts) was read, including declarations and local uses; [README](../README.md) was checked afterward. No tests, separate contracts, domain specifications, or agent instruction files were found in the supplied project. Behavior outside these files is unverified. This is a glossary of the supplied fixture, not a full audit of a larger system.

## Use when writing code

Find the concept in its domain before naming code. Use the permitted name for the identifier's role and scope. Synonyms support recognition and search; they do not authorize new code names. Names marked “by current code” reflect implementation, not an adopted naming convention. Do not choose between competing names without resolving the recorded question.

Reuse existing concepts. Introduce a new domain concept only when a specification explicitly describes it; first compare it with existing concepts. If neither a match nor an explicit specification exists, request clarification. Technical local variables do not need separate domain concepts; follow the existing vocabulary and code style. Names alone, including Account and Position, are not sufficient specifications.

## Sales

The supplied sales operation accepts a customer and returns its identifier as a customer reference.

| Name | Description | Permitted code names | Synonyms |
|---|---|---|---|
| Customer | The entity accepted by `Sales.invoice`, with an `id` and `legalName`; the returned `customerId` copies its `id`. The implementation does not establish additional purchasing or billing rules. [Declaration and use](../src/model.ts#L1-L4). | By current code: `Sales.Customer` — type; `customer` — parameter of `Sales.invoice`; `Customer.id` and `Customer.legalName` — fields; `customerId` — returned reference field. | `Partner` — historical README term for an organization buying goods; equivalence to this code entity and naming status are unconfirmed. |

### Discrepancies and open questions

- [README](../README.md) calls an organization buying goods “Partner,” while the implementation accepts `Customer`. README explicitly predates the implementation and states that no naming convention has been adopted. Does Partner mean exactly this Customer, and which term should a future agreement adopt? Do not introduce a `Partner` identifier on this evidence alone.

## Transport

The supplied transport contract exposes asynchronous sending of a string payload.

| Name | Description | Permitted code names | Synonyms |
|---|---|---|---|
| Client | An object providing `send(payload: string): Promise<void>`. It is a transport interface, distinct from the Sales customer. No protocol, delivery guarantee, or implementation is supplied. [Contract](../src/model.ts#L5-L7). | By current code: `Transport.Client` — interface; `Client.send` — method; `payload` — its string parameter. | None found. |

## Inventory

The supplied operations create and release an order-associated record with an expiry value. No quantity, stock balance, or expiry enforcement is implemented in the supplied code.

| Name | Description | Permitted code names | Synonyms |
|---|---|---|---|
| Order reservation / allocation — terminology unresolved | `reserve` returns the record created by `legacyReserve`, containing `orderId` and `expiresAt`. `Reservation` and `Allocation` declare the same fields. `legacyReserve` sets `expiresAt` to `Date.now() + 60000`; `release` accepts a `Reservation` and returns its order identifier as `releasedOrder`. These operations show overlapping usage but do not establish whether a business distinction is intended. [Declarations and operations](../src/model.ts#L8-L14). | Not determined for the concept: a naming choice is required. Observed type names are `Inventory.Reservation` and `Inventory.Allocation`; do not treat them as freely interchangeable choices for new code. Existing contract field names, by current code: `Reservation.orderId`, `Reservation.expiresAt`, `Allocation.orderId`, `Allocation.expiresAt`; `releasedOrder` — result of `Inventory.release`. | `Reservation` / `Allocation` — competing observed names, normative status unresolved. The function name `legacyReserve` suggests legacy usage but does not establish that `Allocation` is deprecated. |

### Discrepancies and open questions

- Are Reservation and Allocation one concept with two names, or distinct concepts with currently identical structure? If one concept, which name is canonical? No adopted convention resolves this choice.
- [README](../README.md) states that inventory allocation lasts forever. Current creation code instead assigns an expiry timestamp 60 seconds after the current clock reading. No code here enforces expiry or mutates inventory during release. Is the intended rule a time-limited reservation, and where should enforcement live? The README statement cannot establish current runtime behavior.

## Fulfillment

The supplied dispatch operation groups shipment identifiers and produces one result per identifier.

| Name | Description | Permitted code names | Synonyms |
|---|---|---|---|
| Dispatch batch | A record holding `shipmentIds`; `Fulfillment.dispatch` maps each identifier to `{ id, sent: true }`. The supplied implementation returns these results without a transport call, so it does not prove actual shipment or delivery. [Declaration and use](../src/model.ts#L15-L18). | By current code: `Fulfillment.DispatchBatch` — interface; `DispatchBatch.shipmentIds` — identifier-list field; `batch` — parameter of `Fulfillment.dispatch`. | None found. |

## Requested concepts awaiting definition

These are questions from the user request, not established domain entries. Neither appears in the supplied implementation or README; their domain, meaning, relationships, and permitted code names are unconfirmed.

- **Account:** What does an Account represent in this project, which domain owns it, and what behavior distinguishes it from existing concepts? Please supply its definition or specification before introducing identifiers.
- **Position:** What does a Position represent in this project, which domain owns it, and what behavior distinguishes it from existing concepts? Please supply its definition or specification before introducing identifiers.

## Documentation gaps and agent entry point

No separate domain document describing invariants or scenarios was supplied. The code links above are the available behavioral evidence; this glossary does not invent missing requirements.

Only `docs/glossary.md` is created for this task. No agent instruction file exists in the supplied project. Suggested exact addition to README, the existing documentation entry point:

`Before introducing or changing domain names in code, read the [glossary](docs/glossary.md): use the permitted names; introduce new concepts only when a specification explicitly describes them.`

This pointer is proposed here, not installed in README; agents must be directed to read the glossary until it is added.
