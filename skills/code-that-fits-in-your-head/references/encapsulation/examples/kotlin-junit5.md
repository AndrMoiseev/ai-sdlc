# Encapsulation Examples: Kotlin and JUnit 5

Fork addition: the JUnit Jupiter 5 counterpart to the source's parameterized invariant test. Load this file for Kotlin/JVM projects using JUnit Jupiter 5. Use the guarded `Reservation` from [the framework-independent Kotlin examples](kotlin.md#always-valid-constructor-with-guard-clause); the remaining encapsulation examples live there.

## Good Examples

### Parametrised Test Triangulating the `quantity` Invariant

A complete test class; use JUnit Jupiter 5.13.4 and run it on the JUnit Platform:

```kotlin
import java.time.LocalDateTime
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.ValueSource

class ReservationTest {
    @ParameterizedTest
    @ValueSource(ints = [0, -1])
    fun `quantity must be positive`(invalidQuantity: Int) {
        assertThrows<IllegalArgumentException> {
            Reservation(
                at = LocalDateTime.of(2024, 8, 19, 11, 30),
                email = "mail@example.com",
                name = "Marie Ilsøe",
                quantity = invalidQuantity,
            )
        }
    }
}
```

**Why it works**:
- `@ValueSource` exercises zero and negative quantities separately, pinning the exact lower boundary.
- `assertThrows` checks the exception type without coupling to message wording.
- The two cases drive the constructor guard through Red → Green → Refactor.

