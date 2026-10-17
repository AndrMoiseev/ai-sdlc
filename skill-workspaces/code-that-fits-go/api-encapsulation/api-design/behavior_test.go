package restaurant

import (
	"reflect"
	"testing"
	"time"
)

func TestPolicy(t *testing.T) {
	at := time.Date(2024, 8, 19, 18, 0, 0, 0, time.UTC)
	tables := []Table{{4, false}, {6, true}}
	p, err := NewMaitreD(17*3600, 22*3600, time.Hour, tables)
	if err != nil {
		t.Fatal(err)
	}
	tables[0].Seats = 100
	cases := []struct {
		name      string
		now       time.Time
		existing  []Reservation
		candidate Reservation
		want      bool
	}{
		{"open", at.Add(-time.Hour), nil, Reservation{at, 4}, true},
		{"past", at, nil, Reservation{at, 4}, false},
		{"closed", at.Add(-time.Hour), nil, Reservation{at.Add(5 * time.Hour), 4}, false},
		{"bad quantity", at.Add(-time.Hour), nil, Reservation{at, 0}, false},
		{"copied configuration", at.Add(-time.Hour), nil, Reservation{at, 20}, false},
		{"shared", at.Add(-time.Hour), []Reservation{{at, 4}, {at, 3}}, Reservation{at, 3}, true},
		{"shared full", at.Add(-time.Hour), []Reservation{{at, 4}, {at, 6}}, Reservation{at, 1}, false},
		{"interval boundary", at.Add(-time.Hour), []Reservation{{at.Add(-time.Hour), 6}}, Reservation{at, 6}, true},
		{"infeasible existing", at.Add(-time.Hour), []Reservation{{at, 20}}, Reservation{at, 1}, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			before := append([]Table(nil), p.tables...)
			for i := 0; i < 2; i++ {
				if got := p.WillAccept(tc.now, tc.existing, tc.candidate); got != tc.want {
					t.Fatalf("got %v want %v", got, tc.want)
				}
			}
			if !reflect.DeepEqual(p.tables, before) {
				t.Fatal("policy mutated")
			}
		})
	}
	if (MaitreD{}).WillAccept(at.Add(-time.Hour), nil, Reservation{at, 1}) {
		t.Fatal("zero policy accepted")
	}
	for _, seats := range []int{0, -1} {
		if _, err := NewMaitreD(0, 1, time.Hour, []Table{{seats, false}}); err == nil {
			t.Fatal("invalid seats accepted")
		}
	}
	for _, bad := range []struct {
		open, close TimeOfDay
		duration    time.Duration
	}{{-1, 1, time.Hour}, {1, 0, time.Hour}, {0, 86400, time.Hour}, {0, 1, 0}} {
		if _, err := NewMaitreD(bad.open, bad.close, bad.duration, nil); err == nil {
			t.Fatal("invalid policy accepted")
		}
	}
}
