# Outside-In TDD Examples: Kotlin and JUnit 5

These fork additions cover the original walkthrough's framework-independent counterparts: Examples 3, 4, and 6. The subset is intentional and works in Kotlin projects using any HTTP framework. Read [the Ktor examples](kotlin-ktor-junit5.md) only when working on a Ktor HTTP boundary.

Use Kotlin/JVM 2.3.20 targeting Java 17 and `org.junit.jupiter:junit-jupiter:5.13.4`, with `test { useJUnitPlatform() }` and `org.junit.platform:junit-platform-launcher:1.13.4` at test runtime. Snippets belong in the project's test sources and use the application contracts described below. Before/after spy definitions are alternatives.

## Example 3: Unit Test with AAA and a Fake Object

Once the boundary test passes minimally, drive persistence through `ReservationService` directly. Kotlin puts this logic in an ordinary class; the HTTP adapter delegates to it.

```kotlin
@Test
fun `post a valid reservation when the database is empty`() {
    val repository = FakeReservations()
    val service = ReservationService(repository, capacity = 10)

    val dto = ReservationDto("2023-11-24T19:00", "juliad@example.net", "Julia Domna", 5)
    service.book(dto)

    val expected = Reservation(LocalDateTime.of(2023, 11, 24, 19, 0),
        "juliad@example.net", "Julia Domna", 5)
    assertTrue(expected in repository.entries)
}
```

The fake implements the production repository contract through composition:

```kotlin
class FakeReservations : Reservations {
    private val stored = mutableListOf<Reservation>()
    val entries: List<Reservation> get() = stored.toList()
    override fun on(date: LocalDate) = stored.filter { it.at.toLocalDate() == date }
    override fun add(reservation: Reservation) { stored += reservation }
}
```

**Why it works**:
- Arrange, act, and assert remain visually distinct.
- The fake has observable storage and date filtering, with no database dependency.
- `Reservation` is a data class, so membership compares values. Its constructor requires a nonblank email and a positive quantity; `at` is a `LocalDateTime`.
- `ReservationDto` has nullable `at`, `email`, and `name` strings and a nullable integer `quantity`. The service validates it and normalises an absent name to an empty string before constructing the domain value. Fixed dates need no wall-clock assumptions.

## Example 4: Parametrised Test with Devil's Advocate Counter-Case

Suppose an overbooking test passes because `book` rejects every request from `shli@example.org`. Add a row using the same email with an empty repository. That counter-case requires success and storage, rejecting the hard-coded branch.

```kotlin
@ParameterizedTest
@CsvSource(
    "2023-11-24T19:00, juliad@example.net, Julia Domna, 5",
    "2024-02-13T18:15, x@example.com, Xenia Ng, 9",
    "2023-08-23T16:55, kite@example.edu, , 2",
    "2022-03-18T17:30, shli@example.org, Shanghai Li, 5"
)
fun `valid reservations succeed when the database is empty`(
    at: String, email: String, name: String?, quantity: Int
) {
    val repository = FakeReservations()
    val service = ReservationService(repository, capacity = 10)

    val result = service.book(ReservationDto(at, email, name, quantity))

    assertEquals(BookingResult.CREATED, result)
    assertTrue(Reservation(LocalDateTime.parse(at), email,
        name.orEmpty(), quantity) in repository.entries)
}
```

**Why it works**:
- Appending the fourth CSV row preserves every existing case and assertion.
- The new case forces the implementation to consider available capacity rather than the email literal.
- JUnit maps an unquoted empty CSV field to `null`, so `name` is nullable. `orEmpty()` expresses the domain's normalisation explicitly. See [JUnit's CSV sources](https://docs.junit.org/5.13.4/user-guide/index.html#writing-tests-parameterized-tests-sources-CsvSource).

## Example 6: Test Spy Refactored in Isolation

Adding `reservationDeleted` to `PostOffice` requires distinguishing notification kinds. First refactor the spy's representation and migrate existing creation assertions while the production contract is fixed. Run those tests before adding the deletion method. The final after version below includes that subsequent addition; these are alternative class definitions.

Before (captures only reservations, not which method was called):

```kotlin
class SpyPostOffice : PostOffice {
    val reservations = mutableListOf<Reservation>()

    override fun reservationCreated(reservation: Reservation) {
        reservations += reservation
    }
}
```

After (captures both method kind and reservation):

```kotlin
class SpyPostOffice : PostOffice {
    val observations = mutableListOf<Observation>()

    override fun reservationCreated(reservation: Reservation) {
        observations += Observation.Created(reservation)
    }

    override fun reservationDeleted(reservation: Reservation) {
        observations += Observation.Deleted(reservation)
    }

    sealed interface Observation {
        data class Created(val reservation: Reservation) : Observation
        data class Deleted(val reservation: Reservation) : Observation
    }
}
```

**Why it works**:
- Test refactoring and new production behaviour stay separately reviewable.
- Sealed observations distinguish the event kind while retaining structural equality. A creation assertion changes from `reservation` to `Observation.Created(reservation)`.
- Running existing caller tests after the representation change exposes accidental changes to their meaning before the deletion feature adds more moving parts.
