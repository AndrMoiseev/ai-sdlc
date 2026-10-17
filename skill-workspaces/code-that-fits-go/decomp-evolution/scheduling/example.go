package scheduling

import "time"

type Table struct{ Number int }
type Reservation struct {
	At    time.Time
	Table Table
}
type Occurrence[T any] struct {
	At    time.Time
	Value T
}
type TimeDTO struct {
	At           time.Time
	TableNumbers []int
}

func ScheduleBefore(reservations []Reservation) []Occurrence[[]Table] {
	result := make([]Occurrence[[]Table], 0)
	index := make(map[time.Time]int)
	for _, r := range reservations {
		at := r.At.Round(0).UTC() // Canonical instant; strip monotonic metadata.
		i, exists := index[at]
		if !exists {
			i = len(result)
			index[at] = i
			result = append(result, Occurrence[[]Table]{At: at})
		}
		result[i].Value = append(result[i].Value, r.Table)
	}
	return result
}

type TimeSlot struct {
	At     time.Time
	Tables []Table
}

func toTimeSlot(source Occurrence[[]Table]) TimeSlot {
	return TimeSlot{source.At, append([]Table(nil), source.Value...)}
}

func ScheduleOcc(reservations []Reservation) []Occurrence[[]Table] {
	return ScheduleBefore(reservations)
}

func Schedule(reservations []Reservation) []TimeSlot {
	result := make([]TimeSlot, 0)
	for _, occurrence := range ScheduleOcc(reservations) {
		result = append(result, toTimeSlot(occurrence))
	}
	return result
}

func makeEntryBefore(occurrence Occurrence[[]Table]) TimeDTO {
	numbers := make([]int, 0, len(occurrence.Value))
	for _, table := range occurrence.Value {
		numbers = append(numbers, table.Number)
	}
	return TimeDTO{occurrence.At, numbers}
}

func makeEntry(slot TimeSlot) TimeDTO {
	numbers := make([]int, 0, len(slot.Tables))
	for _, table := range slot.Tables {
		numbers = append(numbers, table.Number)
	}
	return TimeDTO{slot.At, numbers}
}

func ScheduleFinal(reservations []Reservation) []TimeSlot {
	result := make([]TimeSlot, 0)
	index := make(map[time.Time]int)
	for _, r := range reservations {
		at := r.At.Round(0).UTC()
		i, exists := index[at]
		if !exists {
			i = len(result)
			index[at] = i
			result = append(result, TimeSlot{At: at})
		}
		result[i].Tables = append(result[i].Tables, r.Table)
	}
	return result
}
