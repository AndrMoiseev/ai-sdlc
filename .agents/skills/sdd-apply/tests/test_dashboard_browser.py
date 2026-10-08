"""Real Chrome fallback when no Browser plugin surface is connected."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from lib.dashboard import render, projection


def chrome():
    choices = [shutil.which("google-chrome"), shutil.which("chromium"), "C:/Program Files/Google/Chrome/Application/chrome.exe"]
    found = next((p for p in choices if p and Path(p).is_file()), None)
    if not found:
        pytest.skip("Real Chrome/Chromium unavailable; browser AC remains unverified")
    return found


def dom(directory, tmp_path):
    command = [chrome(), "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--user-data-dir=" + str(tmp_path / "chrome-profile"), "--virtual-time-budget=6500", "--dump-dom", (directory / "dashboard.html").as_uri()]
    result = subprocess.run(command, capture_output=True, timeout=40)
    (tmp_path / "browser-command.json").write_text(json.dumps(command))
    (tmp_path / "browser-stderr.txt").write_bytes(result.stderr)
    (tmp_path / "browser-dom.html").write_bytes(result.stdout)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return result.stdout.decode("utf-8", "replace")


def test_file_timer_updates_without_reload(driver, tmp_path):
    render(driver.directory)
    html = (driver.directory / "dashboard.html").read_bytes()
    driver.send("block", {"reason": "browser-live-update", "resume_condition": "fix"})
    render(driver.directory)
    (driver.directory / "dashboard.html").write_bytes(html)
    result = dom(driver.directory, tmp_path)
    assert "Live view" in result and "revision 1</p>" in result
    assert "browser-live-update</p>" in result


def test_snapshot_and_stale_foreign_data(driver, tmp_path):
    driver.send("block", {"reason": "saved-state", "resume_condition": "fix"})
    render(driver.directory)
    foreign = projection(driver.state)
    foreign.update(run_id="foreign", revision=999, status="forged")
    (driver.directory / "dashboard-state.js").write_text("window.sddApplyUpdate(" + json.dumps(foreign) + ");")
    result = dom(driver.directory, tmp_path)
    assert "revision 1</p>" in result and "revision 999</p>" not in result
    (driver.directory / "dashboard-state.js").unlink()
    result = dom(driver.directory, tmp_path)
    assert "live data unavailable" in result
