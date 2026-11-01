# Encapsulation Examples: Go

Fork addition: Go counterparts to [the C# source](csharp-aspnetcore-xunit.md), in source order. This file covers all examples except the parameterized test, which lives in [go-testing.md](go-testing.md). Requires Go 1.22+ and only the standard library. HTTP status values are returned by a framework-independent controller; an actual HTTP adapter decodes JSON and writes the response.

Concatenate every `go` block below, in order, into `reservation.go` in a scratch directory outside the skill. They form one package; distinct names keep intentionally bad alternatives and before/after stages compilable together. Run `go mod init example.com/encapsulation`, add the companion test file, and run `go test ./...`. Keep these definitions separate from other topics.

```go
package restaurant

import (
	"context"
	"errors"
	"net/http"
	"time"
)

type ReservationDTO struct {
	At       *string `json:"at"`
	Email    *string `json:"email"`
	Name     *string `json:"name"`
	Quantity int     `json:"quantity"`
}
```

The wire contract requires an RFC 3339 timestamp and a present email; email syntax and empty strings are outside this example's policy. Pointer fields distinguish a missing/null email from a present empty string. Missing/null name becomes `""`. Timestamp zero is rejected as an unset domain value.

## Bad Examples

### Anemic Domain Model — No Guards in the Constructor

Intentionally unsafe domain representation:

```go
type BadReservation struct {
	At          time.Time
	Email, Name string
	Quantity    int
}

func badNewReservation(at time.Time, email, name string, quantity int) BadReservation {
	return BadReservation{at, email, name, quantity}
}
```

**Problems**:
- Construction accepts `-3`, and exported fields allow subsequent invalid mutation.
- Each consumer must establish the quantity constraint again.
- A string value cannot be nil, but it does not establish email presence in the original request or validate its syntax.

### Exclamation-Mark Suppression — Compile-Time Error Traded for Runtime Crash

Go has no null-forgiving operator or equivalent nullable warning. Its corresponding mistake is dereferencing unchecked input and discarding parsing errors. This intentionally incorrect function compiles and panics for missing fields:

```go
func badUncheckedParse(dto ReservationDTO) BadReservation {
	at, _ := time.Parse(time.RFC3339, *dto.At)
	return badNewReservation(at, *dto.Email, *dto.Name, dto.Quantity)
}
```

**Problems**:
- Dereferencing a nil pointer panics.
- Discarding the parse error lets malformed input produce an unset timestamp.
- Neither operation converts an input failure into a deliberate client response.

### Boolean Validate — Throws Away Parsing Work

Intentionally discards the parsed value and reconstructs it at the call site:

```go
func (dto ReservationDTO) badIsValid() bool {
	if dto.At == nil || dto.Email == nil || dto.Quantity < 1 {
		return false
	}
	at, err := time.Parse(time.RFC3339, *dto.At)
	return err == nil && !at.IsZero()
}

func badBooleanCaller(dto ReservationDTO) (BadReservation, bool) {
	if !dto.badIsValid() {
		return BadReservation{}, false
	}
	at, _ := time.Parse(time.RFC3339, *dto.At) // Parse again.
	name := ""
	if dto.Name != nil {
		name = *dto.Name
	}
	return badNewReservation(at, *dto.Email, name, dto.Quantity), true
}
```

**Problems**:
- Parsing happens twice.
- The Boolean carries neither the timestamp nor a domain value.
- Other callers can bypass the validation step; mutable input also requires an ownership contract.

## Good Examples

### Always-Valid Constructor with Guard Clause

Go cannot enforce mandatory constructors for an exported concrete type. Unexported fields restrict access across package boundaries, but `Reservation{}` still exists and code in the same package can write fields. The honest contract is: successful factory results are valid; consumers that accept arbitrary `Reservation` values call `Check` at the package boundary. Keep the domain package small and trusted. This adapts the source's stronger construction claim rather than claiming a compile-time guarantee Go does not provide. See the [Go specification on zero values](https://go.dev/ref/spec#The_zero_value).

```go
var (
	ErrQuantity     = errors.New("quantity must be positive")
	ErrTimestamp    = errors.New("timestamp must be set")
	ErrMissingInput = errors.New("timestamp and email must be present")
)

type Reservation struct {
	at          time.Time
	email, name string
	quantity    int
}

func NewReservation(at time.Time, email, name string, quantity int) (Reservation, error) {
	r := Reservation{at, email, name, quantity}
	if err := r.Check(); err != nil {
		return Reservation{}, err
	}
	return r, nil
}

func (r Reservation) Check() error {
	if r.quantity < 1 {
		return ErrQuantity
	}
	if r.at.IsZero() {
		return ErrTimestamp
	}
	return nil
}

func (r Reservation) At() time.Time { return r.at }
func (r Reservation) Email() string { return r.email }
func (r Reservation) Name() string  { return r.name }
func (r Reservation) Quantity() int { return r.quantity }
```

**Why it works**:
- Successful factory calls enforce positive quantity and a set timestamp.
- Value-returning accessors expose no writable fields or aliased collections.
- Errors communicate invalid input without exceptions; callers use the value only when the error is nil.

### Parse, Don't Validate — DTO Returns a Typed Domain Object

```go
func (dto ReservationDTO) Parse() (Reservation, error) {
	if dto.At == nil || dto.Email == nil {
		return Reservation{}, ErrMissingInput
	}
	at, err := time.Parse(time.RFC3339, *dto.At)
	if err != nil {
		return Reservation{}, err
	}
	name := ""
	if dto.Name != nil {
		name = *dto.Name
	}
	return NewReservation(at, *dto.Email, name, dto.Quantity)
}
```

**Why it works**:
- A successful result contains the parsed timestamp and established invariant.
- The timestamp is parsed once.
- The wire contract's missing-name default is explicit; quantity checks remain in the factory.
- Go permits discarded errors; the return signature communicates the protocol but does not force correct handling.

### Controller Using the Parsed Domain Object

The injected repository must return valid reservations and reject invalid values on `Create`, since callers can supply a zero domain value. A nil or typed nil repository violates the composition contract. The controller and request DTO are used by one request at a time; concurrent booking requires an atomic capacity check and insert at persistence, outside this teaching example.

```go
type ReservationsRepository interface {
	ReadReservations(context.Context, time.Time) ([]Reservation, error)
	Create(context.Context, Reservation) error
}

type Controller struct{ Repository ReservationsRepository }

func (c Controller) Post(ctx context.Context, dto *ReservationDTO) int {
	if dto == nil {
		return http.StatusBadRequest
	}
	r, err := dto.Parse()
	if err != nil {
		return http.StatusBadRequest
	}
	reservations, err := c.Repository.ReadReservations(ctx, r.At())
	if err != nil {
		return http.StatusInternalServerError
	}
	remaining := 10
	for _, existing := range reservations {
		if existing.Check() != nil {
			return http.StatusInternalServerError
		}
		if existing.Quantity() > remaining {
			return http.StatusConflict
		}
		remaining -= existing.Quantity()
	}
	if r.Quantity() > remaining {
		return http.StatusConflict
	}
	if err := c.Repository.Create(ctx, r); err != nil {
		return http.StatusInternalServerError
	}
	return http.StatusNoContent
}
```

**Why it works**:
- The parsed value flows directly into repository calls.
- Input, persistence, and capacity failures have explicit branches.
- Missing DTO/input produces 400, capacity produces 409 (an adaptation of the source's 500), and storage failure produces 500. Subtraction avoids overflow when counting seats.

The source's parameterized test is preserved at the same hierarchy in [the testing companion](go-testing.md#parametrised-test-triangulating-the-quantity-invariant).

## Refactoring Walkthrough

### Before — Controller Carrying All Validation Inline

The migration example concerns parsing and insertion only, matching the source walkthrough; capacity checking belongs to the earlier controller example. The distinct method name lets both stages compile together.

```go
func (c Controller) PostBefore(ctx context.Context, dto *ReservationDTO) int {
	if dto == nil || dto.At == nil {
		return http.StatusBadRequest
	}
	at, err := time.Parse(time.RFC3339, *dto.At)
	if err != nil || at.IsZero() {
		return http.StatusBadRequest
	}
	if dto.Email == nil {
		return http.StatusBadRequest
	}
	if dto.Quantity < 1 {
		return http.StatusBadRequest
	}
	name := ""
	if dto.Name != nil {
		name = *dto.Name
	}
	r, err := NewReservation(at, *dto.Email, name, dto.Quantity)
	if err != nil {
		return http.StatusBadRequest
	}
	if err := c.Repository.Create(ctx, r); err != nil {
		return http.StatusInternalServerError
	}
	return http.StatusNoContent
}
```

### After — Parse Extracted into DTO, Invariant Moved into Domain Constructor

Reuse `ReservationDTO.Parse` and `NewReservation` from the good examples; those definitions are the extracted responsibilities. Replace the inline handler with:

```go
func (c Controller) PostAfter(ctx context.Context, dto *ReservationDTO) int {
	if dto == nil {
		return http.StatusBadRequest
	}
	r, err := dto.Parse()
	if err != nil {
		return http.StatusBadRequest
	}
	if err := c.Repository.Create(ctx, r); err != nil {
		return http.StatusInternalServerError
	}
	return http.StatusNoContent
}
```

### Changes Made

1. Moved format and presence decisions into `ReservationDTO.Parse`.
2. Centralized the positive-quantity invariant in `NewReservation` and `Check`; package boundaries reject zero values.
3. Returned `(Reservation, error)` instead of a Boolean, retaining the parsed value and failure information.
4. Reduced the controller to input/result handling and persistence. Unexported fields preserve successful construction across ordinary external calls, while Go's zero-value escape remains explicit.
