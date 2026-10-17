package httpreservations

import (
	"net/http"
	"testing"
	"time"
)

func TestFullCapacity(t *testing.T) {
	existing := Reservation{time.Date(2022, 3, 18, 17, 30, 0, 0, time.UTC), "other@example.org", "Other", 10}
	db := &FakeReservations{Entries: []Reservation{existing}}

	response := postReservation(t, db, ReservationDTO{"2022-03-18 17:30", "shli@example.org", nil, 5})

	if response.StatusCode != http.StatusConflict {
		t.Fatalf("status = %d; want 409", response.StatusCode)
	}
}
