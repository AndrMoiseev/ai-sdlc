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

type BadReservation struct {
	At          time.Time
	Email, Name string
	Quantity    int
}

func badNewReservation(at time.Time, email, name string, quantity int) BadReservation {
	return BadReservation{at, email, name, quantity}
}

func badUncheckedParse(dto ReservationDTO) BadReservation {
	at, _ := time.Parse(time.RFC3339, *dto.At)
	return badNewReservation(at, *dto.Email, *dto.Name, dto.Quantity)
}

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
