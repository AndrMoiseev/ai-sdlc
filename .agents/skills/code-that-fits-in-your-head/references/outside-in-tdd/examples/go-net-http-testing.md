# Outside-In TDD Examples: Go, net/http, and testing

These fork additions adapt HTTP Examples 1, 2, and 5 from [the C# source](csharp-aspnetcore-xunit.md), retaining their order and scenarios. Use [the Go/testing examples](go-testing.md) for service tests and spies (3, 4, and 6).

Use Go 1.22+ and only the standard library (`net/http`, `net/http/httptest`, and `testing`). In a scratch directory outside the skill, run `go mod init example.com/httpreservations` and `go mod edit -go=1.22`. Save the named blocks together and run `go test ./...`; Example 5's before and after files are alternatives. The support code is intentionally local so these HTTP examples run without loading the unit-test file.

## Example 1: Walking Skeleton + Characterisation Test

The scaffold already serves a home route. This first test characterises that behaviour; it has no intentional red phase. Save as `home_test.go`:

```go
package httpreservations

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func home() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	return mux
}

func TestHomeIsOK(t *testing.T) {
	server := httptest.NewServer(home())
	t.Cleanup(server.Close)

	response, err := server.Client().Get(server.URL + "/")

	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		t.Fatalf("actual status code: %d", response.StatusCode)
	}
}
```

**Why it works**:
- The single behavioural assertion accepts any 2xx status. Transport error checks and cleanup keep the test trustworthy without constraining the response body.
- Blank lines retain AAA: server setup, request, then observations.
- [`httptest.NewServer`](https://pkg.go.dev/net/http/httptest#NewServer) exercises a local HTTP server; CI and a deployed smoke test are still needed to prove the deployment path.
- Method-aware routing and the exact-root `{$}` pattern require Go 1.22+; see [`ServeMux`](https://pkg.go.dev/net/http#ServeMux).

## Example 2: Boundary Test Driving a New Feature

Start with the home-only handler and this test: POST `/reservations` returns 404, so the success assertion is intentionally red. Then register the smallest successful POST handler. Move inward to [Examples 3 and 4](go-testing.md) to drive validation and persistence. The complete runnable block below is the later green fixture, not a claim that the full implementation preceded the test. Save as `reservation_test.go`:

```go
package httpreservations

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

type ReservationDTO struct {
	Date     string  `json:"date"`
	Email    string  `json:"email"`
	Name     *string `json:"name"`
	Quantity int     `json:"quantity"`
}
type Reservation struct {
	At          time.Time
	Email, Name string
	Quantity    int
}
type FakeReservations struct{ Entries []Reservation }

func reservationsHandler(db *FakeReservations) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /reservations", func(w http.ResponseWriter, r *http.Request) {
		var dto ReservationDTO
		decoder := json.NewDecoder(r.Body)
		if err := decoder.Decode(&dto); err != nil {
			http.Error(w, "invalid JSON", http.StatusBadRequest)
			return
		}
		if err := decoder.Decode(new(any)); err != io.EOF {
			http.Error(w, "expected one JSON object", http.StatusBadRequest)
			return
		}
		at, err := time.Parse("2006-01-02 15:04", dto.Date)
		if err != nil || strings.TrimSpace(dto.Email) == "" || dto.Quantity <= 0 {
			http.Error(w, "invalid reservation", http.StatusBadRequest)
			return
		}
		remaining := 10
		for _, entry := range db.Entries {
			if entry.At.Format("2006-01-02") == at.Format("2006-01-02") {
				remaining -= entry.Quantity
			}
		}
		if dto.Quantity > remaining {
			http.Error(w, "no tables available", http.StatusConflict)
			return
		}
		name := ""
		if dto.Name != nil {
			name = *dto.Name
		}
		db.Entries = append(db.Entries, Reservation{at, dto.Email, name, dto.Quantity})
		w.WriteHeader(http.StatusCreated)
	})
	return mux
}

func TestPostValidReservation(t *testing.T) {
	name := "Katinka Ingabogovinanana"
	db := &FakeReservations{}

	response := postReservation(t, db, ReservationDTO{
		"2023-03-10 19:00", "katinka@example.com", &name, 2,
	})

	if response.StatusCode < 200 || response.StatusCode >= 300 {
		t.Fatalf("actual status code: %d", response.StatusCode)
	}
}

func postReservation(t *testing.T, db *FakeReservations, dto ReservationDTO) *http.Response {
	t.Helper()
	body, err := json.Marshal(dto)
	if err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(http.MethodPost, "/reservations", bytes.NewReader(body))
	request.Header.Set("Content-Type", "application/json")
	recorder := httptest.NewRecorder()
	reservationsHandler(db).ServeHTTP(recorder, request)
	response := recorder.Result()
	t.Cleanup(func() { response.Body.Close() })
	return response
}
```

The hidden helper is a SUT Encapsulation Method / Test Utility Method: `t.Helper()` attributes failures to callers. It owns request encoding, routing, and response cleanup. The recorder invokes the handler in process; Example 1 covers a real local transport. Replace `reservationsHandler(db)` with `home()` in this helper to reproduce the initial red phase.

**Why it works**:
- The test foregrounds a valid reservation and successful response. The first slice deliberately leaves room for later storage assertions.
- Missing/null names become empty, while a nonstring name fails decoding. Missing/null quantities decode to zero and fail validation; fractional quantities fail decoding. Multiple JSON values also fail before storage.
- This isolated fixture combines the adapter and booking logic to remain self-contained. In the application, move the booking logic into the service driven by Example 3. It assumes nonblank email, UTC dates, daily capacity 10, and sequential requests; historical dates remain valid. A real concurrent repository requires an atomic capacity check and insert. Body-size limits, authentication, and production persistence are outside this demonstration.

## Example 5: Strengthening Postconditions by Adding Assertions

Fill the same day's capacity, then post another reservation. This Go adaptation returns 409 for capacity conflict, following the Kotlin adaptation; the C# source's 500 would also require cause-specific assertions. The before and after stages use the same setup and request. The after stage retains the status assertion verbatim and adds checks for the cause and unchanged storage.

Before: save as `capacity_test.go` beside Example 2.

```go
package httpreservations

import (
	"net/http"
	"testing"
	"time"
)

func TestFullCapacity(t *testing.T) {
	existing := Reservation{time.Date(2022, 3, 18, 17, 30, 0, 0, time.UTC), "other@example.org", "Other", 10}
	db := &FakeReservations{Entries: []Reservation{existing}}

	response := postReservation(t, db, ReservationDTO{"2022-03-18 17:30", "shli@example.org", nil, 5})

	if response.StatusCode != http.StatusConflict {
		t.Fatalf("status = %d; want 409", response.StatusCode)
	}
}
```

After: replace only `capacity_test.go` with this version.

```go
package httpreservations

import (
	"io"
	"net/http"
	"strings"
	"testing"
	"time"
)

func TestFullCapacity(t *testing.T) {
	existing := Reservation{time.Date(2022, 3, 18, 17, 30, 0, 0, time.UTC), "other@example.org", "Other", 10}
	db := &FakeReservations{Entries: []Reservation{existing}}

	response := postReservation(t, db, ReservationDTO{"2022-03-18 17:30", "shli@example.org", nil, 5})

	if response.StatusCode != http.StatusConflict {
		t.Fatalf("status = %d; want 409", response.StatusCode)
	}
	content, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(strings.ToLower(string(content)), "tables") {
		t.Fatalf("body = %q; want a tables explanation", content)
	}
	if len(db.Entries) != 1 || db.Entries[0] != existing {
		t.Fatalf("rejection changed storage: %#v", db.Entries)
	}
}
```

**Why it works**:
- The original assertion remains unchanged. An unrelated conflict is no longer enough to pass.
- `ResponseRecorder.Result` supplies a nonnil body, so no separate nil assertion is needed for this fixture.
- The storage assertion catches accidental writes on rejected bookings. The counter-case in Example 4 prevents an email-specific rejection from masquerading as capacity logic.

## Changes Made (across the vertical slice)

1. Scaffold a working home route, then characterise its successful response.
2. Run tests in CI and add a deployed smoke test for the walking skeleton.
3. Add the failing JSON boundary test, then the smallest POST handler that passes.
4. Move inward to the service, domain value, repository interface, and fake in [Examples 3 and 4](go-testing.md).
5. Introduce a real persistence adapter as a Humble Object when adding SQL; test its atomic capacity check and insertion separately. These examples use a fake only.
6. Append counter-cases and strengthen postconditions before refactoring seat counting. Go uses an ordinary loop instead of LINQ `Sum`.
