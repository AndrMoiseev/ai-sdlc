# Encapsulation Examples: Kotlin

Fork addition: Kotlin/JVM counterparts to the C# examples, in the same order. Snippets are alternatives or excerpts; repeated declarations belong to different stages. They use `java.time.LocalDateTime` and `java.time.format.DateTimeParseException`. `ReservationDto` has immutable `at: String?`, `email: String?`, `name: String?`, and `quantity: Int` properties. The date helper below parses ISO local date/time values in the restaurant's time zone. Controller excerpts use a framework-free `HttpResponse(status: Int)` and a repository with suspendable `readReservations(at)` and `create(reservation)` operations. For the matching parameterized invariant test, load [the JUnit 5 example](kotlin-junit5.md) only when the project uses JUnit Jupiter 5.

## Bad Examples

### Anemic Domain Model — No Guards in the Constructor

```kotlin
data class Reservation(
    val at: LocalDateTime,
    val email: String,
    val name: String,
    val quantity: Int,
)
```

**Problems**:
- A caller can construct `Reservation(..., quantity = -3)`.
- Downstream code must repeatedly check that `quantity > 0`.
- Non-null Kotlin types establish presence at ordinary Kotlin call sites, but they do not establish the quantity invariant.

### Exclamation-Mark Suppression — Compile-Time Error Traded for Runtime Crash

Inside a handler receiving `dto: ReservationDto`:

```kotlin
val r = Reservation(
    at = LocalDateTime.parse(dto.at!!),
    email = dto.email!!,
    name = dto.name!!,
    quantity = dto.quantity,
)
```

**Problems**:
- Kotlin's `!!` performs a runtime assertion; unlike C#'s null-forgiving `!`, it throws immediately when the value is null.
- Missing input or a malformed date becomes an exception instead of an explicit client-input failure.
- The compiler accepts the assertion, but the input has not become trustworthy.

### Boolean Validate — Throws Away Parsing Work

The reusable date helper handles only expected parsing failures. The problem is discarding its result behind a Boolean:

```kotlin
fun parseDateTime(text: String?): LocalDateTime? {
    if (text == null) return null
    return try {
        LocalDateTime.parse(text)
    } catch (_: DateTimeParseException) {
        null
    }
}

fun ReservationDto.isValid(): Boolean {
    if (parseDateTime(at) == null) return false
    if (email == null) return false
    if (quantity < 1) return false
    return true
}
```

The caller must reconstruct the checked values:

```kotlin
if (!dto.isValid()) return HttpResponse(400)
val r = Reservation(
    at = LocalDateTime.parse(dto.at!!), // Parse again.
    email = dto.email!!,               // Assert again.
    name = dto.name ?: "",
    quantity = dto.quantity,
)
```

**Problems**:
- The date is parsed twice: once in `isValid`, once during construction.
- A Boolean return carries no parsed value or nullable-property refinement to the caller.
- Another caller can skip `isValid` completely.

## Good Examples

### Always-Valid Constructor with Guard Clause

```kotlin
data class Reservation(
    val at: LocalDateTime,
    val email: String,
    val name: String,
    val quantity: Int,
) {
    init {
        require(quantity > 0) { "Quantity must be a positive number" }
    }
}
```

**Why it works**:
- Every construction rejects zero and negative quantities with `IllegalArgumentException`; generated `copy` calls also execute `init`.
- Non-null property types establish that date, email, and name are present at Kotlin call sites. The example does not claim to validate email syntax.
- Immutable properties preserve the established invariant, so downstream code can use the quantity directly.

### Parse, Don't Validate — DTO Returns a Typed Domain Object

Using the `parseDateTime` helper above:

```kotlin
fun ReservationDto.parse(): Reservation? {
    val parsedAt = parseDateTime(at) ?: return null
    val parsedEmail = email ?: return null
    if (quantity < 1) return null
    return Reservation(
        at = parsedAt,
        email = parsedEmail,
        name = name ?: "",
        quantity = quantity,
    )
}
```

**Why it works**:
- `Reservation?` states that parsing yields a domain value or fails.
- Parsing happens once; the returned object carries both the parsed date and the quantity invariant.
- This wire contract explicitly permits a missing name as `""`, and rejects a missing email or unparseable date.
- Elvis returns establish non-null local values without `!!`; callers must handle the nullable result.

### Controller Using the Parsed Domain Object

A controller member with an injected `repository`:

```kotlin
suspend fun post(dto: ReservationDto?): HttpResponse {
    requireNotNull(dto) { "dto must be supplied" }
    val r = dto.parse() ?: return HttpResponse(400)

    val reservations = repository.readReservations(r.at)
    val reservedSeats = reservations.sumOf { it.quantity.toLong() }
    if (10 < reservedSeats + r.quantity) return HttpResponse(409)

    repository.create(r)
    return HttpResponse(204)
}
```

**Why it works**:
- All domain values are typed and no null assertions remain.
- Parsing, capacity rejection, and persistence are visible in a short sequence.
- A null parse result becomes 400; a valid reservation reaches the repository. This Kotlin variant uses 409 for unavailable capacity, where the source example uses 500.

`requireNotNull` protects the controller's calling contract, corresponding to the source's argument guard. An actual HTTP adapter should handle a missing request body before this call. Concurrent booking also needs an atomic capacity check and write at the persistence boundary.

## Refactoring Walkthrough

### Before — Controller Carrying All Validation Inline

A controller member; `parseDateTime` is the shared format helper, while input decisions remain in this method:

```kotlin
suspend fun post(dto: ReservationDto?): HttpResponse {
    requireNotNull(dto) { "dto must be supplied" }
    val parsedAt = parseDateTime(dto.at) ?: return HttpResponse(400)
    val parsedEmail = dto.email ?: return HttpResponse(400)
    if (dto.quantity < 1) return HttpResponse(400)
    val r = Reservation(parsedAt, parsedEmail, dto.name ?: "", dto.quantity)
    repository.create(r)
    return HttpResponse(204)
}
```

### After — Parse Extracted into DTO, Invariant Moved into Domain Constructor

These declarations form the alternative final stage. Reuse the date helper and transport DTO from above:

```kotlin
// ReservationDto.kt
fun ReservationDto.parse(): Reservation? {
    val parsedAt = parseDateTime(at) ?: return null
    val parsedEmail = email ?: return null
    if (quantity < 1) return null
    return Reservation(parsedAt, parsedEmail, name ?: "", quantity)
}

// Reservation.kt
data class Reservation(
    val at: LocalDateTime,
    val email: String,
    val name: String,
    val quantity: Int,
) {
    init {
        require(quantity > 0) { "Quantity must be a positive number" }
    }
}

// ReservationsController.kt
class ReservationsController(private val repository: ReservationsRepository) {
    suspend fun post(dto: ReservationDto?): HttpResponse {
        requireNotNull(dto) { "dto must be supplied" }
        val r = dto.parse() ?: return HttpResponse(400)
        repository.create(r)
        return HttpResponse(204)
    }
}
```

### Changes Made

1. Moved parsing into `ReservationDto.parse`, so the controller no longer knows date-format or nullable-email details.
2. Moved the positive-quantity invariant into `Reservation.init`, protecting direct construction and `copy` as well as HTTP callers.
3. Replaced a Boolean validation result with `Reservation?`, carrying the parsed value forward without repeated parsing or `!!`.
4. Reduced the controller to argument checking, parsing-result handling, and persistence; immutable domain values preserve validity afterward.
