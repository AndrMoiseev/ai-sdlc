# Outside-In TDD Examples: Kotlin, Ktor, and JUnit 5

These fork additions cover the original walkthrough's Ktor HTTP counterparts: Examples 1, 2, and 5. The subset is intentional. For service tests or spies without an HTTP framework dependency, read only the relevant section in [the Kotlin/JUnit examples](kotlin-junit5.md).

Use Kotlin/JVM 2.3.20 targeting Java 17, `io.ktor:ktor-server-core-jvm:3.1.3`, `io.ktor:ktor-server-test-host-jvm:3.1.3`, `org.jetbrains.kotlinx:kotlinx-serialization-json-jvm:1.8.0`, and `org.junit.jupiter:junit-jupiter:5.13.4`. Configure `test { useJUnitPlatform() }` and `org.junit.platform:junit-platform-launcher:1.13.4` at test runtime. Snippets show successive stages in a project's test sources, with its application types and fixtures; before/after snippets are alternatives.

## Example 1: Walking Skeleton + Characterisation Test

This first test targets the scaffolded application's HTTP boundary and asserts only a 2xx status. `homeModule` is the existing application module serving the home route. Because the test follows scaffolding, it characterises existing behaviour rather than starting with a red phase.

```kotlin
@Test
fun `home is available`() = testApplication {
    application { homeModule() }

    val response = client.get("/")

    assertTrue(response.status.value in 200..299) {
        "Actual status code: ${response.status}"
    }
}
```

**Why it works**:
- One loose assertion permits changes to the response body and successful status.
- Blank lines distinguish application setup, the request, and the assertion.
- The failure message reports the actual status. Kotlin needs no URI-analyser suppression for this literal.
- Ktor's `testApplication` runs HTTP calls in process. A walking skeleton also needs CI and a deployed smoke test to prove the deployment path. See the [Ktor testing API](https://api.ktor.io/3.1.x/ktor-server-test-host/io.ktor.server.testing/test-application.html).

## Example 2: Boundary Test Driving a New Feature

Post a valid reservation and initially assert success. Write this while the route is absent, observe the 404, then add the smallest implementation that passes. `testApplication` owns the application lifetime; the helper hides wiring and JSON details.

```kotlin
@Test
fun `post a valid reservation`() = testApplication {
    val response = postReservation(ReservationDto(
        at = "2023-03-10T19:00",
        email = "katinka@example.com",
        name = "Katinka Ingabogovinanana",
        quantity = 2
    ))

    assertTrue(response.status.value in 200..299) {
        "Actual status code: ${response.status}"
    }
}
```

The hidden helper (a SUT Encapsulation Method / Test Utility Method):

```kotlin
suspend fun ApplicationTestBuilder.postReservation(
    dto: ReservationDto,
    repository: Reservations = FakeReservations()
): HttpResponse {
    application { reservationsModule(ReservationService(repository, capacity = 10)) }
    return client.post("/reservations") {
        contentType(ContentType.Application.Json)
        setBody(buildJsonObject {
            put("at", dto.at)
            put("email", dto.email)
            put("name", dto.name)
            put("quantity", dto.quantity)
        }.toString())
    }
}
```

Call this helper once per `testApplication` block, before its application starts. `reservationsModule` handles JSON, invokes the service, and maps its result to HTTP. The DTO has nullable `at`, `email`, and `name` strings and a nullable integer `quantity`. An omitted or JSON `null` name becomes an empty domain name; a supplied nonstring name is invalid input. Malformed JSON and invalid quantities return 400 without storing anything. The JSON tree API needs no serialization compiler plugin.

**Why it works**:
- The test reads as a behaviour specification; request construction stays in the helper.
- The helper encapsulates URL and JSON conventions and injects a fresh fake by default.
- The success assertion is appropriate for the first slice. Before accepting the feature, strengthen the boundary coverage with the stored outcome and invalid-input cases.

## Example 5: Strengthening Postconditions by Adding Assertions

A full-capacity test initially checks only the status. In this API, a capacity conflict returns 409. Populate the repository to capacity, post another reservation, then strengthen the same act phase so an unrelated conflict cannot satisfy it.

Before:

```kotlin
assertEquals(HttpStatusCode.Conflict, response.status)
```

After:

```kotlin
assertEquals(HttpStatusCode.Conflict, response.status)
val content = response.bodyAsText()
assertTrue(content.contains("tables", ignoreCase = true))
```

**Why it works**:
- The original status assertion is retained verbatim; only another observation is added.
- An unrelated 409 response no longer passes unless it also reports the expected cause.
- `bodyAsText()` returns a nonnullable string, so Kotlin needs no redundant null assertion. A further storage assertion can ensure rejection leaves existing bookings unchanged.

## Changes Made (across the vertical slice)

The corresponding implementation sequence is:

1. Scaffold a home endpoint and capture its successful response with a characterisation test.
2. Run tests in CI and add a deployment smoke test for the walking skeleton.
3. Add the failing JSON boundary test, then a Ktor route that passes it minimally.
4. Move inward to service tests, introducing the DTO, domain value, repository contract, and fake; use [Examples 3 and 4](kotlin-junit5.md) for that step.
5. Add a real persistence adapter as a Humble Object when introducing SQL; verify it separately, including an atomic capacity check and insert. These snippets use the fake.
6. Append counter-cases, strengthen postconditions, and refactor seat counting to `sumOf` once the tests support the generalisation.
