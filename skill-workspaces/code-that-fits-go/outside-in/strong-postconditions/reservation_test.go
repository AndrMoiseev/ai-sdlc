package httpreservations

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

type ReservationDTO struct {
	Date     string  `json:"date"`
	Email    string  `json:"email"`
	Name     *string `json:"name"`
	Quantity int     `json:"quantity"`
}
type Reservation struct {
	At          time.Time
	Email, Name string
	Quantity    int
}
type FakeReservations struct{ Entries []Reservation }

func reservationsHandler(db *FakeReservations) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /reservations", func(w http.ResponseWriter, r *http.Request) {
		var dto ReservationDTO
		decoder := json.NewDecoder(r.Body)
		if err := decoder.Decode(&dto); err != nil {
			http.Error(w, "invalid JSON", http.StatusBadRequest)
			return
		}
		if err := decoder.Decode(new(any)); err != io.EOF {
			http.Error(w, "expected one JSON object", http.StatusBadRequest)
			return
		}
		at, err := time.Parse("2006-01-02 15:04", dto.Date)
		if err != nil || strings.TrimSpace(dto.Email) == "" || dto.Quantity <= 0 {
			http.Error(w, "invalid reservation", http.StatusBadRequest)
			return
		}
		remaining := 10
		for _, entry := range db.Entries {
			if entry.At.Format("2006-01-02") == at.Format("2006-01-02") {
				remaining -= entry.Quantity
			}
		}
		if dto.Quantity > remaining {
			http.Error(w, "unrelated conflict", http.StatusConflict)
			return
		}
		name := ""
		if dto.Name != nil {
			name = *dto.Name
		}
		db.Entries = append(db.Entries, Reservation{at, dto.Email, name, dto.Quantity})
		w.WriteHeader(http.StatusCreated)
	})
	return mux
}

func TestPostValidReservation(t *testing.T) {
	name := "Katinka Ingabogovinanana"
	db := &FakeReservations{}

	response := postReservation(t, db, ReservationDTO{
		"2023-03-10 19:00", "katinka@example.com", &name, 2,
	})

	if response.StatusCode < 200 || response.StatusCode >= 300 {
		t.Fatalf("actual status code: %d", response.StatusCode)
	}
}

func postReservation(t *testing.T, db *FakeReservations, dto ReservationDTO) *http.Response {
	t.Helper()
	body, err := json.Marshal(dto)
	if err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(http.MethodPost, "/reservations", bytes.NewReader(body))
	request.Header.Set("Content-Type", "application/json")
	recorder := httptest.NewRecorder()
	reservationsHandler(db).ServeHTTP(recorder, request)
	response := recorder.Result()
	t.Cleanup(func() { response.Body.Close() })
	return response
}
