import json
from pathlib import Path
import threading
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import pytest
from lib.dashboard import render
from lib.server import make_server


def test_safe_generated_data_and_recovery(driver):
    before = (driver.directory / "state.json").read_bytes()
    result = render(driver.directory)
    assert result["revision"] == 0
    driver.send("block", {"reason": '</script><script>window.pwned=1</script>"', "resume_condition": "fix"})
    render(driver.directory)
    js = (driver.directory / "dashboard-state.js").read_text()
    assert "</script>" not in js
    assert "\\u003c" in js
    state = (driver.directory / "state.json").read_bytes()
    (driver.directory / "dashboard-state.js").write_text("broken")
    render(driver.directory)
    assert (driver.directory / "state.json").read_bytes() == state
    assert "TASK-one" in (driver.directory / "summary.md").read_text()


def test_loopback_allowlist_and_owned_shutdown(driver):
    render(driver.directory)
    server, meta = make_server(driver.directory)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        with urlopen(meta["url"]) as response:
            assert b"TASK-one" in response.read()
        for path in ("/state.json", "/../state.json", "/runs/"):
            with pytest.raises(HTTPError):
                urlopen(meta["url"] + path)
        with pytest.raises(HTTPError):
            urlopen(Request(meta["url"] + "/stop", method="POST"))
        with urlopen(Request(meta["url"] + "/stop", method="POST", headers={"X-SDD-Token": meta["token"]})) as response:
            assert response.status == 204
        thread.join(5)
        assert not thread.is_alive()
    finally:
        if thread.is_alive():
            server.shutdown()
        server.server_close()
