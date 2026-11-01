# Outside-In TDD Examples: Go and testing

These fork additions adapt Examples 3, 4, and 6 from [the C# source](csharp-aspnetcore-xunit.md), retaining their order and scenarios. For HTTP Examples 1, 2, and 5, use [the net/http examples](go-net-http-testing.md).

Use Go 1.22+ and the standard library only. In a scratch directory outside the skill, run `go mod init example.com/reservations` and `go mod edit -go=1.22`. Save each named block as its indicated file and run `go test ./...`. Examples 3 and 4 share one package. Example 6 is independent: put its before and after alternatives in separate directories. All code is included; production definitions sit beside tests here for a compact runnable demonstration.

## Example 3: Unit Test with AAA and a Fake Object

Once the HTTP test passes minimally, drive persistence through an ordinary service. The HTTP adapter delegates to this service; it does not own business rules. Save as `reservation_test.go`:

```go
package reservations

import (
	"errors"
	"strings"
	"testing"
	"time"
)

type ReservationDTO struct {
	At       string
	Email    string
	Name     *string
	Quantity int
}

type Reservation struct {
	at          time.Time
	email, name string
	quantity    int
}

func newReservation(dto ReservationDTO) (Reservation, error) {
	at, err := time.Parse("2006-01-02 15:04", dto.At)
	if err != nil || strings.TrimSpace(dto.Email) == "" || dto.Quantity <= 0 {
		return Reservation{}, errors.New("invalid reservation")
	}
	name := ""
	if dto.Name != nil {
		name = *dto.Name
	}
	return Reservation{at, dto.Email, name, dto.Quantity}, nil
}

type Reservations interface {
	On(time.Time) ([]Reservation, error)
	Add(Reservation) error
}

type FakeReservations struct{ entries []Reservation }

func (f *FakeReservations) On(day time.Time) ([]Reservation, error) {
	var found []Reservation
	for _, r := range f.entries {
		if r.at.Format("2006-01-02") == day.Format("2006-01-02") {
			found = append(found, r)
		}
	}
	return found, nil
}

func (f *FakeReservations) Add(r Reservation) error {
	f.entries = append(f.entries, r)
	return nil
}

var ErrFull = errors.New("no tables available")

type ReservationService struct {
	repository Reservations
	capacity   int
}

func (s ReservationService) Book(dto ReservationDTO) error {
	r, err := newReservation(dto)
	if err != nil {
		return err
	}
	existing, err := s.repository.On(r.at)
	if err != nil {
		return err
	}
	remaining := s.capacity
	for _, booking := range existing {
		remaining -= booking.quantity
	}
	if r.quantity > remaining {
		return ErrFull
	}
	return s.repository.Add(r)
}

func text(s string) *string { return &s }

func TestPostValidReservationWhenDatabaseIsEmpty(t *testing.T) {
	db := &FakeReservations{}
	sut := ReservationService{db, 10}

	dto := ReservationDTO{"2023-11-24 19:00", "juliad@example.net", text("Julia Domna"), 5}
	err := sut.Book(dto)

	expected := Reservation{time.Date(2023, 11, 24, 19, 0, 0, 0, time.UTC), dto.Email, *dto.Name, 5}
	if err != nil {
		t.Fatal(err)
	}
	if len(db.entries) != 1 || db.entries[0] != expected {
		t.Fatalf("stored = %#v; want [%#v]", db.entries, expected)
	}
}
```

**Why it works**:
- Arrange, act, and assert stay visually separate; storage is the observable outcome.
- The fake implements the small repository interface through composition. It filters by day and propagates errors through the same contract as a real adapter.
- The comparable struct gives value equality here: dates are parsed in UTC without monotonic clock readings. Use `Time.Equal` when comparing times with different location or monotonic metadata.
- A missing name becomes empty. This simplified domain accepts any nonblank email, counts seats per UTC calendar day, and permits historical dates. Validation is runtime: Go permits a zero `Reservation`, and code in the same package can bypass unexported fields. The service constructs validated values before storage.
- The fake and check-then-add service are sequential examples. A concurrent persistence adapter must check capacity and insert atomically; this interface alone does not guarantee that.

## Example 4: Parametrised Test with Devil's Advocate Counter-Case

Suppose a deliberately incorrect implementation rejects every booking from `shli@example.org` to pass an overbooking test. Append the fourth row below: an empty repository must accept that same email. Save as `countercase_test.go` beside Example 3:

```go
package reservations

import (
	"testing"
	"time"
)

func TestValidReservationsWhenDatabaseIsEmpty(t *testing.T) {
	cases := []ReservationDTO{
		{"2023-11-24 19:00", "juliad@example.net", text("Julia Domna"), 5},
		{"2024-02-13 18:15", "x@example.com", text("Xenia Ng"), 9},
		{"2023-08-23 16:55", "kite@example.edu", nil, 2},
		{"2022-03-18 17:30", "shli@example.org", text("Shanghai Li"), 5},
	}
	for _, dto := range cases {
		t.Run(dto.Email, func(t *testing.T) {
			db := &FakeReservations{}
			sut := ReservationService{db, 10}

			err := sut.Book(dto)

			at, parseErr := time.Parse("2006-01-02 15:04", dto.At)
			if parseErr != nil {
				t.Fatal(parseErr)
			}
			name := ""
			if dto.Name != nil {
				name = *dto.Name
			}
			expected := Reservation{at, dto.Email, name, dto.Quantity}
			if err != nil {
				t.Fatal(err)
			}
			if len(db.entries) != 1 || db.entries[0] != expected {
				t.Fatalf("stored = %#v; want [%#v]", db.entries, expected)
			}
		})
	}
}
```

**Why it works**:
- Appending one row preserves the existing inputs and postconditions.
- Each subtest starts with empty storage; the counter-case defeats the email branch without weakening the original capacity test.
- Go's [table-driven subtests](https://go.dev/blog/subtests) need no parameterisation library. A nil name is an explicit input, not a magic CSV convention.

## Example 6: Test Spy Refactored in Isolation

First change the spy representation and migrate creation assertions while keeping the production interface fixed. Run the existing creation tests. Only then extend the production interface and add deletion coverage. The after block shows that final stage; verify the intermediate stage by removing its deletion method, interface member, call, and expected deletion observation. Keep the creation observation assertion intact.

Before (captures only reservations, not which method was called). Save in `before/spy_test.go`:

```go
package spy

import "testing"

type Reservation struct{ Email string }
type PostOffice interface{ ReservationCreated(Reservation) error }
type SpyPostOffice struct{ reservations []Reservation }

func (s *SpyPostOffice) ReservationCreated(r Reservation) error {
	s.reservations = append(s.reservations, r)
	return nil
}

var _ PostOffice = (*SpyPostOffice)(nil)

func TestCreationNotification(t *testing.T) {
	spy := &SpyPostOffice{}
	r := Reservation{"juliad@example.net"}

	err := spy.ReservationCreated(r)

	if err != nil {
		t.Fatal(err)
	}
	if len(spy.reservations) != 1 || spy.reservations[0] != r {
		t.Fatalf("observed = %#v; want [%#v]", spy.reservations, r)
	}
}
```

After (captures both method kind and reservation). Save in `after/spy_test.go`:

```go
package spy

import (
	"reflect"
	"testing"
)

type Reservation struct{ Email string }
type PostOffice interface {
	ReservationCreated(Reservation) error
	ReservationDeleted(Reservation) error
}
type Event int

const (
	Created Event = iota
	Deleted
)

type Observation struct {
	Event       Event
	Reservation Reservation
}
type SpyPostOffice struct{ observations []Observation }

func (s *SpyPostOffice) ReservationCreated(r Reservation) error {
	s.observations = append(s.observations, Observation{Created, r})
	return nil
}
func (s *SpyPostOffice) ReservationDeleted(r Reservation) error {
	s.observations = append(s.observations, Observation{Deleted, r})
	return nil
}

var _ PostOffice = (*SpyPostOffice)(nil)

func TestNotificationKinds(t *testing.T) {
	spy := &SpyPostOffice{}
	r := Reservation{"juliad@example.net"}

	if err := spy.ReservationCreated(r); err != nil {
		t.Fatal(err)
	}
	if err := spy.ReservationDeleted(r); err != nil {
		t.Fatal(err)
	}

	expected := []Observation{{Created, r}, {Deleted, r}}
	if !reflect.DeepEqual(spy.observations, expected) {
		t.Fatalf("observed = %#v; want %#v", spy.observations, expected)
	}
}
```

**Why it works**:
- Refactoring the creation spy and adding deletion behaviour are separately reviewable steps. Preserve caller test preconditions while changing their observation assertions.
- Interface conformance is compile-time; event values and observations remain ordinary runtime values, not a sealed union. This test double records only its two defined kinds.
- The small reservation type isolates the notification example from booking validation; production callers pass their existing domain value.
