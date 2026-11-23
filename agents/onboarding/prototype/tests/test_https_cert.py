"""The course endpoint is HTTPS signed by the course's own certificate authority (.crt file).
This test builds a private CA and an HTTPS stand-in model, then checks that:
  - with CREDASSURE_LLM_CA_CERT pointing at the CA, the call succeeds;
  - without it, the certificate is refused and the gate falls back to the template (never breaks).
Skipped if openssl is not installed."""
import json
import shutil
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from readiness.gate import run_readiness_gate
from readiness import generate_hr_data as gen

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed")
GOOD = ("You can't start this proposal yet because there is no record of your "
        "Financial Data Handling and Privacy training. Please complete it and run the check again.")


def _make_certs(d):
    run = lambda *a: subprocess.run(a, cwd=d, check=True, capture_output=True)
    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=Test Course CA",
        "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign",
        "-keyout", "ca.key", "-out", "ca.crt")
    run("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=127.0.0.1", "-keyout", "srv.key", "-out", "srv.csr")
    (d / "ext.cnf").write_text("subjectAltName=IP:127.0.0.1\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n")
    run("openssl", "x509", "-req", "-in", "srv.csr", "-CA", "ca.crt", "-CAkey", "ca.key", "-CAcreateserial",
        "-days", "2", "-extfile", "ext.cnf", "-out", "srv.crt")
    return d / "ca.crt", d / "srv.crt", d / "srv.key"


@pytest.fixture()
def https_model(hr_env, monkeypatch):
    ca, crt, key = _make_certs(hr_env)

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            out = json.dumps({"choices": [{"message": {"content": "<think>\n</think>\n" + GOOD}}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("CREDASSURE_LLM_BASE_URL", f"https://127.0.0.1:{srv.server_address[1]}/v1")
    monkeypatch.setenv("CREDASSURE_LLM_MODEL", "Qwen/Qwen3-8B")
    monkeypatch.setenv("CREDASSURE_LLM_API_KEY", "test-key")
    monkeypatch.setenv("CREDASSURE_LLM_TIMEOUT", "5")
    yield ca
    srv.shutdown()


def test_with_course_certificate_the_call_succeeds(https_model, monkeypatch):
    monkeypatch.setenv("CREDASSURE_LLM_CA_CERT", str(https_model))
    r = run_readiness_gate("CASE-T", "EMP-007", as_of=gen.AS_OF)
    assert r.explanation_source == "llm", r.warnings
    assert r.explanation == GOOD


def test_without_certificate_falls_back_safely(https_model, monkeypatch):
    monkeypatch.delenv("CREDASSURE_LLM_CA_CERT", raising=False)
    r = run_readiness_gate("CASE-T", "EMP-007", as_of=gen.AS_OF)
    assert r.explanation_source == "template" and r.decision.value == "NO_GO"
