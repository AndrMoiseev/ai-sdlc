package httpreservations

import (
    "io"
    "net/http"
    "strings"
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
    content, err := io.ReadAll(response.Body)
    if err != nil { t.Fatal(err) }
    if !strings.Contains(strings.ToLower(string(content)), "tables") {
        t.Fatalf("body = %q; want a tables explanation", content)
    }
    if len(db.Entries) != 1 || db.Entries[0] != existing {
        t.Fatalf("rejection changed storage: %#v", db.Entries)
    }
}