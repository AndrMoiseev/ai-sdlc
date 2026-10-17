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


def dom(directory, tmp_path, width=1280, screenshot=False):
    command = [chrome(), "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--user-data-dir=" + str(tmp_path / "chrome-profile"), "--virtual-time-budget=6500", "--dump-dom", (directory / "dashboard.html").as_uri()]
    command[1:1] = [f"--window-size={width},1800"]
    if screenshot:
        command[1:1] = ["--screenshot=" + str(tmp_path / "browser.png")]
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


@pytest.mark.parametrize("width", [1280, 540])
def test_wave_layout_links_and_live_updates(monkeypatch, tmp_path, width):
    from test_waves import wave_state
    from lib.state import new_task
    from lib import dashboard
    state = wave_state()
    state["tasks"]["I"] = new_task(dict(id="I", number=9, depends_on=["A"], covers=["AC-demo"]))
    monkeypatch.setattr(dashboard, "read", lambda directory: state)
    directory = tmp_path / "view"
    directory.mkdir()
    render(directory)


    html_path = directory / "dashboard.html"
    saved = html_path.read_text(encoding="utf-8")
    state["revision"] = 1
    for key, status in {"A": "accepted", "B": "accepted", "C": "accepted", "D": "reviewing", "E": "running", "F": "accepted", "G": "running"}.items():
        state["tasks"][key]["status"] = status
    render(directory)
    probe = """<script>
    document.querySelector('#task-D details').open=true;
    document.querySelector('[data-wave="wave-4"] a').click();
    setTimeout(()=>{
      const checks={};
      const waves=[...document.querySelectorAll('.wave')];
      checks.vertical=waves.every((w,i)=>!i||w.getBoundingClientRect().top>=waves[i-1].getBoundingClientRect().bottom);
      const cards=[...document.querySelector('[data-wave="wave-2"] .wave-tasks').children];
      checks.wrap=cards[3].getBoundingClientRect().top>cards[0].getBoundingClientRect().top;
      checks.order=cards.map(c=>c.dataset.task).join(',')==='C,D,E,I';
      checks.unique=cards.every(c=>c.querySelectorAll('h3').length===1);
      checks.width=document.documentElement.scrollWidth<=innerWidth;
      checks.viewport=innerWidth<=__WIDTH__;
      checks.link=location.hash==='#task-C'&&document.querySelector('article.selected')?.id==='task-C';
      checks.details=document.querySelector('#task-D details').open;
      checks.live=document.getElementById('meta').textContent.includes('revision 1');
      checks.overlap=waves[0].dataset.status==='completed'&&waves[1].dataset.status==='in_progress'&&waves[2].dataset.status==='in_progress'&&waves[3].dataset.status==='ready';
      checks.accepted=document.querySelector('[data-wave="wave-4"] a').dataset.accepted==='true';
      const result=document.createElement('pre');result.id='wave-checks';
      result.dataset.result=Object.values(checks).every(Boolean)?'pass':'fail';
      result.textContent=JSON.stringify(checks);document.body.append(result);
      document.querySelector('#task-D details').open=false;
      window.scrollTo(0,0);
    },4500);
    </script>"""
    html_path.write_text(saved.replace("</body>", probe.replace("__WIDTH__", str(width)) + "</body>"), encoding="utf-8")
    result = dom(directory, tmp_path, width, screenshot=True)
    assert 'id="wave-checks" data-result="pass"' in result, result[-6000:]
    assert (tmp_path / "browser.png").is_file()
    # Retain a clean standalone example alongside the instrumented browser evidence.
    render(directory)


@pytest.mark.parametrize("storage_disabled", [False, "read", "write"])
def test_evidence_survives_reload_and_updates(monkeypatch, tmp_path, storage_disabled):
    from test_waves import wave_state
    from lib import dashboard
    state = wave_state()
    monkeypatch.setattr(dashboard, "read", lambda directory: state)
    directory = tmp_path / "view"
    directory.mkdir()
    render(directory)
    page = directory / "dashboard.html"
    original = page.read_text(encoding="utf-8")
    if storage_disabled == "read":
        original = original.replace('<script>', '<script>Object.defineProperty(window,"localStorage",{get(){throw new Error("Storage denied");}});</script><script>', 1)
    if storage_disabled == "write":
        original = original.replace('<script>', '<script>Object.defineProperty(window,"localStorage",{value:{getItem(){return null;},setItem(){throw new Error("Quota exceeded");}}});</script><script>', 1)
    # The hash carries test phase only; product UI preferences must survive reload themselves.
    probe = """<script>
    const disabled=__DISABLED__;
    function visible(){const c=document.getElementById('task-C');return !!c.querySelector('details[open], section.evidence');}
    function finish(ok){const p=document.createElement('p');p.id='persistence-result';p.dataset.result=ok?'pass':'fail';document.body.append(p);}
    if(location.hash==='#reloaded'){
      const restored=visible();
      if(disabled){finish(restored);}
      else {
        document.querySelector('#task-C summary').click();
        setTimeout(()=>{location.hash='closed';location.reload();},100);
        sessionStorage.setItem('demo-restored',String(restored));
      }
    }else if(location.hash==='#closed'){
      const closed=!visible();
      const summary=document.querySelector('#task-C summary');
      summary.click();
      const update=__UPDATE__;
      window.sddApplyUpdate(update);
      const stable=summary===document.querySelector('#task-C summary');
      const openAfterUpdate=visible();
      summary.click();
      finish(sessionStorage.getItem('demo-restored')==='true'&&closed&&stable&&openAfterUpdate&&!visible());
    }else{
      const summary=document.querySelector('#task-C summary');if(summary)summary.click();
      setTimeout(()=>{location.hash='reloaded';location.reload();},100);
    }
    </script>"""
    update = projection(state)
    update["revision"] = 1
    update["tasks"][2]["evidence"] = [{"stage": "independent", "outcome": "pass", "log": "runs/demo/result.json"}]
    probe = probe.replace("__DISABLED__", str(bool(storage_disabled)).lower()).replace("__UPDATE__", json.dumps(update))
    page.write_text(original.replace('</body>', probe + '</body>'), encoding="utf-8")
    result = dom(directory, tmp_path)
    assert 'id="persistence-result" data-result="pass"' in result, result[-2000:]


def test_evidence_preferences_are_scoped_to_run(monkeypatch, tmp_path):
    from test_waves import wave_state
    from lib import dashboard
    state = wave_state()
    monkeypatch.setattr(dashboard, "read", lambda directory: state)
    directory = tmp_path / "view"
    directory.mkdir()
    page = directory / "dashboard.html"
    render(directory)
    html = page.read_text(encoding="utf-8")
    page.write_text(html.replace('</body>', '<script>document.querySelector("#task-C summary").click();</script></body>'), encoding="utf-8")
    assert '<details class="evidence" open="">' in dom(directory, tmp_path)
    state["run_id"] = "another-run"
    render(directory)
    html = page.read_text(encoding="utf-8")
    page.write_text(html.replace('</body>', '<script>document.body.dataset.leaked=String(document.querySelector("#task-C details").open);</script></body>'), encoding="utf-8")
    assert '<body data-leaked="false">' in dom(directory, tmp_path)
