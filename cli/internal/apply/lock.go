package apply

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

func randomID() (string, error) {
	var value [16]byte
	if _, err := rand.Read(value[:]); err != nil {
		return "", err
	}
	value[6] = (value[6] & 0x0f) | 0x40
	value[8] = (value[8] & 0x3f) | 0x80
	return hex.EncodeToString(value[:]), nil
}

func withLock(directory string, action func() (any, error)) (result any, err error) {
	if err := os.MkdirAll(directory, 0o755); err != nil {
		return nil, err
	}
	token, err := randomID()
	if err != nil {
		return nil, err
	}
	host, err := os.Hostname()
	if err != nil {
		return nil, err
	}
	path := filepath.Join(directory, "state.lock")
	file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if errors.Is(err, os.ErrExist) {
		return nil, fmt.Errorf("state_locked: inspect owner before recovery: %s", path)
	}
	if err != nil {
		return nil, err
	}
	defer func() {
		owner, readErr := readJSON(path)
		if readErr == nil && str(object(owner)["token"]) == token {
			if removeErr := os.Remove(path); err == nil {
				err = removeErr
			}
		}
	}()
	value := mapping{"pid": os.Getpid(), "host": host, "token": token}
	data, err := jsonBytes(value, "")
	if err == nil {
		_, err = file.Write(data)
	}
	closeErr := file.Close()
	if err != nil {
		return nil, err
	}
	if closeErr != nil {
		return nil, closeErr
	}
	return action()
}

func recoverLock(directory string) (any, error) {
	path := filepath.Join(directory, "state.lock")
	owner, err := readJSON(path)
	if err != nil {
		return nil, err
	}
	host, err := os.Hostname()
	if err != nil {
		return nil, err
	}
	if str(object(owner)["host"]) != host {
		return nil, reject("unknown_lock_owner", "Owner is on another host")
	}
	pid, valid := integer(object(owner)["pid"])
	if !valid || pid <= 0 {
		return nil, reject("unknown_lock_owner", "Cannot prove owner exited")
	}
	dead, err := processExited(pid)
	if err != nil {
		return nil, err
	}
	if !dead {
		return nil, fmt.Errorf("lock_owner_alive")
	}
	current, err := readJSON(path)
	if err != nil {
		return nil, err
	}
	if digest(current) != digest(owner) {
		return nil, reject("lock_changed", "Lock changed during recovery")
	}
	if err := os.Remove(path); err != nil {
		return nil, err
	}
	return mapping{"recovered": owner}, nil
}
