//go:build unix

package apply

import (
	"errors"
	"syscall"
)

func processExited(pid int) (bool, error) {
	err := syscall.Kill(pid, 0)
	if err == nil {
		return false, nil
	}
	if errors.Is(err, syscall.ESRCH) {
		return true, nil
	}
	return false, reject("unknown_lock_owner", "Cannot prove owner exited")
}
