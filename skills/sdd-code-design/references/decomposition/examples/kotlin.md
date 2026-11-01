# Decomposition Examples — Kotlin

Kotlin/JVM additions to this fork, following the original examples and refactoring stages; these are not code from the book. The blocks are excerpts from independent stages, using JDK `java.time` and `java.util.UUID`. `ReservationDto` contains nullable input strings; `Reservation` contains parsed values. `ReservationsRepository` provides reads and writes, and `BookingResponse` represents the endpoint outcome. No web framework is required.

## Example 1: Extracting a Low-Cohesion Guard-Clause Block

### Before

The reservation endpoint mixes date parsing, email presence, and quantity checks with repository I/O. Extract that cohesive input-checking block first: it depends only on the request and can be checked independently of storage.

### After

```kotlin
private fun parseAtOrNull(raw: String?): LocalDateTime? = try {
    raw?.let(LocalDateTime::parse)
} catch (_: DateTimeParseException) {
    null
}

private fun isValid(dto: ReservationDto): Boolean =
    parseAtOrNull(dto.at) != null && dto.email != null && dto.quantity > 0

fun post(dto: ReservationDto, repository: ReservationsRepository): BookingResponse {
    if (!isValid(dto)) return BookingResponse.BadRequest
    val at = LocalDateTime.parse(dto.at)
    val reservations = repository.readReservations(at.toLocalDate())
    val reservedSeats = reservations.sumOf { it.quantity.toLong() }
    if (reservedSeats + dto.quantity > 10L) return BookingResponse.NoCapacity
    val reservation = Reservation(
        at, requireNotNull(dto.email), dto.name.orEmpty(), dto.quantity,
    )
    repository.create(reservation)
    return BookingResponse.NoContent
}
```

### Changes Made

1. Extracted the guards into `isValid`, leaving the storage sequence visible in `post`.
2. Used a private top-level function because no instance state is needed; Kotlin does not require a static utility class.
3. Replaced several caller decisions with the named `isValid` check. The non-null parameter expresses the endpoint's request-object requirement, while nullable fields still need runtime checks.

---

## Example 2: Fixing Feature Envy by Moving the Method

### Problem with Example 1

`isValid` reads only `ReservationDto`. Keeping this behavior with the type can make its ownership clearer. A top-level function is not inherently a Kotlin design smell; the reason to move it is cohesion.

### After

```kotlin
data class ReservationDto(
    val at: String?,
    val email: String?,
    val name: String?,
    val quantity: Int,
) {
    internal val isValid: Boolean
        get() = parseAtOrNull(at) != null && email != null && quantity > 0
}
```

The corresponding endpoint guard becomes:

```kotlin
if (!dto.isValid) return BookingResponse.BadRequest
```

### Changes Made

1. Moved the check onto the input type whose values it understands.
2. Used a computed property for this inexpensive, deterministic observation; malformed dates produce `false` through `parseAtOrNull`.
3. Kept visibility `internal` while the behavior is needed only inside the module.
4. Removed the separate `isValid(dto)` helper; no utility object is needed.

### Still Not Good Enough

The Boolean discards the parsed timestamp. `post` still parses again and uses `requireNotNull` to recover an email the compiler cannot infer from `isValid`. Return a parsed `Reservation?` instead; Example 5 shows that conversion. A sealed result is appropriate when callers need specific validation errors.

---

## Example 3: Sequential Composition in a Domain Query

### The `WillAccept` Pipeline

The Kotlin `willAccept` query constructs a seating, filters overlapping reservations, allocates tables, then checks the remaining capacity. `Seating` holds `start`, `end`, and its `duration`; `Table` is a value with available `seats` and a `communal` flag.

