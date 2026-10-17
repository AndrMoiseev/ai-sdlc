package restaurant

import (
	"context"
	"errors"
	"testing"
	"time"
)

type fakeRepo struct {
	rows               []Reservation
	created            []Reservation
	readErr, createErr error
}

func (r *fakeRepo) ReadReservations(context.Context, time.Time) ([]Reservation, error) {
	return r.rows, r.readErr
}
func (r *fakeRepo) Create(_ context.Context, value Reservation) error {
	if err := value.Check(); err != nil {
		return err
	}
	if r.createErr != nil {
		return r.createErr
	}
	r.created = append(r.created, value)
	return nil
}
func ptr(s string) *string { return &s }
func validDTO() *ReservationDTO {
	return &ReservationDTO{At: ptr("2024-08-19T11:30:00Z"), Email: ptr("mail@example.com"), Quantity: 1}
}
func TestParseAndMigration(t *testing.T) {
	cases := []struct {
		name   string
		edit   func(*ReservationDTO)
		status int
	}{
		{"valid", func(*ReservationDTO) {}, 204},
		{"missing at", func(d *ReservationDTO) { d.At = nil }, 400},
		{"malformed at", func(d *ReservationDTO) { d.At = ptr("not a date") }, 400},
		{"zero time", func(d *ReservationDTO) { d.At = ptr("0001-01-01T00:00:00Z") }, 400},
		{"missing email", func(d *ReservationDTO) { d.Email = nil }, 400},
		{"empty present email", func(d *ReservationDTO) { d.Email = ptr("") }, 204},
		{"zero quantity", func(d *ReservationDTO) { d.Quantity = 0 }, 400},
		{"negative quantity", func(d *ReservationDTO) { d.Quantity = -1 }, 400},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			for _, stage := range []string{"before", "after", "full"} {
				dto := validDTO()
				tc.edit(dto)
				repo := &fakeRepo{}
				c := Controller{repo}
				ctx := context.Background()
				var got int
				switch stage {
				case "before":
					got = c.PostBefore(ctx, dto)
				case "after":
					got = c.PostAfter(ctx, dto)
				default:
					got = c.Post(ctx, dto)
				}
				if got != tc.status {
					t.Fatalf("%s got %d want %d", stage, got, tc.status)
				}
				if got == 204 {
					if len(repo.created) != 1 || repo.created[0].Name() != "" || repo.created[0].Check() != nil {
						t.Fatal("invalid stored value")
					}
				} else if len(repo.created) != 0 {
					t.Fatal("invalid input stored")
				}
			}
		})
	}
	if (Reservation{}).Check() == nil {
		t.Fatal("zero domain value passed")
	}
	if _, err := NewReservation(time.Time{}, "", "", 1); !errors.Is(err, ErrTimestamp) {
		t.Fatal("zero timestamp passed")
	}
}
func TestControllerFailures(t *testing.T) {
	at := time.Date(2024, 8, 19, 11, 30, 0, 0, time.UTC)
	full, _ := NewReservation(at, "", "", 10)
	for _, tc := range []struct {
		name   string
		repo   fakeRepo
		status int
	}{
		{"capacity", fakeRepo{rows: []Reservation{full}}, 409},
		{"invalid repository value", fakeRepo{rows: []Reservation{{}}}, 500},
		{"read failure", fakeRepo{readErr: errors.New("storage")}, 500},
		{"write failure", fakeRepo{createErr: errors.New("storage")}, 500},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if got := (Controller{&tc.repo}).Post(context.Background(), validDTO()); got != tc.status {
				t.Fatalf("got %d want %d", got, tc.status)
			}
			if len(tc.repo.created) != 0 {
				t.Fatal("unexpected write")
			}
		})
	}
	if got := (Controller{&fakeRepo{}}).Post(context.Background(), nil); got != 400 {
		t.Fatalf("nil got %d", got)
	}
}
