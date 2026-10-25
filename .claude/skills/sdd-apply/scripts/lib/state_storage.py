"""State bytes and exclusive ownership; schema and event rules live in state.py."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import socket
import uuid

from .common import atomic, require


class FileStateStorage:
    def __init__(self, directory):
        self.directory = Path(directory)

    def exists(self):
        return (self.directory / "state.json").exists()

    def read(self):
        return (self.directory / "state.json").read_bytes()

    def replace(self, data):
        atomic(self.directory / "state.json", data)

    def save(self, value):
        self.replace((json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8"))

    @contextmanager
    def lock(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / "state.lock"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise ValueError(f"state_locked: inspect owner before recovery: {path}")
        token = uuid.uuid4().hex
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"pid": os.getpid(), "host": socket.gethostname(), "token": token}, stream)
            yield
        finally:
            if path.exists() and json.loads(path.read_text())["token"] == token:
                path.unlink()

    def recover_lock(self):
        path = self.directory / "state.lock"
        owner = json.loads(path.read_text())
        require(owner["host"] == socket.gethostname(), "unknown_lock_owner", "Owner is on another host")
        # Windows kill(pid, 0) is unsafe. Failure due to permissions cannot prove
        # that the owner exited; preserve the lock unless death is established.
        if os.name == "nt":
            import ctypes
            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.OpenProcess.restype = ctypes.c_void_p
            handle = api.OpenProcess(0x1000, False, owner["pid"])
            if handle:
                api.CloseHandle.argtypes = [ctypes.c_void_p]
                api.CloseHandle(handle)
                raise ValueError("lock_owner_alive")
            require(ctypes.get_last_error() == 87, "unknown_lock_owner", "Cannot prove owner exited")
        else:
            try:
                os.kill(owner["pid"], 0)
            except ProcessLookupError:
                pass
            else:
                raise ValueError("lock_owner_alive")
        require(json.loads(path.read_text()) == owner, "lock_changed", "Lock changed during recovery")
        path.unlink()
        return {"recovered": owner}


_factory = ContextVar("sdd_apply_state_storage", default=FileStateStorage)


def storage(directory):
    return _factory.get()(Path(directory))


@contextmanager
def use_storage(factory):
    token = _factory.set(factory)
    try:
        yield factory
    finally:
        _factory.reset(token)
