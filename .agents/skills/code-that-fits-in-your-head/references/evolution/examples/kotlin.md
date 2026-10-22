# Evolution Examples — Kotlin

Kotlin/JVM additions to this fork, following the original examples and migration stages; these are not code from the book. The blocks are independent stage excerpts using JDK `LocalDate`, `LocalDateTime`, and `UUID`. `HomeDto` contains link values, and repository examples use parsed reservation values. Scheduling excerpts assume reservations already have assigned tables. No web or test framework is required.

## Example 1: Calendar Feature Flag

The calendar feature can be integrated continuously while its links remain hidden until release. Keep the flag temporary and make both configurations observable in tests.

### Before (no calendar)

```kotlin
fun home(): HomeDto = HomeDto(listOf(createReservationsLink()))
```

The home resource exposes only the reservations link.

### With Feature Flag

```kotlin
fun home(enableCalendar: Boolean): HomeDto = HomeDto(buildList {
    add(createReservationsLink())
    if (enableCalendar) {
        add(createYearLink())
        add(createMonthLink())
        add(createDayLink())
    }
})
```

### Wiring the Flag

Pass the Boolean directly. A wrapper type is unnecessary for ordinary Kotlin function composition. Read configuration at the application boundary, default to disabled, and reject malformed configuration.

```kotlin
fun calendarEnabled(configuration: Map<String, String>): Boolean {
    val raw = configuration["ENABLE_CALENDAR"] ?: return false
    return requireNotNull(raw.toBooleanStrictOrNull()) {
        "ENABLE_CALENDAR must be true or false"
    }
}

fun configuredHome(configuration: Map<String, String>): HomeDto =
    home(calendarEnabled(configuration))
```

Application startup supplies `System.getenv()` or another configuration map. Changing that configuration and restarting reverses the rollout while the flag exists. Gate calendar entry points as well if unfinished functionality must also be inaccessible through direct requests.

### Flipping the Flag in Tests

Supply configuration explicitly; these checks need only the standard library. They exercise the configuration-to-feature path without changing process environment variables.

```kotlin
fun verifyCalendarFlag() {
    val disabled = configuredHome(emptyMap())
    check(disabled.links == listOf(createReservationsLink()))
    val enabled = configuredHome(mapOf("ENABLE_CALENDAR" to "true"))
    check(enabled.links == listOf(
        createReservationsLink(), createYearLink(), createMonthLink(), createDayLink(),
    ))
    check(configuredHome(mapOf("ENABLE_CALENDAR" to "false")) == disabled)
    check(runCatching { calendarEnabled(mapOf("ENABLE_CALENDAR" to "tru")) }.isFailure)
}
```

### After the Release

Once rollout is complete, delete `calendarEnabled`, its configuration key, and the Boolean parameter. Update callers and replace the conditional with its enabled branch. Remove assertions for the retired disabled behavior, retaining the released links as the expected response.

**Why it works**:
- Missing configuration preserves the previous behavior.
- Tests can enable the calendar without a dependency-injection container.
- Both rollout states can be integrated and verified independently.
- Removing the Boolean parameter makes stale call sites visible to the compiler.

---

## Example 2: Method-Level Strangler — `ReadReservations`

The repository initially reads one calendar date. The calendar feature needs a range of dates. An inclusive `ClosedRange<LocalDate>` represents a single date as `date..date`, preserving that day's behavior even for `LocalDate.MAX`.

### Before

```kotlin
interface ReservationsRepository {
    fun create(reservation: Reservation)
    fun readReservations(date: LocalDate): List<Reservation>
    fun readReservation(id: UUID): Reservation?
    fun update(reservation: Reservation)
    fun delete(id: UUID)
}
```

### Step 1: Add the New Overload

```kotlin
interface ReservationsRepository {
    fun create(reservation: Reservation)

    @Deprecated("Use readReservations(date..date)")
    fun readReservations(date: LocalDate): List<Reservation> =
        readReservations(date..date)

    fun readReservations(dates: ClosedRange<LocalDate>): List<Reservation>
    fun readReservation(id: UUID): Reservation?
    fun update(reservation: Reservation)
    fun delete(id: UUID)
}
```

