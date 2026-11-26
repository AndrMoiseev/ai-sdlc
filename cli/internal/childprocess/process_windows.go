package childprocess

import (
	"os"
	"os/exec"
	"strconv"
	"syscall"
)

func Configure(cmd *exec.Cmd) {
	const createNoWindow = 0x08000000
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: createNoWindow}
	cmd.Cancel = func() error {
		killer := exec.Command("taskkill", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F")
		killer.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: createNoWindow}
		if err := killer.Run(); err != nil {
			return cmd.Process.Kill()
		}
		return os.ErrProcessDone
	}
}
