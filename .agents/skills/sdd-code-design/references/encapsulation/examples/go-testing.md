# Encapsulation Examples: Go and testing

Fork addition: standard-library counterpart to the C# parameterized invariant test. Requires Go 1.22+; no external test library. Assemble `reservation.go` as described in [go.md](go.md), save this block beside it as `reservation_test.go`, and run `go test ./...`. Other source examples live in the framework-independent file. Subtests use the standard [`testing` package](https://pkg.go.dev/testing).

## Good Examples

### Parametrised Test Triangulating the `quantity` Invariant

```go
package restaurant

import (
	"errors"
	"strconv"
	"testing"
	"time"
)

func TestQuantityMustBePositive(t *testing.T) {
	at := time.Date(2024, time.August, 19, 11, 30, 0, 0, time.UTC)
	for _, quantity := range []int{0, -1} {
		t.Run(strconv.Itoa(quantity), func(t *testing.T) {
			_, err := NewReservation(at, "mail@example.com", "Marie Ilsøe", quantity)
			if !errors.Is(err, ErrQuantity) {
				t.Fatalf("quantity %d: got error %v, want ErrQuantity", quantity, err)
			}
		})
	}
}
```

**Why it works**:
- Table-driven subtests distinguish zero from negative quantities and pin the lower boundary.
- `errors.Is` checks the failure category without depending on message text.
- These cases drive the factory guard through Red → Green → Refactor; production consumers still handle Go's possible zero domain value at their boundaries.
