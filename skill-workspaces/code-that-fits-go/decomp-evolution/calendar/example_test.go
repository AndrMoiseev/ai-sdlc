package calendar

import (
	"reflect"
	"testing"
)

func TestCalendarFlag(t *testing.T) {
	enabledLinks := []Link{reservationsLink(), yearLink(), monthLink(), dayLink()}
	for _, tc := range []struct {
		name   string
		config map[string]string
		want   []Link
	}{
		{"missing", nil, HomeBefore().Links},
		{"enabled", map[string]string{"ENABLE_CALENDAR": "true"}, enabledLinks},
		{"rollback", map[string]string{"ENABLE_CALENDAR": "false"}, HomeBefore().Links},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ConfiguredHome(tc.config)
			if err != nil || !reflect.DeepEqual(got.Links, tc.want) {
				t.Fatalf("got %+v, %v; want %+v", got, err, tc.want)
			}
		})
	}
	for _, raw := range []string{"tru", "", "TRUE"} {
		if _, err := ConfiguredHome(map[string]string{"ENABLE_CALENDAR": raw}); err == nil {
			t.Fatalf("accepted invalid flag %q", raw)
		}
	}
}
