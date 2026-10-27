"""Chrome startup contracts without a browser, socket or wall-clock waits."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import chrome_session


READY = "43123\n/devtools/browser/session-id\n"


@pytest.fixture
def startup(monkeypatch):
    port_file = MagicMock()
    port_file.is_file.return_value = True
    port_file.read_text.return_value = READY
    stderr = BytesIO()
    stderr_file = MagicMock()
    stderr_file.open.return_value = stderr
    directory = MagicMock()
    directory.__truediv__.side_effect = {
        "profile": "profile", "profile/DevToolsActivePort": port_file,
        "chrome-stderr.txt": stderr_file,
    }.__getitem__
    process = MagicMock()
    process.poll.return_value = None
    popen = MagicMock(return_value=process)
    connect = MagicMock()
    clock = SimpleNamespace(now=100.0)

    def sleep(seconds):
        assert 0 < seconds <= 0.1
        clock.now += seconds
        assert clock.now <= 121, "Startup exceeded its original 20-second deadline"

    monkeypatch.setattr(chrome_session, "subprocess", SimpleNamespace(
        Popen=popen, DEVNULL=chrome_session.subprocess.DEVNULL,
        TimeoutExpired=chrome_session.subprocess.TimeoutExpired))
    monkeypatch.setattr(chrome_session, "create_connection", connect)
    monkeypatch.setattr(chrome_session, "time", SimpleNamespace(
        monotonic=lambda: clock.now, sleep=sleep))
    return SimpleNamespace(directory=directory, port_file=port_file, stderr=stderr,
                           process=process, connect=connect, clock=clock)


@pytest.mark.parametrize("pending", [PermissionError("Chrome is writing"),
                                     FileNotFoundError("Not published yet"),
                                     "", "43123\n", "43123\n\n"])
def test_startup_retries_until_both_port_lines_are_readable(startup, pending):
    startup.port_file.read_text.side_effect = [pending, pending, READY]

    session = chrome_session.ChromeSession("chrome", startup.directory)

    startup.connect.assert_called_once_with(
        "ws://127.0.0.1:43123/devtools/browser/session-id",
        origin="http://localhost", timeout=20)
    assert session.socket is startup.connect.return_value
    assert startup.clock.now > 100
    assert not startup.stderr.closed
    startup.process.terminate.assert_not_called()


def test_startup_waits_for_absent_port_file(startup):
    startup.port_file.is_file.side_effect = [False, False, True]
    startup.port_file.read_text.side_effect = [FileNotFoundError(), READY]

    chrome_session.ChromeSession("chrome", startup.directory)

    startup.connect.assert_called_once()
    assert startup.clock.now > 100


@pytest.mark.parametrize("pending", [PermissionError("Still locked"),
                                     FileNotFoundError("Still absent"), "43123\n"])
def test_startup_retries_share_original_deadline_and_clean_up(startup, pending):
    if isinstance(pending, Exception):
        startup.port_file.read_text.side_effect = pending
    else:
        startup.port_file.read_text.return_value = pending

    with pytest.raises(RuntimeError, match="Chrome did not expose its local debugging port"):
        chrome_session.ChromeSession("chrome", startup.directory)

    assert 120 <= startup.clock.now <= 120.02
    startup.connect.assert_not_called()
    startup.process.terminate.assert_called_once()
    startup.process.wait.assert_called_once_with(timeout=10)
    assert startup.stderr.closed


def test_startup_stops_when_chrome_exits_and_closes_stderr(startup):
    startup.port_file.is_file.return_value = False
    startup.port_file.read_text.side_effect = FileNotFoundError()
    startup.process.poll.return_value = 7

    with pytest.raises(RuntimeError, match="Chrome did not expose its local debugging port"):
        chrome_session.ChromeSession("chrome", startup.directory)

    assert startup.clock.now == 100
    startup.connect.assert_not_called()
    startup.process.terminate.assert_not_called()
    assert startup.stderr.closed


def test_startup_does_not_hide_unrelated_read_errors(startup):
    failure = OSError("Unexpected device failure")
    startup.port_file.read_text.side_effect = failure

    with pytest.raises(OSError) as raised:
        chrome_session.ChromeSession("chrome", startup.directory)

    assert raised.value is failure
    assert startup.clock.now == 100
    startup.connect.assert_not_called()
    startup.process.terminate.assert_called_once()
    assert startup.stderr.closed


def test_startup_preserves_connection_error_and_cleans_up(startup):
    failure = chrome_session.WebSocketException("Connection refused")
    startup.connect.side_effect = failure

    with pytest.raises(chrome_session.WebSocketException) as raised:
        chrome_session.ChromeSession("chrome", startup.directory)

    assert raised.value is failure
    startup.process.terminate.assert_called_once()
    startup.process.wait.assert_called_once_with(timeout=10)
    assert startup.stderr.closed
