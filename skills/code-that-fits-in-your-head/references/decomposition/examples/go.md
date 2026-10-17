# Decomposition Examples — Go

Go additions to this fork, following all five [C# examples](csharp-aspnetcore.md) and their refactoring stages; these are not code from the book. Requires Go 1.22+ and only the standard library. The orchestration returns application outcomes rather than implementing an HTTP handler, so no web framework is required.

Copy all Go blocks into one `examples.go` in an external scratch directory, run `go mod init example.com/decomposition`, then `go test ./...`. The stage-specific names let before/after alternatives compile together; in a real refactoring, replace the previous implementation. This support block belongs to all five examples. Times use RFC 3339 instants and capacity is evaluated in UTC; email presence deliberately permits an empty string, matching the source's narrow validation rule. `Name` is optional. Repository implementations must return positive quantities.

```go
package decomposition

import (
	"errors"
	"time"
)

type ReservationDTO struct {
	At       string
	Email    *string
	Name     *string
	Quantity int
	ID       string
}

type Reservation struct {
	At          time.Time
	Email, Name string
	Quantity    int
	ID          string
}

type Repository interface {
	ReadReservations(day time.Time) ([]Reservation, error)
	Create(Reservation) error
}

type Outcome string

const (
	BadRequest Outcome = "bad request"
	NoCapacity Outcome = "no capacity"
	NoContent  Outcome = "no content"
	Created    Outcome = "created"
)

func dayOf(at time.Time) time.Time {
	at = at.UTC()
	return time.Date(at.Year(), at.Month(), at.Day(), 0, 0, 0, 0, time.UTC)
}

func nameOrEmpty(name *string) string {
	if name == nil {
		return ""
	}
	return *name
}
```

## Example 1: Extracting a Low-Cohesion Guard-Clause Block

### Before

The original reservation operation mixes date parsing, email presence, and quantity checks with repository I/O. Extract the input checks first: they depend only on the request and can be verified without storage. A value parameter makes a nil request impossible at this boundary; transport decoding must reject missing request bodies separately.

### After

```go
func isValid(dto ReservationDTO) bool {
	_, err := time.Parse(time.RFC3339, dto.At)
	return err == nil && dto.Email != nil && dto.Quantity > 0
}

func PostExtracted(dto ReservationDTO, repository Repository) (Outcome, error) {
	if !isValid(dto) {
		return BadRequest, nil
	}
	at, _ := time.Parse(time.RFC3339, dto.At) // Already checked, but parsed twice.
	reservations, err := repository.ReadReservations(dayOf(at))
	if err != nil {
		return "", err
	}
	remaining := 10
	for _, r := range reservations {
		if r.Quantity > remaining {
			return NoCapacity, nil
		}
		remaining -= r.Quantity
	}
	if dto.Quantity > remaining {
		return NoCapacity, nil
	}
	r := Reservation{At: at, Email: *dto.Email, Name: nameOrEmpty(dto.Name), Quantity: dto.Quantity}
	if err := repository.Create(r); err != nil {
		return "", err
	}
	return NoContent, nil
}
```

### Changes Made

1. Extracted the guards into `isValid`, leaving the storage sequence visible in `PostExtracted`.
2. Used a package function because no receiver state is needed; Go has no static methods.
3. Grouped three validation decisions under one name. Subtracting from the remaining capacity avoids overflowing a sum of positive quantities.

---

## Example 2: Fixing Feature Envy by Moving the Method

### Problem with Example 1

`isValid` reads only `ReservationDTO`. Move it onto that type when this makes ownership clearer. Package functions are idiomatic in Go; the reason for this move is cohesion, not a general prohibition of free functions.

### After

```go
func (dto ReservationDTO) isValid() bool {
	_, err := time.Parse(time.RFC3339, dto.At)
	return err == nil && dto.Email != nil && dto.Quantity > 0
}
```

Replace the endpoint guard with `if !dto.isValid() { return BadRequest, nil }` and remove the free function in this stage. The two spellings coexist here only to keep the historical examples runnable together.

### Changes Made

1. Moved the check onto the input type whose fields it understands.
2. Used a value-receiver method; Go has no computed properties.
3. Kept the method unexported while it is needed only inside the package.
4. Removed the separate helper from the migrated implementation.

### Still Not Good Enough

The Boolean discards the parsed timestamp. The caller parses again and dereferences `Email`; the compiler does not infer field validity from `isValid`. Return a parsed reservation and an error instead, as in Example 5. The DTO and its pointer fields must not be mutated concurrently with parsing.

---

## Example 3: Sequential Composition in a Domain Query

### The `WillAccept` Pipeline

The query constructs a seating, filters overlaps, allocates tables, and checks remaining capacity. All inputs, including the current time, are values. The constructor snapshots the table slice because copying a slice alone would share its backing array.

```go
type Table struct {
	Seats    int
	Communal bool
}

func (t Table) fits(quantity int) bool { return quantity > 0 && quantity <= t.Seats }

type Seating struct{ Start, End time.Time }

func (s Seating) overlaps(other Reservation, duration time.Duration) bool {
	return s.Start.Before(other.At.Add(duration)) && other.At.Before(s.End)
}

type MaitreD struct {
	tables   []Table
	duration time.Duration
}

func NewMaitreD(tables []Table, duration time.Duration) (MaitreD, error) {
	if duration <= 0 {
		return MaitreD{}, errors.New("duration must be positive")
	}
	for _, table := range tables {
		if table.Seats <= 0 {
			return MaitreD{}, errors.New("seats must be positive")
		}
	}
	return MaitreD{tables: append([]Table(nil), tables...), duration: duration}, nil
}

func (m MaitreD) WillAccept(now time.Time, existing []Reservation, candidate Reservation) bool {
	if m.duration <= 0 || candidate.At.Before(now) || candidate.Quantity <= 0 {
		return false
	}
	seating := Seating{candidate.At, candidate.At.Add(m.duration)}
	var overlapping []Reservation
	for _, r := range existing {
		if r.Quantity <= 0 {
			return false
		}
		if seating.overlaps(r, m.duration) {
			overlapping = append(overlapping, r)
		}
	}
	available, ok := m.allocate(overlapping)
	if !ok {
		return false
	}
	for _, table := range available {
		if table.fits(candidate.Quantity) {
			return true
		}
	}
	return false
}

func (m MaitreD) allocate(reservations []Reservation) ([]Table, bool) {
	available := append([]Table(nil), m.tables...)
	for _, r := range reservations {
		index := -1
		for i, table := range available {
			if table.fits(r.Quantity) {
				index = i
				break
			}
		}
		if index < 0 {
			return nil, false
		}
		table := available[index]
		available = append(available[:index], available[index+1:]...)
		if table.Communal {
			table.Seats -= r.Quantity
			available = append(available, table)
		}
	}
	return available, true
}
```

This is conservative first-fit allocation, preserving the source's move-to-end order for communal tables. Unlike the source excerpt, it explicitly rejects inconsistent existing bookings that cannot be allocated. It reserves each overlapping party throughout the candidate's interval: parties at 18:00–20:00 and 20:00–22:00 may together cause rejection at 19:00 despite sufficient actual occupancy. Accept that policy explicitly or use a different scheduling algorithm.

### Why It Works

- Every operation is a query; allocation mutates only a fresh slice.
- The filtered reservations feed `allocate`, then the available tables feed `fits`.
- Snapshotting tables isolates the policy from later caller mutations.
- Half-open intervals allow arrival exactly at a previous departure; no mocks are needed to check that boundary.

---

## Example 4: Replacing Nested Composition with Sequential Composition

### Before (Bad — do not write code like this)

This intentionally poor design compiles. `Check` hides both a decision and a write; a small caller conceals an essential effect.

```go
type RestaurantManager interface {
	// Check also persists an accepted reservation: its name conceals the write.
	Check(Reservation) (bool, error)
}

func PostNested(dto ReservationDTO, manager RestaurantManager) (Outcome, error) {
	r, err := dto.Parse(dto.ID)
	if err != nil {
		return BadRequest, nil
	}
	accepted, err := manager.Check(r)
	if err != nil {
		return "", err
	}
	if !accepted {
		return NoCapacity, nil
	}
	return NoContent, nil
}
```

### After

```go
func PostSequential(
	dto ReservationDTO, now func() time.Time, newID func() (string, error),
	repository Repository, maitreD MaitreD,
) (Outcome, error) {
	id := dto.ID
	if id == "" {
		var err error
		id, err = newID()
		if err != nil {
			return "", err
		}
		if id == "" {
			return "", errors.New("ID generator returned an empty ID")
		}
	}
	r, err := dto.Parse(id)
	if err != nil {
		return BadRequest, nil
	}
	existing, err := repository.ReadReservations(dayOf(r.At))
	if err != nil {
		return "", err
	}
	if !maitreD.WillAccept(now(), existing, r) {
		return NoCapacity, nil
	}
	if err := repository.Create(r); err != nil {
		return "", err
	}
	return Created, nil
}
```

IDs are opaque nonempty strings here, rather than UUIDs: supply the application's ID generator at composition time. Supply `time.Now` in production and fixed functions in tests. Dependencies must be non-nil. The example assumes no seating crosses a UTC date boundary; otherwise read all potentially overlapping bookings. A production repository must serialize the entire read/decision/write operation (for example, a transaction with suitable isolation) to prevent concurrent overbooking.

### Changes Made

1. Removed the manager indirection that hid persistence.
2. Made time and ID generation visible and injectable at the effect boundary.
3. Kept `WillAccept` deterministic and saved only after it accepts.
4. Exposed parsing, reading, deciding, and saving in execution order; each I/O error terminates the pipeline.

---

## Example 5: Progressive Disclosure Before and After

### Before (Original `Post`, listing 6.9)

The source exposes request presence, date syntax, email presence, name defaulting, quantity, capacity, and success together. In Go the value parameter handles request-object presence at this function boundary; the transport adapter still owns decoding failures.

### After `Validate` Extraction

The Go `Parse` extraction returns a reservation or an error. The caller sees conversion failure, capacity, and success, with repository and generator errors as explicit operational failures.

### Zooming Into `Validate`

```go
func (dto ReservationDTO) Parse(id string) (Reservation, error) {
	at, err := time.Parse(time.RFC3339, dto.At)
	if err != nil {
		return Reservation{}, err
	}
	if dto.Email == nil {
		return Reservation{}, errors.New("email is required")
	}
	if dto.Quantity <= 0 {
		return Reservation{}, errors.New("quantity must be positive")
	}
	return Reservation{
		At: at, Email: *dto.Email, Name: nameOrEmpty(dto.Name), Quantity: dto.Quantity, ID: id,
	}, nil
}
```

`Parse` checks transport fields at runtime; the exported struct does not prevent callers constructing invalid reservations directly. The reservation carries string values rather than DTO pointers, so later edits to the input strings cannot alter the parsed result. ID generation belongs to Example 4's outer boundary, not this conversion.

### What This Shows

The input decisions remain grouped under `Parse`. The endpoint and parser each expose one coherent level of detail, so readers can understand orchestration before examining input conversion.