```kotlin
fun Seating.overlaps(other: Reservation): Boolean {
    val otherSeating = Seating(duration, other)
    return start < otherSeating.end && otherSeating.start < end
}

class MaitreD(tables: List<Table>, private val duration: Duration) {
    private val tables = tables.toList()

    fun willAccept(
        now: LocalDateTime,
        existing: List<Reservation>,
        candidate: Reservation,
    ): Boolean {
        if (candidate.at < now) return false
        val seating = Seating(duration, candidate)
        val overlapping = existing.filter { seating.overlaps(it) }
        val available = allocate(overlapping) ?: return false
        return available.any { it.fits(candidate.quantity) }
    }

    private fun allocate(reservations: List<Reservation>): List<Table>? {
        val available = tables.toMutableList()
        for (reservation in reservations) {
            val index = available.indexOfFirst { it.fits(reservation.quantity) }
            if (index < 0) return null
            val table = available.removeAt(index)
            if (table.communal) {
                available.add(index, table.copy(seats = table.seats - reservation.quantity))
            }
        }
        return available
    }
}
```

This is a conservative first-fit policy: each overlapping reservation holds its allocation throughout the candidate's interval. A communal table of four can therefore reject a party of two at 19:00 when two existing parties of two occupy 18:00–20:00 and 20:00–22:00. Actual occupancy would permit that booking; use this policy only if that conservatism is accepted. It is not a general scheduling optimizer.

### Why It Works

- The query receives time as a value and performs no I/O.
- The output of `filter` feeds `allocate`, whose result feeds `any`.
- The constructor snapshots the table list; later edits to the caller's list cannot change the policy. Allocation mutates only its fresh `available` list.
- Half-open seating intervals allow an arrival exactly at a previous departure. Pure-query tests can check this boundary without mocks.

---

## Example 4: Replacing Nested Composition with Sequential Composition

### Before (Bad — do not write code like this)

```kotlin
fun post(dto: ReservationDto, manager: RestaurantManager): BookingResponse {
    val reservation = dto.parse() ?: return BookingResponse.BadRequest
    // check also saves an accepted reservation: its name conceals a write.
    if (!manager.check(reservation)) return BookingResponse.NoCapacity
    return BookingResponse.NoContent
}
```

The short caller hides the storage operation inside `manager.check`. Returning a Boolean is not itself the problem; a query-like name conceals an effect that the reader needs to understand.

### After

```kotlin
fun post(
    dto: ReservationDto,
    clock: Clock,
    repository: ReservationsRepository,
    maitreD: MaitreD,
): BookingResponse {
    val id = dto.parseId() ?: UUID.randomUUID()
    val reservation = dto.parse(id) ?: return BookingResponse.BadRequest
    val existing = repository.readReservations(reservation.at.toLocalDate())
    if (!maitreD.willAccept(LocalDateTime.now(clock), existing, reservation)) {
        return BookingResponse.NoCapacity
    }
    repository.create(reservation)
    return BookingResponse.Created(reservation)
}
```

The excerpt assumes one seating day contains every potentially overlapping reservation. A storage implementation must serialize the read/decision/write sequence, for example with a transaction that prevents concurrent conflicting capacity checks.

### Changes Made

1. Removed the manager call that hid persistence.
2. Made time and ID generation visible at the effect boundary; a supplied `Clock` makes time controllable in tests.
3. Kept `willAccept` deterministic and placed `repository.create` after that decision.
4. Exposed parsing, reading, deciding, and saving in execution order.

---

## Example 5: Progressive Disclosure Before and After

### Before (Original `Post`, listing 6.9)

The original example exposes request presence, date syntax, email presence, quantity, name defaulting, capacity, and success together. In Kotlin the non-null request parameter handles request-object presence at the type boundary; nullable transport fields still carry the remaining input decisions.

### After `Validate` Extraction

With Kotlin's `parse` extraction, the caller handles a parsed value or failure, capacity, and success. It no longer repeats date parsing or recovers individual nullable fields.

### Zooming Into `Validate`

Keep the related input decisions inside the conversion. This excerpt extends the DTO used in the ID-aware endpoint stage; `parseId` separately parses an optional incoming ID.

```kotlin
fun ReservationDto.parse(id: UUID): Reservation? {
    val parsedAt = parseAtOrNull(at) ?: return null
    val parsedEmail = email ?: return null
    if (quantity <= 0) return null
    return Reservation(parsedAt, parsedEmail, name.orEmpty(), quantity, id)
}
```

### What This Shows

The input decisions remain present, grouped under `parse`. The endpoint and parser each expose one coherent level of detail, so a reader can understand the orchestration before zooming into input conversion.
