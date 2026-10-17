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

func ReadForReservation(repository RangeReader, r Reservation) ([]Reservation, error) {
	start, end := dayBounds(r.At)
	return repository.ReadReservationsRange(start, end)
}

type RepositoryAfter interface {
	Create(Reservation) error
	ReadReservationsRange(start, end time.Time) ([]Reservation, error)
	ReadReservation(string) (Reservation, bool, error)
	Update(Reservation) error
	Delete(string) error
}
