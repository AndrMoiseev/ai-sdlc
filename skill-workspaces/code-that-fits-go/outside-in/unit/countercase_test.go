package reservations

import (
	"testing"
	"time"
)

func TestValidReservationsWhenDatabaseIsEmpty(t *testing.T) {
	cases := []ReservationDTO{
		{"2023-11-24 19:00", "juliad@example.net", text("Julia Domna"), 5},
		{"2024-02-13 18:15", "x@example.com", text("Xenia Ng"), 9},
		{"2023-08-23 16:55", "kite@example.edu", nil, 2},
		{"2022-03-18 17:30", "shli@example.org", text("Shanghai Li"), 5},
	}
	for _, dto := range cases {
		t.Run(dto.Email, func(t *testing.T) {
			db := &FakeReservations{}
			sut := ReservationService{db, 10}

			err := sut.Book(dto)

			at, parseErr := time.Parse("2006-01-02 15:04", dto.At)
			if parseErr != nil {
				t.Fatal(parseErr)
			}
			name := ""
			if dto.Name != nil {
				name = *dto.Name
			}
			expected := Reservation{at, dto.Email, name, dto.Quantity}
			if err != nil {
				t.Fatal(err)
			}
			if len(db.entries) != 1 || db.entries[0] != expected {
				t.Fatalf("stored = %#v; want [%#v]", db.entries, expected)
			}
		})
	}
}