Update the production repository and test implementation in the same change. The range query selects `reservation.at.toLocalDate() in dates` and preserves the old ordering. Remove existing single-date overrides or change them to delegate to the range overload; otherwise they take precedence over the interface's default implementation. The old overload then delegates to the range implementation so callers can migrate separately. For externally implemented interfaces, adding a required method also needs a compatibility and versioning plan.

### Step 2: Migrate Callers One at a Time

```kotlin
val day = reservation.at.toLocalDate()
val reservations = repository.readReservations(day..day)
```

Migrate each caller through a verified change. Compare the old overload with the new one for the same date, including reservations on either side of the date boundary.

### Step 3: Delete the Old Method

```kotlin
interface ReservationsRepository {
    fun create(reservation: Reservation)
    fun readReservations(dates: ClosedRange<LocalDate>): List<Reservation>
    fun readReservation(id: UUID): Reservation?
    fun update(reservation: Reservation)
    fun delete(id: UUID)
}
```

Remove the single-date overload after every caller has migrated. For an externally consumed API, retain the announced deprecation period and remove it in the breaking release.

**Why it works**:
- A single date is a special case of a date range, so the new query can subsume the old one.
- The delegating bridge retains one selection rule during migration.
- Removing the old signature makes remaining single-date calls fail to compile.
- Each stage can be verified and integrated independently.

---

## Example 3: Class-Level Strangler — `Occurrence<T>` to `TimeSlot`

Every actual use associates a timestamp with a list of tables. A concrete `TimeSlot` expresses that domain concept without the generic wrapper.

### Before: the over-abstract generic

```kotlin
data class Occurrence<T>(val at: LocalDateTime, val value: T)

fun schedule(reservations: List<Reservation>): List<Occurrence<List<Table>>> =
    reservations.groupBy { it.at }.map { (at, bookings) ->
        Occurrence(at, bookings.map { it.table })
    }
```

### Step 1: Introduce `TimeSlot` Beside `Occurrence<T>`

```kotlin
data class TimeSlot(val at: LocalDateTime, val tables: List<Table>)
```

Add the type without changing callers or behavior. `List` provides a read-only API; use fresh list snapshots when crossing mutable ownership boundaries.

### Step 2: Add a Temporary Bridge

```kotlin
internal fun Occurrence<List<Table>>.toTimeSlot(): TimeSlot =
    TimeSlot(at, value.toList())
```

### Step 3: Work Around Return-Type Overloading

Kotlin also cannot distinguish overloads solely by return type. Rename the old query to `scheduleOcc`, update its existing callers, and introduce `schedule` with the domain result. The bridge preserves timestamps, table values, and encounter order during migration.

```kotlin
fun scheduleOcc(reservations: List<Reservation>): List<Occurrence<List<Table>>> =
    reservations.groupBy { it.at }.map { (at, bookings) ->
        Occurrence(at, bookings.map { it.table })
    }

fun schedule(reservations: List<Reservation>): List<TimeSlot> =
    scheduleOcc(reservations).map { it.toTimeSlot() }
```

Migrate helper parameters too; these are alternative versions of the same helper:

```kotlin
// Before
private fun makeEntry(occurrence: Occurrence<List<Table>>): TimeDto =
    TimeDto(occurrence.at, occurrence.value.map { it.number })

// After
private fun makeEntry(timeSlot: TimeSlot): TimeDto =
    TimeDto(timeSlot.at, timeSlot.tables.map { it.number })
```

### Step 4: Migrate Callers, Then Delete the Old Class

Once every caller uses `schedule` and `TimeSlot`, move the grouping implementation into `schedule`, constructing `TimeSlot` directly. Then delete:

1. `scheduleOcc`.
2. The `toTimeSlot` conversion.
3. `Occurrence<T>`.

Check empty input, grouping, table values, and ordering across the transition. Each verified checkpoint remains consistent and can be integrated independently.

**Why it works**:
- The new type can be introduced before any callers change.
- The temporary bridge has one explicit deletion point.
- The temporary query name lets both return types coexist.
- Moving the implementation before deleting the bridge preserves a working final query.
