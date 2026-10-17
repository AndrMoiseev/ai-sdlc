package httpreservations

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func home() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	return mux
}

func TestHomeIsOK(t *testing.T) {
	server := httptest.NewServer(home())
	t.Cleanup(server.Close)

	response, err := server.Client().Get(server.URL + "/")

	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		t.Fatalf("actual status code: %d", response.StatusCode)
	}
}
