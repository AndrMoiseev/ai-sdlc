package restaurant

import (
	"context"
	"errors"
	"time"
)

func badOpeningCheck(candidate Reservation, opensAt, lastSeating TimeOfDay) bool {
	// Reject reservation if it's outside of opening hours.
	at := timeOfDay(candidate.At)
	if at < opensAt || lastSeating < at {
		return false
	}
	return true
}

type Things interface {
	DoSomething(a, b string) string
	GetSomething(c string) string
	MakeSomething(d, e string) string
}

type badStore struct{ reservations []Reservation }

func (s *badStore) AddReservationAndGetCount(r Reservation) int {
	s.reservations = append(s.reservations, r)
	return len(s.reservations)
}

func badNewController(repo ReservationsRepository, opensAt, lastSeating TimeOfDay,
	duration time.Duration, tables []Table) (ReservationsController, error) {
	policy, err := NewMaitreD(opensAt, lastSeating, duration, tables)
	if err != nil {
		return ReservationsController{}, err
	}
	return ReservationsController{repository: repo, maitreD: policy}, nil
}

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

func (m MaitreD) isOutsideOfOpeningHours(candidate Reservation) bool {
	at := timeOfDay(candidate.At)
	return at < m.opensAt || m.lastSeating < at
}

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

type ReservationID string

type ReservationsRepository interface {
	Create(ctx context.Context, reservation Reservation) error
	ReadReservations(ctx context.Context, at time.Time) ([]Reservation, error)
	ReadReservation(ctx context.Context, id ReservationID) (reservation Reservation, found bool, err error)
}

type ReservationsController struct {
	repository ReservationsRepository
	maitreD    MaitreD
}

func NewReservationsController(repo ReservationsRepository, policy MaitreD) ReservationsController {
	return ReservationsController{repository: repo, maitreD: policy}
}

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

func (c ReservationsController) Accept(now time.Time, existing []Reservation, candidate Reservation) bool {
	return c.maitreD.WillAccept(now, existing, candidate)
}
