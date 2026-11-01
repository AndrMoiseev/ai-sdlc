# API Design Examples: Kotlin

Fork addition: Kotlin/JVM counterparts to the C# examples, in the same order. Snippets are alternatives or excerpts, not a single source file. They use `java.time.LocalDateTime`, `LocalTime`, `Duration`, and `java.util.UUID`. `Reservation` is an immutable value with `at: LocalDateTime` and positive `quantity: Int`; immutable `Table` values expose `fits`, `isCommunal`, and `reserve`, which returns a new table. Constructor, repository, and controller excerpts use those domain types. No web framework is required.

## Bad Examples

### Comment Explaining What the Code Does

Inside the reservation decision:

```kotlin
// Reject reservation if it's outside of opening hours
if (candidate.at.toLocalTime() < opensAt ||
    lastSeating < candidate.at.toLocalTime()
) return false
```

**Problems**:
- The comment and conditional can drift apart.
- The reader still has to interpret the comparisons to verify the comment.
- Other decisions cannot reuse this unnamed check.

### Stringly Typed / X-Out Failure

```kotlin
interface Things {
    fun doSomething(a: String, b: String): String
    fun getSomething(c: String): String
    fun makeSomething(d: String, e: String): String
}
```

**Problems**:
- Replacing the names with `xxx` leaves nearly identical signatures.
- `String` conveys no domain meaning or value constraints.
- The compiler accepts swapped arguments with the same type.

### CQS Violation

A member of a class owning `store: MutableList<Reservation>`:

```kotlin
fun addReservationAndGetCount(reservation: Reservation): Int {
    store += reservation
    return store.size
}
```

**Problems**:
- The `Int` return type does not reveal the mutation.
- Adding a reservation and reading the count are coupled.
- A caller wanting only the count must also add a reservation.

### Swiss Army Knife Constructor

```kotlin
class ReservationsController(
    private val repository: ReservationsRepository,
    opensAt: LocalTime,
    lastSeating: LocalTime,
    seatingDuration: Duration,
    tables: List<Table>,
) {
    private val maitreD = MaitreD(opensAt, lastSeating, seatingDuration, tables)
}
```

**Problems**:
- The controller knows the policy's constructor shape, so configuration changes reach it.
- Restaurant configuration leaks into the HTTP boundary.
- The constructor asks for policy fragments instead of the policy dependency.

## Good Examples

### MaitreD as Affordance

The policy below uses the allocation function shown later. This excerpt assumes same-day opening hours, a fixed seating duration, and accepted existing reservations that its allocation strategy can accommodate. It conservatively treats every overlapping reservation as occupying its table throughout the candidate's entire seating interval. Staggered reservations can therefore cause it to reject a feasible booking.

```kotlin
class MaitreD(
    private val opensAt: LocalTime,
    private val lastSeating: LocalTime,
    private val seatingDuration: Duration,
    tables: List<Table>,
) {
    private val tables = tables.toList()

    init {
        require(opensAt <= lastSeating)
        require(!seatingDuration.isZero && !seatingDuration.isNegative)
    }

    fun willAccept(
        now: LocalDateTime,
        existingReservations: List<Reservation>,
        candidate: Reservation,
    ): Boolean {
        if (candidate.at <= now || isOutsideOfOpeningHours(candidate)) return false
        val overlapping = existingReservations.filter { reservation ->
            reservation.at < candidate.at.plus(seatingDuration) &&
                candidate.at < reservation.at.plus(seatingDuration)
        }
        return allocate(tables, overlapping).any { it.fits(candidate.quantity) }
    }

    private fun isOutsideOfOpeningHours(candidate: Reservation): Boolean =
        candidate.at.toLocalTime() !in opensAt..lastSeating
}
```

**Why it works**:
- `LocalTime`, `Duration`, `Reservation`, and `Table` distinguish configuration and domain values. `MaitreD` names a responsibility recognizable to domain experts.
- The constructor requires the policy inputs and copies the table list; immutable table values prevent callers from changing the policy indirectly.
- `willAccept` is a query by contract and implementation. Kotlin's `Boolean` return type alone does not establish purity.
- The X-Out exercise still distinguishes configuration from a decision over reservations. Named arguments can make calls with two `LocalTime` values clearer.

