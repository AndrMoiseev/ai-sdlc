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
