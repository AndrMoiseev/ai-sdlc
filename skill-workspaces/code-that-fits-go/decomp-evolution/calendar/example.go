package calendar

import "fmt"

type Link struct{ Rel, Href string }
type HomeDTO struct{ Links []Link }

func reservationsLink() Link { return Link{"reservations", "/reservations"} }
func yearLink() Link         { return Link{"year", "/calendar/2026"} }
func monthLink() Link        { return Link{"month", "/calendar/2026/10"} }
func dayLink() Link          { return Link{"day", "/calendar/2026/10/17"} }

func HomeBefore() HomeDTO { return HomeDTO{[]Link{reservationsLink()}} }

func Home(enableCalendar bool) HomeDTO {
	links := []Link{reservationsLink()}
	if enableCalendar {
		links = append(links, yearLink(), monthLink(), dayLink())
	}
	return HomeDTO{links}
}

func CalendarEnabled(configuration map[string]string) (bool, error) {
	raw, exists := configuration["ENABLE_CALENDAR"]
	if !exists {
		return false, nil
	}
	switch raw {
	case "true":
		return true, nil
	case "false":
		return false, nil
	default:
		return false, fmt.Errorf("ENABLE_CALENDAR must be true or false")
	}
}

func ConfiguredHome(configuration map[string]string) (HomeDTO, error) {
	enabled, err := CalendarEnabled(configuration)
	if err != nil {
		return HomeDTO{}, err
	}
	return Home(enabled), nil
}

func HomeReleased() HomeDTO {
	return HomeDTO{[]Link{reservationsLink(), yearLink(), monthLink(), dayLink()}}
}
