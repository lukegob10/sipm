import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest


script = Path(__file__).resolve().parents[3] / "skills/sipm-agent/scripts/sipm_agent.py"
spec = importlib.util.spec_from_file_location("sipm_agent_redirect_test", script)
assert spec and spec.loader
sipm_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sipm_agent)


def test_redirect_origin_normalizes_default_ports_and_distinguishes_schemes():
    assert sipm_agent._origin("HTTP://EXAMPLE.COM:80/path") == sipm_agent._origin("http://example.com/path")
    assert sipm_agent._origin("https://example.com/path") != sipm_agent._origin("http://example.com/path")
    assert sipm_agent._origin("http://example.com:0/path") != sipm_agent._origin("http://example.com/path")
    assert sipm_agent._origin("https://example.com:invalid/path") is None


@pytest.mark.parametrize("cross_origin", [False, True], ids=["same-origin", "cross-origin"])
def test_agent_client_does_not_forward_token_to_another_origin(cross_origin):
    received = []

    class Destination(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.headers.get("Authorization"))
            body = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    destination = ThreadingHTTPServer(("127.0.0.1", 0), Destination)

    class Origin(Destination):
        def do_GET(self):
            if self.path == "/api/redirect":
                self.send_response(302)
                if cross_origin:
                    self.send_header("Location", f"http://127.0.0.1:{destination.server_port}/collect")
                else:
                    self.send_header("Location", "/api/destination")
                self.end_headers()
            else:
                super().do_GET()

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    threads = [Thread(target=server.serve_forever, daemon=True) for server in (origin, destination)]
    for thread in threads:
        thread.start()
    try:
        client = sipm_agent.SipmClient(f"http://127.0.0.1:{origin.server_port}", "test-token")
        if cross_origin:
            with pytest.raises(SystemExit, match="redirect"):
                client.request("GET", "/redirect")
            assert received == []
        else:
            assert client.request("GET", "/redirect") == {"ok": True}
            assert received == ["Bearer test-token"]
    finally:
        for server in (origin, destination):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join()
