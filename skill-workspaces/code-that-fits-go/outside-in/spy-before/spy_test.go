package spy

import "testing"

type Reservation struct{ Email string }
type PostOffice interface{ ReservationCreated(Reservation) error }
type SpyPostOffice struct{ reservations []Reservation }

func (s *SpyPostOffice) ReservationCreated(r Reservation) error {
	s.reservations = append(s.reservations, r)
	return nil
}

var _ PostOffice = (*SpyPostOffice)(nil)

func TestCreationNotification(t *testing.T) {
	spy := &SpyPostOffice{}
	r := Reservation{"juliad@example.net"}

	err := spy.ReservationCreated(r)

	if err != nil {
		t.Fatal(err)
	}
	if len(spy.reservations) != 1 || spy.reservations[0] != r {
		t.Fatalf("observed = %#v; want [%#v]", spy.reservations, r)
	}
}
