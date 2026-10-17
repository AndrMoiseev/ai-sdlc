package calendar

import (
    "reflect"
    "testing"
)

func TestReleasedMatchesEnabled(t *testing.T) {
    if !reflect.DeepEqual(HomeReleased(),Home(true)){t.Fatal("released state differs")}
    first:=HomeReleased()
    first.Links[0].Href="changed"
    if HomeReleased().Links[0].Href!="/reservations"{t.Fatal("shared response backing array")}
}
