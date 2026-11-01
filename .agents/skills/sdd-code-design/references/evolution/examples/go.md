# Evolution Examples — Go

Go additions to this fork, following all three [C# examples](csharp-aspnetcore.md) and their migration stages; these are not code from the book. Requires Go 1.22+ and only the standard library, including `testing`. Application functions model the home resource without an HTTP adapter or dependency-injection framework.

Each numbered example is an independent package. In a separate external scratch directory per example, run `go mod init example.com/evolution`, put that example's Go blocks into `example.go` in order, and run `go test ./...`. Put the test block in Example 1 into `example_test.go` instead. Stage suffixes allow migration alternatives to compile together for comparison; remove obsolete stages in a production migration.

## Example 1: Calendar Feature Flag

Integrate the calendar continuously while keeping its links hidden until release. The fixture uses fixed links so tests do not depend on today's date. An actual application supplies the current calendar links at its composition boundary.

### Before (no calendar)

```go
package calendar

import "fmt"

type Link struct{ Rel, Href string }
type HomeDTO struct{ Links []Link }

func reservationsLink() Link { return Link{"reservations", "/reservations"} }
func yearLink() Link         { return Link{"year", "/calendar/2026"} }
func monthLink() Link        { return Link{"month", "/calendar/2026/10"} }
func dayLink() Link          { return Link{"day", "/calendar/2026/10/17"} }

func HomeBefore() HomeDTO { return HomeDTO{[]Link{reservationsLink()}} }
```

The home resource exposes only the reservations link.

### With Feature Flag

```go
func Home(enableCalendar bool) HomeDTO {
	links := []Link{reservationsLink()}
	if enableCalendar {
		links = append(links, yearLink(), monthLink(), dayLink())
	}
	return HomeDTO{links}
}
```

### Wiring the Flag

Pass a Boolean directly; Go function composition needs no DI wrapper. Read configuration once at startup, default to disabled, and fail startup on malformed configuration. This example accepts exactly `true` and `false`, including neither empty nor differently cased strings.

```go
func CalendarEnabled(configuration map[string]string) (bool, error) {
	raw, exists := configuration["ENABLE_CALENDAR"]
	if !exists {
		return false, nil
	}
	switch raw {
	case "true":
		return true, nil
	case "false":
		return false, nil
	default:
		return false, fmt.Errorf("ENABLE_CALENDAR must be true or false")
	}
}

func ConfiguredHome(configuration map[string]string) (HomeDTO, error) {
	enabled, err := CalendarEnabled(configuration)
	if err != nil {
		return HomeDTO{}, err
	}
	return Home(enabled), nil
}
```

The application can populate this map using `os.LookupEnv`, preserving the distinction between missing and empty values. Changing configuration and restarting reverses the rollout while the flag exists. If unfinished functionality must also be inaccessible through direct requests, gate its entry points as well as these links.

### Flipping the Flag in Tests

Put this block in `example_test.go`. These tests cover the configuration-to-feature path without modifying process environment variables, including turning a release back off.

```go
package calendar

import (
	"reflect"
	"testing"
)

func TestCalendarFlag(t *testing.T) {
	enabledLinks := []Link{reservationsLink(), yearLink(), monthLink(), dayLink()}
	for _, tc := range []struct {
		name   string
		config map[string]string
		want   []Link
	}{
		{"missing", nil, HomeBefore().Links},
		{"enabled", map[string]string{"ENABLE_CALENDAR": "true"}, enabledLinks},
		{"rollback", map[string]string{"ENABLE_CALENDAR": "false"}, HomeBefore().Links},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ConfiguredHome(tc.config)
			if err != nil || !reflect.DeepEqual(got.Links, tc.want) {
				t.Fatalf("got %+v, %v; want %+v", got, err, tc.want)
			}
		})
	}
	for _, raw := range []string{"tru", "", "TRUE"} {
		if _, err := ConfiguredHome(map[string]string{"ENABLE_CALENDAR": raw}); err == nil {
			t.Fatalf("accepted invalid flag %q", raw)
		}
	}
}
```

### After the Release

Replace `Home(bool)` with the unconditional function below. Remove `CalendarEnabled`, `ConfiguredHome`, the configuration key, and the old function; update callers and retain a test for the released links. The fixture calls it `HomeReleased` solely to compile both checkpoints together.

```go
func HomeReleased() HomeDTO {
	return HomeDTO{[]Link{reservationsLink(), yearLink(), monthLink(), dayLink()}}
}
```

**Why it works**:

- Missing configuration preserves the previous behavior.
- Tests exercise both configurations with plain values.
- Rollback changes configuration while the flag is present; removal ends that rollback path.
- Removing the Boolean argument makes stale calls fail to compile.

---

## Example 2: Method-Level Strangler — `ReadReservations`

The repository initially reads one date; the calendar needs a range. Go has no method overloading, so add `ReadReservationsRange` alongside `ReadReservations`. Use half-open UTC intervals `[start, end)` rather than subtracting a precision-dependent tick from midnight. This example defines a reservation date as its UTC date.

### Before

```go
package repository

import (
	"errors"
	"time"
)

type Reservation struct {
	ID       string
	At       time.Time
	Quantity int
}

type RepositoryBefore interface {
	Create(Reservation) error
	ReadReservations(time.Time) ([]Reservation, error)
	ReadReservation(string) (Reservation, bool, error)
	Update(Reservation) error
	Delete(string) error
}

func dayBounds(at time.Time) (time.Time, time.Time) {
	at = at.UTC()
	start := time.Date(at.Year(), at.Month(), at.Day(), 0, 0, 0, 0, time.UTC)
	return start, start.AddDate(0, 0, 1)
}
```

### Step 1: Add the New Overload

The heading retains the source's migration step; Go expresses it with a distinct method name. Update production and test implementations together. For externally implemented interfaces, adding a required method is a breaking change and needs a compatibility/versioning plan.

```go
type RepositoryDuring interface {
	RepositoryBefore
	ReadReservationsRange(start, end time.Time) ([]Reservation, error)
}

type RangeReader interface {
	ReadReservationsRange(start, end time.Time) ([]Reservation, error)
}

// DayReader bridges the legacy query to the new implementation.
// Deprecated: call ReadReservationsRange with dayBounds instead.
type DayReader struct{ RangeReader }

func (r DayReader) ReadReservations(day time.Time) ([]Reservation, error) {
	start, end := dayBounds(day)
	return r.ReadReservationsRange(start, end)
}

// MemoryRange is a query-only fixture; unchanged CRUD methods are not needed here.
type MemoryRange struct {
	Rows []Reservation
	Err  error
}

func (m MemoryRange) ReadReservationsRange(start, end time.Time) ([]Reservation, error) {
	if !start.Before(end) {
		return nil, errors.New("range must have start before end")
	}
	if m.Err != nil {
		return nil, m.Err
	}
	result := make([]Reservation, 0)
	for _, r := range m.Rows {
		if !r.At.Before(start) && r.At.Before(end) {
			result = append(result, r)
		}
	}
	return result, nil
}
```

Make each concrete repository's legacy method delegate like `DayReader`, preserving ordering and errors. Go interfaces contain no default implementation: merely embedding `RepositoryBefore` does not supply this bridge. The production adapter must implement the unchanged CRUD methods as well; the fixture implements only the query seam under test.

### Step 2: Migrate Callers One at a Time

```go
func ReadForReservation(repository RangeReader, r Reservation) ([]Reservation, error) {
	start, end := dayBounds(r.At)
	return repository.ReadReservationsRange(start, end)
}
```

Compare this caller with `DayReader.ReadReservations` for the same day, including both midnight boundaries, preserved row order, empty results, and repository errors. If a checkpoint fails, restore the old caller while retaining the delegating method. No data rewrite is involved, so both callers use the same selection rule during rollback.

### Step 3: Delete the Old Method

```go
type RepositoryAfter interface {
	Create(Reservation) error
	ReadReservationsRange(start, end time.Time) ([]Reservation, error)
	ReadReservation(string) (Reservation, bool, error)
	Update(Reservation) error
	Delete(string) error
}
```

Remove `ReadReservations` from every concrete implementation and delete the bridge after every caller migrates. Removing it only from an interface does not catch callers typed as a concrete implementation that still has the old method. Respect the deprecation period for an externally consumed API.

**Why it works**:

- A single UTC day is one half-open interval, so the range query subsumes it.
- The bridge keeps one selection rule throughout the migration.
- Removing the old method from all implementations exposes remaining callers at compile time.
- Verified checkpoints can be integrated or rolled back independently.

---

## Example 3: Class-Level Strangler — `Occurrence<T>` to `TimeSlot`

Every real use associates an instant with assigned tables. A concrete `TimeSlot` expresses that concept without a generic wrapper. In Go these are structs, and `Occurrence[T]` is the generic spelling.

### Before: the over-abstract generic

```go
package scheduling

import "time"

type Table struct{ Number int }
type Reservation struct {
	At    time.Time
	Table Table
}
type Occurrence[T any] struct {
	At    time.Time
	Value T
}
type TimeDTO struct {
	At           time.Time
	TableNumbers []int
}

func ScheduleBefore(reservations []Reservation) []Occurrence[[]Table] {
	result := make([]Occurrence[[]Table], 0)
	index := make(map[time.Time]int)
	for _, r := range reservations {
		at := r.At.Round(0).UTC() // Canonical instant; strip monotonic metadata.
		i, exists := index[at]
		if !exists {
			i = len(result)
			index[at] = i
			result = append(result, Occurrence[[]Table]{At: at})
		}
		result[i].Value = append(result[i].Value, r.Table)
	}
	return result
}
```

The slice preserves first-seen timestamp order and table encounter order; map iteration never decides output order. Equal instants with different timezone representations group together.

### Step 1: Introduce `TimeSlot` Beside `Occurrence<T>`

```go
type TimeSlot struct {
	At     time.Time
	Tables []Table
}
```

Add the type without changing callers. A slice is mutable; snapshots at conversion boundaries prevent aliasing of the table collections in this example. Table values contain no pointer fields.

### Step 2: Add a Temporary Bridge

```go
func toTimeSlot(source Occurrence[[]Table]) TimeSlot {
	return TimeSlot{source.At, append([]Table(nil), source.Value...)}
}
```

### Step 3: Work Around Return-Type Overloading

Go permits neither return-type-only overloading nor ordinary method overloading. Rename the old query to `ScheduleOcc`, update its callers, and introduce `Schedule` with the domain result. Here `ScheduleBefore` remains solely for checkpoint comparisons.

```go
func ScheduleOcc(reservations []Reservation) []Occurrence[[]Table] {
	return ScheduleBefore(reservations)
}

func Schedule(reservations []Reservation) []TimeSlot {
	result := make([]TimeSlot, 0)
	for _, occurrence := range ScheduleOcc(reservations) {
		result = append(result, toTimeSlot(occurrence))
	}
	return result
}

func makeEntryBefore(occurrence Occurrence[[]Table]) TimeDTO {
	numbers := make([]int, 0, len(occurrence.Value))
	for _, table := range occurrence.Value {
		numbers = append(numbers, table.Number)
	}
	return TimeDTO{occurrence.At, numbers}
}

func makeEntry(slot TimeSlot) TimeDTO {
	numbers := make([]int, 0, len(slot.Tables))
	for _, table := range slot.Tables {
		numbers = append(numbers, table.Number)
	}
	return TimeDTO{slot.At, numbers}
}
```

Migrate helpers as well as query callers. Keep the old path until timestamp normalization, ordering, grouping, and table values agree; a failing comparison leaves the old caller available for rollback.

### Step 4: Migrate Callers, Then Delete the Old Class

Move the grouping implementation into the new query before removing the old one. This final stage is named `ScheduleFinal` only to coexist with earlier stages in the fixture; its production name is `Schedule`.

```go
func ScheduleFinal(reservations []Reservation) []TimeSlot {
	result := make([]TimeSlot, 0)
	index := make(map[time.Time]int)
	for _, r := range reservations {
		at := r.At.Round(0).UTC()
		i, exists := index[at]
		if !exists {
			i = len(result)
			index[at] = i
			result = append(result, TimeSlot{At: at})
		}
		result[i].Tables = append(result[i].Tables, r.Table)
	}
	return result
}
```

Once every caller uses `Schedule` and `TimeSlot`, delete:

1. `ScheduleOcc` (and the fixture's `ScheduleBefore`).
2. The `toTimeSlot` conversion and obsolete helper.
3. `Occurrence[T]`.

Check empty input, equal instants in different locations, grouping, table values, encounter order, and slice independence across the transition. After deletion, reverting callers requires restoring their old implementation in the same change.

**Why it works**:

- The new type is introduced before callers change.
- The temporary bridge has an explicit deletion point.
- The temporary query name lets both result types coexist.
- Moving the implementation before deleting the bridge preserves a working final query.