### Well-Named Method Replacing a Comment

Alternative excerpts from `willAccept`; the named helper is defined on `MaitreD` above:

```kotlin
// Before: the comment carries the intent.
// Reject reservation if it's outside of opening hours
if (candidate.at.toLocalTime() < opensAt ||
    lastSeating < candidate.at.toLocalTime()
) return false

// After: the helper carries the intent.
if (isOutsideOfOpeningHours(candidate)) return false
```

**Why it works**:
- The compiler checks calls to the helper when it is renamed.
- Other branches can reuse the same opening-hours decision.
- The calling code communicates intent without repeating time comparisons.

### Query With No Observable Side Effects (CQS)

A private top-level function in the same Kotlin file as `MaitreD`. As in the source example, it allocates already accepted reservations in order; it is not an optimal packing algorithm. `Table.reserve` returns an immutable table with fewer available seats, including zero when a communal table is full.

```kotlin
private fun allocate(
    tables: List<Table>,
    reservations: List<Reservation>,
): List<Table> {
    val availableTables = tables.toMutableList()
    for (reservation in reservations) {
        val table = availableTables.firstOrNull { it.fits(reservation.quantity) }
        if (table != null) {
            availableTables.remove(table)
            if (table.isCommunal) {
                availableTables += table.reserve(reservation.quantity)
            }
        }
    }
    return availableTables.toList()
}
```

**Why it works**:
- Only the local list changes; reserving communal seats creates a new table value.
- A `List<Table>` return exposes a read-only collection interface and suits the query contract.
- Purity comes from ownership and immutable elements. Kotlin's read-only `List` type by itself does not guarantee an immutable backing collection.

### Nullability Expressed in the Type (Poka-Yoke + Hierarchy)

```kotlin
interface ReservationsRepository {
    suspend fun create(reservation: Reservation): Unit
    suspend fun readReservations(at: LocalDateTime): List<Reservation>
    suspend fun readReservation(id: UUID): Reservation?
}
```

**Why it works**:
- `Reservation?` makes a missing result explicit and forces nullable handling at Kotlin call sites.
- The method name needs no `OrNull` suffix to communicate absence.
- With names hidden, `Unit`, `List<Reservation>`, and `Reservation?` still distinguish the command, collection query, and lookup query. `suspend` expresses a suspendable call without returning a C#-style `Task`.

### Dependency as a Whole Object (Poka-Yoke at the Seam)

```kotlin
class ReservationsController(
    private val repository: ReservationsRepository,
    private val maitreD: MaitreD,
)
```

**Why it works**:
- The controller receives `MaitreD` instead of its configuration fields.
- Changes to the policy's constructor stay in the composition root.
- The policy copies its collection and holds immutable values, so callers can safely share it.
- Only composition knows raw opening hours, duration, and table configuration.

## Refactoring Walkthrough

### Before

Business logic hard-coded in a Boolean decision inside the controller:

```kotlin
val reservedSeats = reservations.sumOf { it.quantity.toLong() }
if (10 < reservedSeats + r.quantity) return false
```

### After

The decision is delegated to the domain policy. The caller supplies `now`, making the time dependency explicit:

```kotlin
if (!maitreD.willAccept(now, reservations, r)) return false
```

### Changes Made

1. **Extracted a domain class** (`MaitreD`) whose name matches the restaurant responsibility.
2. **Replaced the magic number (10) with typed configuration** (`List<Table>`), so restaurants can supply their own validated table values.
3. **Named the decision `willAccept`** and implemented it as a query. The implementation preserves state; a Boolean return type alone cannot prove that property.
4. **Moved allocation to a private query** (`allocate`) that changes a local copy and returns available tables. A top-level private function is sufficient in Kotlin.
5. **Injected `MaitreD` through the constructor**, keeping the controller independent of how the policy is configured.
