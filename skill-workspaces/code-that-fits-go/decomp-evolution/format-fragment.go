package example

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
