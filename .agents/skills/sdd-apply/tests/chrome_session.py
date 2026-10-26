"""One real Chrome process, sequential pages and isolated per-test storage."""
import base64
from collections import deque
import json
import subprocess
import time

from websocket import create_connection, WebSocketException


class ChromeSession:
    def __init__(self, executable, directory):
        self.directory = directory
        self.command = [executable, "--headless", "--disable-gpu", "--no-first-run",
                        "--no-default-browser-check", "--disable-background-networking",
                        "--remote-debugging-port=0", "--remote-allow-origins=http://localhost",
                        "--user-data-dir=" + str(directory / "profile"), "about:blank"]
        self.stderr = (directory / "chrome-stderr.txt").open("wb")
        self.process = subprocess.Popen(self.command, stdout=subprocess.DEVNULL, stderr=self.stderr)
        self.socket = None
        try:
            deadline = time.monotonic() + 20
            port_file = directory / "profile/DevToolsActivePort"
            while not port_file.is_file():
                if self.process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Chrome did not expose its local debugging port")
                time.sleep(0.01)
            port, endpoint = port_file.read_text().splitlines()[:2]
            self.socket = create_connection(f"ws://127.0.0.1:{port}{endpoint}",
                                            origin="http://localhost", timeout=20)
            self.number, self.events = 0, deque()
        except BaseException:
            self.close()
            raise

    def call(self, method, params=None, session=None):
        self.number += 1
        request = dict(id=self.number, method=method, params=params or {})
        if session:
            request["sessionId"] = session
        self.socket.send(json.dumps(request))
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            response = json.loads(self.socket.recv())
            if response.get("id") == self.number:
                assert "error" not in response, response
                return response.get("result", {})
            self.events.append(response)
        raise TimeoutError(method)

    def wait(self, method, session):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            event = self.events.popleft() if self.events else json.loads(self.socket.recv())
            if event.get("method") == method and event.get("sessionId") == session:
                return event.get("params", {})
        raise TimeoutError(method)

    def dom(self, context, directory, evidence, width, screenshot, virtual_time=2500):
        target = self.call("Target.createTarget", {"url": "about:blank", "browserContextId": context})["targetId"]
        session = self.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        try:
            self.call("Page.enable", session=session)
            self.call("Emulation.setDeviceMetricsOverride", dict(width=width, height=1800,
                      deviceScaleFactor=1, mobile=False), session)
            self.events.clear()
            self.call("Page.navigate", {"url": (directory / "dashboard.html").as_uri()}, session)
            self.wait("Page.loadEventFired", session)
            if virtual_time:
                self.call("Emulation.setVirtualTimePolicy", dict(policy="pauseIfNetworkFetchesPending",
                          budget=virtual_time, maxVirtualTimeTaskStarvationCount=10000), session)
                self.wait("Emulation.virtualTimeBudgetExpired", session)
            result = self.call("Runtime.evaluate", dict(expression="document.documentElement.outerHTML",
                               returnByValue=True), session)
            assert "exceptionDetails" not in result, result
            html = result["result"]["value"]
            if screenshot:
                data = self.call("Page.captureScreenshot", {"format": "png"}, session)
                (evidence / "browser.png").write_bytes(base64.b64decode(data["data"]))
            (evidence / "browser-command.json").write_text(json.dumps(self.command))
            (evidence / "browser-dom.html").write_text(html, encoding="utf-8")
            return html
        finally:
            self.call("Target.closeTarget", {"targetId": target})

    def close(self):
        if self.socket:
            try:
                self.call("Browser.close")
                self.process.wait(timeout=5)
            except (OSError, WebSocketException, subprocess.TimeoutExpired):
                pass
            self.socket.close()
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)
        self.stderr.close()
