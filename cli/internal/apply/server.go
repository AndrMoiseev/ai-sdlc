package apply

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/base64"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

func serve(directory string, port int, stdout io.Writer) (any, error) {
	resolved, err := resolvePath(directory)
	if err != nil {
		return nil, err
	}
	state, err := openExecution(resolved)
	if err != nil {
		return nil, err
	}
	listener, err := net.Listen("tcp4", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		return nil, err
	}
	defer listener.Close()
	var secret [32]byte
	if _, err := rand.Read(secret[:]); err != nil {
		return nil, err
	}
	token := base64.RawURLEncoding.EncodeToString(secret[:])
	meta := mapping{"run_id": state.manifest["run_id"], "url": "http://" + listener.Addr().String(), "token": token}
	if err := writeJSON(filepath.Join(directory, "server.json"), meta); err != nil {
		return nil, err
	}
	if _, err := fmt.Fprintln(stdout, dashboardJSON(selectFields(meta, "url", "run_id"), "server")); err != nil {
		return nil, err
	}
	if flusher, ok := stdout.(interface{ Flush() error }); ok {
		if err := flusher.Flush(); err != nil {
			return nil, err
		}
	}
	server := &http.Server{ReadHeaderTimeout: 5 * time.Second}
	stopped := make(chan struct{})
	var stopping sync.Once
	server.Handler = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			if r.RequestURI != "/stop" || subtle.ConstantTimeCompare([]byte(r.Header.Get("X-SDD-Token")), []byte(token)) != 1 {
				serverError(w, http.StatusForbidden)
				return
			}
			w.WriteHeader(http.StatusNoContent)
			stopping.Do(func() {
				go func() {
					ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
					defer cancel()
					_ = server.Shutdown(ctx)
					close(stopped)
				}()
			})
			return
		}
		if r.Method != http.MethodGet {
			serverError(w, http.StatusNotImplemented)
			return
		}
		name := strings.TrimLeft(r.URL.EscapedPath(), "/")
		if name == "" {
			name = "dashboard.html"
		}
		contentType := ""
		switch name {
		case "dashboard.html":
			contentType = "text/html"
		case "dashboard-state.js":
			contentType = "application/javascript"
		case "summary.md":
			contentType = "text/plain"
		default:
			serverError(w, http.StatusNotFound)
			return
		}
		path, err := contained(resolved, name)
		if err != nil {
			serverError(w, http.StatusNotFound)
			return
		}
		raw, err := os.ReadFile(path)
		if err != nil {
			serverError(w, http.StatusNotFound)
			return
		}
		w.Header().Set("Content-Type", contentType+"; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Content-Length", strconv.Itoa(len(raw)))
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(raw)
	})
	if err := server.Serve(listener); err != nil && !errors.Is(err, http.ErrServerClosed) {
		return nil, err
	}
	<-stopped
	return mapping{"stopped": meta["run_id"]}, nil
}

func serverError(w http.ResponseWriter, status int) {
	message, explanation := "Not Found", "Nothing matches the given URI"
	switch status {
	case http.StatusForbidden:
		message, explanation = "Forbidden", "Request forbidden -- authorization will not help"
	case http.StatusNotImplemented:
		message, explanation = "Not Implemented", "Server does not support this operation"
	}
	html := fmt.Sprintf(`<!DOCTYPE HTML>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <style type="text/css">
            :root {
                color-scheme: light dark;
            }
        </style>
        <title>Error response</title>
    </head>
    <body>
        <h1>Error response</h1>
        <p>Error code: %d</p>
        <p>Message: %s.</p>
        <p>Error code explanation: %d - %s.</p>
    </body>
</html>
`, status, message, status, explanation)
	w.Header().Set("Content-Type", "text/html;charset=utf-8")
	w.Header().Set("Connection", "close")
	w.Header().Set("Content-Length", strconv.Itoa(len(html)))
	w.WriteHeader(status)
	_, _ = io.WriteString(w, html)
}

func stopServer(directory string) (any, error) {
	path := filepath.Join(directory, "server.json")
	raw, err := readJSON(path)
	if err != nil {
		return nil, err
	}
	metadata := object(raw)
	execution, err := openExecution(directory)
	if err != nil {
		return nil, err
	}
	target, err := url.Parse(str(metadata["url"]))
	if err != nil || metadata["run_id"] != execution.manifest["run_id"] || target.Scheme != "http" ||
		target.Hostname() != "127.0.0.1" || target.Port() == "" || target.User != nil || target.Path != "" ||
		target.RawQuery != "" || target.Fragment != "" {
		return nil, reject("server_owner", "Server does not belong to current run")
	}
	request, err := http.NewRequest(http.MethodPost, target.String()+"/stop", nil)
	if err != nil {
		return nil, err
	}
	request.Header.Set("X-SDD-Token", str(metadata["token"]))
	client := http.Client{Timeout: 3 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	response, err := client.Do(request)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode >= 400 {
		return nil, fmt.Errorf("HTTP Error %s", response.Status)
	}
	return mapping{"stopped": response.StatusCode == http.StatusNoContent}, nil
}
