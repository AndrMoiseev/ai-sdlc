# Glossary

Terms for Service. Reviewed domains: Sales, Transport, Inventory, and Fulfillment; all declarations and uses present in [src/model.ts](../src/model.ts), checked against [README.md](../README.md). No existing glossary or project instruction file was found. Tests, external consumers, persistence, and runtime integrations are not present in the supplied project and were not verified. This is a glossary of the supplied code, not a full system audit.

## Use when writing code

Before naming a domain concept, find it in the relevant domain and use the allowed name for the identifier's role. Synonyms help locate and recognize concepts; they do not authorize new code names. Introduce a new domain concept only when a specification explicitly describes it, after checking for an existing equivalent. If neither an equivalent nor an explicit specification exists, clarify the specification. Technical local variables do not require separate domain entries; follow existing vocabulary and code style. Where competing names remain unresolved, obtain a naming decision before introducing another name.

No naming convention has been adopted, according to the README. “By current code” below identifies a consistently observed name, rather than an approved project-wide convention.

## Sales

Organization identity used by the invoicing operation; distinct from the calling client in Transport.

| Name | Description | Allowed code names | Synonyms |
|---|---|---|---|
| Customer / Partner — terminology unresolved | The README describes an organization buying goods as Partner. The implementation represents a Customer with `id` and `legalName`; `invoice` takes that object and returns its ID as `customerId`. The code does not establish any further buying or invoicing behavior. [Code](../src/model.ts#L1), [README](../README.md#L2). | Undetermined: a choice is required between the documented and implemented terminology. Observed identifiers are listed below. | `Partner`: documented business name, status unresolved; README explicitly predates the implementation. `Customer`: implementation name, status unresolved relative to Partner. |

### Discrepancies and open questions

- Is the organization called Partner in the README the same concept as `Sales.Customer`, and which name should be canonical? Observed identifiers: `Sales.Customer` (type), `Customer.id` and `Customer.legalName` (fields), `Sales.invoice` (operation), `invoice.customer` (parameter), and `invoice` result `customerId` (field). [Implementation](../src/model.ts#L1) and [older documentation](../README.md#L2) disagree; neither provides an adopted naming decision.

## Transport

Outbound payload sending through a callable interface; no implementation is supplied.

| Name | Description | Allowed code names | Synonyms |
|---|---|---|---|
| Client | Interface for sending a string payload asynchronously, with completion represented by `Promise<void>`. It is a transport endpoint abstraction, distinct from the Sales organization. Delivery guarantees and transport protocol are not specified. [Contract](../src/model.ts#L5). | By current code: `Transport.Client` — interface; `Client.send` — operation; `send.payload` — string parameter. | None found. |

## Inventory

Creation and release of order-associated reservation records. The supplied functions expose data transformations, not storage or stock mutation.

| Name | Description | Allowed code names | Synonyms |
|---|---|---|---|
| Reservation / Allocation — terminology unresolved | An order-associated record with `orderId` and `expiresAt`. `reserve` returns the result of `legacyReserve`: the former declares `Reservation`, the latter `Allocation`, and both interfaces have identical fields. `release` accepts a Reservation and returns its order ID as `releasedOrder`. [Code](../src/model.ts#L8). | Undetermined: a choice is required for the competing record type names. Observed roles are listed below; their presence does not make the two type names interchangeable names for new code. | `Reservation` and `Allocation`: observed implementation names, canonical status unresolved. `legacyReserve` labels an operation as legacy; this does not establish that Allocation is formally deprecated. |
| Reservation expiry | The `expiresAt` field is initialized by `legacyReserve` to `Date.now() + 60000`, a timestamp 60 seconds after creation. `reserve` uses that same creation path. No expiry check or automatic release is implemented in the supplied code. [Creation and use](../src/model.ts#L9). | By current code: `Inventory.Reservation.expiresAt` and `Inventory.Allocation.expiresAt` — timestamp fields on the respective observed types. | None found. |

### Discrepancies and open questions

- Should `Inventory.Reservation` or `Inventory.Allocation` be the canonical record type, or do they represent intended distinctions not expressed in this implementation? Observed names: `Reservation` and `Allocation` (types), each type's `orderId` and `expiresAt` (fields), `Inventory.reserve` and `Inventory.legacyReserve` (creation operations), `Inventory.release` (operation), `release.reservation` (parameter), and release result `releasedOrder` (field). The shared creation path is evidence of overlapping current behavior, not an adopted terminology decision. [Code](../src/model.ts#L8).
- The [README](../README.md#L2) says allocation lasts forever, but [creation code](../src/model.ts#L12) assigns an expiry 60 seconds ahead. Is this timestamp intended to enforce expiry, or is indefinite validity still the intended requirement? The supplied implementation does not enforce expiration. No current domain document explaining the intended lifetime or release semantics was found.

## Fulfillment

Grouping shipment identifiers and producing dispatch results.

| Name | Description | Allowed code names | Synonyms |
|---|---|---|---|
| Dispatch batch | A group of shipment IDs supplied to `dispatch`. The operation maps each ID to an object containing that ID and `sent: true`; the supplied implementation does not perform or verify shipment delivery. This concept is present in code but absent from the README. [Code](../src/model.ts#L15). | By current code: `Fulfillment.DispatchBatch` — interface; `DispatchBatch.shipmentIds` — field; `Fulfillment.dispatch` — operation; `dispatch.batch` — parameter. | None found. |

## Documentation gaps

No separate current domain description, specification, naming decision, or tests were supplied. Detailed business rules beyond the observations above remain unverified. The README is explicitly older than the implementation, so its claims are preserved as discrepancies rather than treated as current implemented behavior.
