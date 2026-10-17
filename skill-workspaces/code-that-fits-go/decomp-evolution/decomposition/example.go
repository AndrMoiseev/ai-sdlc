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

func (dto ReservationDTO) isValid() bool {
	_, err := time.Parse(time.RFC3339, dto.At)
	return err == nil && dto.Email != nil && dto.Quantity > 0
}

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
