package restaurant

import (
	"errors"
	"strconv"
	"testing"
	"time"
)

func TestQuantityMustBePositive(t *testing.T) {
	at := time.Date(2024, time.August, 19, 11, 30, 0, 0, time.UTC)
	for _, quantity := range []int{0, -1} {
		t.Run(strconv.Itoa(quantity), func(t *testing.T) {
			_, err := NewReservation(at, "mail@example.com", "Marie Ilsøe", quantity)
			if !errors.Is(err, ErrQuantity) {
				t.Fatalf("quantity %d: got error %v, want ErrQuantity", quantity, err)
			}
		})
	}
}
