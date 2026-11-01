# API Design Examples: Go

Fork addition: Go counterparts to every example in [the C# source](csharp.md), preserving its order. Requires Go 1.22+ and only the standard library. Concatenate every `go` block in this document, in order, into `api.go` in a separate scratch directory; together they form one compilable package, including deliberately poor alternatives named `bad` or `before`. Run `go mod init example.com/api` and `go test ./...` there. Keep this package separate from other topics' examples.

```go
package restaurant

import (
	"context"
	"errors"
	"time"
)
```

## Bad Examples

### Comment Explaining What the Code Does

Intentionally poor naming; domain definitions appear under the good examples.

```go
func badOpeningCheck(candidate Reservation, opensAt, lastSeating TimeOfDay) bool {
	// Reject reservation if it's outside of opening hours.
	at := timeOfDay(candidate.At)
	if at < opensAt || lastSeating < at {
		return false
	}
	return true
}
```

**Problems**:
- Comment and condition can drift apart.
- The reader must interpret both comparisons.
- The helper's name does not convey the domain decision.

### Stringly Typed / X-Out Failure

Intentionally weak API:

```go
type Things interface {
	DoSomething(a, b string) string
	GetSomething(c string) string
	MakeSomething(d, e string) string
}
```

**Problems**:
- Hiding the names leaves nearly identical signatures.
- Strings carry no domain constraints.
- Swapping two string arguments compiles.

### CQS Violation

Intentionally combines mutation and a count query:

```go
type badStore struct{ reservations []Reservation }

func (s *badStore) AddReservationAndGetCount(r Reservation) int {
	s.reservations = append(s.reservations, r)
	return len(s.reservations)
}
```

**Problems**:
- The result type does not reveal the mutation.
- Reading the count requires an unrelated write.
- Go permits commands to return errors or generated IDs; this example couples an independent query to the command unnecessarily.

### Swiss Army Knife Constructor

Intentionally exposes configuration at the controller boundary:

```go
func badNewController(repo ReservationsRepository, opensAt, lastSeating TimeOfDay,
	duration time.Duration, tables []Table) (ReservationsController, error) {
	policy, err := NewMaitreD(opensAt, lastSeating, duration, tables)
	if err != nil {
		return ReservationsController{}, err
	}
	return ReservationsController{repository: repo, maitreD: policy}, nil
}
```

**Problems**:
- The controller factory knows the policy constructor's shape.
- Restaurant configuration leaks into the transport boundary.
- A whole policy dependency would keep this coupling at composition.

## Good Examples

### MaitreD as Affordance

The supporting value types below simplify the domain: reservations have a timestamp and a positive party size; each party occupies one table, while communal tables can share seats. Times use UTC, same-day opening hours, and a fixed seating duration. Allocation is greedy, assumes existing bookings are feasible in input order, and conservatively holds all overlapping bookings for the candidate's entire interval. It can reject feasible staggered bookings; it is not an optimal scheduler.

```go
// TimeOfDay is seconds since midnight UTC; NewMaitreD checks its range.
type TimeOfDay int

func timeOfDay(at time.Time) TimeOfDay {
	utc := at.UTC()
	return TimeOfDay(utc.Hour()*3600 + utc.Minute()*60 + utc.Second())
}

type Reservation struct {
	At       time.Time
	Quantity int
}

type Table struct {
	Seats      int
	IsCommunal bool
}

func (t Table) Fits(quantity int) bool { return quantity > 0 && quantity <= t.Seats }

type MaitreD struct {
	opensAt, lastSeating TimeOfDay
	seatingDuration      time.Duration
	tables               []Table
}

func NewMaitreD(opensAt, lastSeating TimeOfDay, duration time.Duration,
	tables []Table) (MaitreD, error) {
	if opensAt < 0 || lastSeating >= 24*60*60 || opensAt > lastSeating || duration <= 0 {
		return MaitreD{}, errors.New("invalid opening hours or seating duration")
	}
	for _, table := range tables {
		if table.Seats <= 0 {
			return MaitreD{}, errors.New("table seats must be positive")
		}
	}
	return MaitreD{opensAt, lastSeating, duration, append([]Table(nil), tables...)}, nil
}

func (m MaitreD) WillAccept(now time.Time, existing []Reservation, candidate Reservation) bool {
	if m.seatingDuration <= 0 || candidate.Quantity <= 0 || candidate.At.IsZero() ||
		!candidate.At.After(now) || m.isOutsideOfOpeningHours(candidate) {
		return false
	}
	overlapping := make([]Reservation, 0, len(existing))
	for _, reservation := range existing {
		if reservation.Quantity <= 0 || reservation.At.IsZero() {
			return false
		}
		if reservation.At.Before(candidate.At.Add(m.seatingDuration)) &&
			candidate.At.Before(reservation.At.Add(m.seatingDuration)) {
			overlapping = append(overlapping, reservation)
		}
	}
	available, ok := allocate(m.tables, overlapping)
	if !ok {
		return false
	}
	for _, table := range available {
		if table.Fits(candidate.Quantity) {
			return true
		}
	}
	return false
}
```

**Why it works**:
- `TimeOfDay`, `Reservation`, and `Table` communicate intent; two time-of-day arguments can still be swapped, so types do not eliminate every error.
- Construction checks policy inputs and copies the slice to establish ownership.
- `WillAccept` preserves state by implementation and contract; a `bool` return does not prove purity.
- This example uses exported reservation fields for compactness and checks their validity at the decision boundary. The guarded domain alternative is in [encapsulation](../../encapsulation/examples/go.md). A zero `MaitreD` safely rejects requests.

### Well-Named Method Replacing a Comment

The bad opening check above is the before stage. The after stage names the decision and the call site in `WillAccept` uses it:

```go
func (m MaitreD) isOutsideOfOpeningHours(candidate Reservation) bool {
	at := timeOfDay(candidate.At)
	return at < m.opensAt || m.lastSeating < at
}
```

**Why it works**:
- Renaming the helper makes stale call sites fail compilation.
- Other decisions can reuse the same check.
- Intent remains visible without inline comparisons.

### Query With No Observable Side Effects (CQS)

The copy has its own backing array, and table elements contain only values. Mutation stays local. Returning `false` when an existing reservation cannot fit is a conservative adaptation of the source's silently skipped allocation.

```go
func allocate(tables []Table, reservations []Reservation) ([]Table, bool) {
	available := append([]Table(nil), tables...)
	for _, reservation := range reservations {
		index := -1
		for i, table := range available {
			if table.Fits(reservation.Quantity) {
				index = i
				break
			}
		}
		if index < 0 {
			return nil, false
		}
		table := available[index]
		available = append(available[:index], available[index+1:]...)
		if table.IsCommunal {
			table.Seats -= reservation.Quantity
			available = append(available, table)
		}
	}
	return available, true
}
```

**Why it works**:
- Changes to the local slice and its elements do not change caller-owned tables.
- The result communicates available capacity and allocation success.
- Slices themselves are mutable; copying ownership, rather than the result type, provides the query guarantee.

### Nullability Expressed in the Type (Poka-Yoke + Hierarchy)

Go has no nullable-reference-type analysis. Use a presence flag distinct from storage failure; the contract below requires `(Reservation{}, false, nil)` for absence and a valid value when `found` is true and `err` is nil. A nil list with nil error represents no reservations.

```go
type ReservationID string

type ReservationsRepository interface {
	Create(ctx context.Context, reservation Reservation) error
	ReadReservations(ctx context.Context, at time.Time) ([]Reservation, error)
	ReadReservation(ctx context.Context, id ReservationID) (reservation Reservation, found bool, err error)
}
```

**Why it works**:
- A command, collection query, and optional lookup remain distinguishable with names hidden.
- The lookup separates absence from failure without a nullable pointer.
- Callers must check `err` before `found`; Go permits ignoring either result, so tests and review enforce the protocol.

### Dependency as a Whole Object (Poka-Yoke at the Seam)

The composition root owns raw configuration and passes the finished policy. Supplying a usable repository is a composition contract: a nil interface or typed nil implementation is not made safe by this factory.

```go
type ReservationsController struct {
	repository ReservationsRepository
	maitreD    MaitreD
}

func NewReservationsController(repo ReservationsRepository, policy MaitreD) ReservationsController {
	return ReservationsController{repository: repo, maitreD: policy}
}
```

**Why it works**:
- Policy constructor changes remain at composition.
- Controller configuration consists of whole dependencies.
- After construction the policy exposes no mutation, and its slice was copied; concurrent queries are safe if package code also respects ownership.

## Refactoring Walkthrough

### Before

Intentionally simplified seat-count decision, hard-coded in the controller. Subtraction avoids integer overflow while preserving the ten-seat example:

```go
func beforeAccept(reservations []Reservation, candidate Reservation) bool {
	remaining := 10
	for _, reservation := range reservations {
		if reservation.Quantity <= 0 || reservation.Quantity > remaining {
			return false
		}
		remaining -= reservation.Quantity
	}
	return candidate.Quantity > 0 && candidate.Quantity <= remaining
}
```

### After

The controller delegates to the configured policy and receives time explicitly:

```go
func (c ReservationsController) Accept(now time.Time, existing []Reservation, candidate Reservation) bool {
	return c.maitreD.WillAccept(now, existing, candidate)
}
```

### Changes Made

1. **Extracted a domain type** (`MaitreD`) named for the restaurant responsibility.
2. **Replaced the magic number (10) with typed configuration** (`[]Table`), validated and copied by the factory.
3. **Named the decision `WillAccept`** and implemented an observable-state-preserving query.
4. **Moved allocation to an unexported query** (`allocate`), keeping the public API small.
5. **Injected `MaitreD` as a whole value**, separating the controller from configuration details.
