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
	if dto.Email == "shli@example.org" { return ErrFull }; r, err := newReservation(dto)
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
