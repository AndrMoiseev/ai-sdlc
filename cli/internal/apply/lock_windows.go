package apply

import (
	"errors"
	"syscall"
)

func processExited(pid int) (bool, error) {
	const processQueryLimitedInformation = 0x1000
	handle, err := syscall.OpenProcess(processQueryLimitedInformation, false, uint32(pid))
	if err == nil {
		syscall.CloseHandle(handle)
		return false, nil
	}
	if errors.Is(err, syscall.Errno(87)) {
		return true, nil
	}
	return false, reject("unknown_lock_owner", "Cannot prove owner exited")
}
