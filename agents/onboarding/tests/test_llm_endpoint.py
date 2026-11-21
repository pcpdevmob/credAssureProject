"""The real HTTP path to an OpenAI-compatible endpoint (as Ollama and the course endpoint expose),
tested against a small stand-in server, so no model is needed to run these tests."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from readiness import generate_hr_data as gen
from readiness.gate import run_readiness_gate

GOOD = ("You can't start this proposal yet because there is no record of your "
        "Financial Data Handling and Privacy training. Please complete it and run the check again.")
BAD = "You're qualified! Everything looks fine."            # contradicts a NO_GO


class FakeModel:
    """Serves scripted replies; an int is an HTTP error status."""
    def __init__(self, replies):
        self.replies, self.requests = list(replies), []
        model = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                model.requests.append((self.path, self.headers.get("Authorization"), body))
                reply = model.replies.pop(0) if model.replies else GOOD
                if isinstance(reply, int):
                    self.send_response(reply)
                    self.end_headers()
                    return
                out = json.dumps({"choices": [{"message": {"role": "assistant", "content": reply}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"


@pytest.fixture()
def model(hr_env, monkeypatch):
    servers = []

    def start(replies, model_name="qwen3:8b"):
        m = FakeModel(replies)
        servers.append(m)
        monkeypatch.setenv("CREDASSURE_LLM_BASE_URL", m.url)
        monkeypatch.setenv("CREDASSURE_LLM_MODEL", model_name)
        monkeypatch.setenv("CREDASSURE_LLM_API_KEY", "ollama")
        monkeypatch.setenv("CREDASSURE_LLM_TIMEOUT", "5")
        return m
    yield start
    for m in servers:
        m.server.shutdown()


def run():
    return run_readiness_gate("CASE-T", "EMP-007", as_of=gen.AS_OF)


def test_good_reply_is_used_and_request_is_openai_shaped(model):
    m = model([GOOD])
    r = run()
    assert r.explanation_source == "llm" and r.explanation == GOOD
    path, auth, body = m.requests[0]
    assert path == "/v1/chat/completions" and auth == "Bearer ollama"
    assert body["model"] == "qwen3:8b" and body["temperature"] == 0
    assert [msg["role"] for msg in body["messages"]] == ["system", "user"]


@pytest.mark.parametrize("status", [429, 503, 500])
def test_busy_endpoint_is_retried_with_backoff(model, status):
    m = model([status, GOOD])
    r = run()
    assert r.explanation_source == "llm" and len(m.requests) == 2


def test_at_most_two_retries_then_template(model):
    """NFR-04: three calls at most (one try plus two retries), then the template."""
    m = model([429, 429, 429, 429])
    r = run()
    assert r.explanation_source == "template" and len(m.requests) == 3
    assert any("unavailable" in w for w in r.warnings)


def test_auth_error_is_not_retried(model):
    m = model([401])
    assert run().explanation_source == "template" and len(m.requests) == 1


# ---------- Qwen3 specifics ----------
def test_qwen_gets_no_think_and_thinking_is_stripped(model):
    m = model(["<think>\nThe user wants a short rewrite.\n</think>\n\n" + GOOD])
    r = run()
    assert r.explanation_source == "llm" and r.explanation == GOOD
    assert m.requests[0][2]["messages"][1]["content"].endswith("/no_think")


def test_unfinished_thinking_falls_back_to_template(model):
    model(["<think>I am still reasoning about", "<think>still going"])
    assert run().explanation_source == "template"


def test_non_qwen_model_gets_no_suffix(model):
    m = model([GOOD], model_name="llama3.1:8b")
    run()
    assert not m.requests[0][2]["messages"][1]["content"].endswith("/no_think")


def test_extra_body_is_sent(model, monkeypatch):
    monkeypatch.setenv("CREDASSURE_LLM_EXTRA_BODY", '{"chat_template_kwargs": {"enable_thinking": false}}')
    m = model([GOOD])
    run()
    assert m.requests[0][2]["chat_template_kwargs"] == {"enable_thinking": False}


def test_missing_certificate_file_is_reported(model, monkeypatch, tmp_path):
    from readiness.explain import openai_compatible_llm
    model([])
    monkeypatch.setenv("CREDASSURE_LLM_CA_CERT", str(tmp_path / "nope.crt"))
    with pytest.raises(FileNotFoundError):
        openai_compatible_llm()


def test_missing_certificate_never_breaks_the_gate(model, monkeypatch, tmp_path):
    model([])
    monkeypatch.setenv("CREDASSURE_LLM_CA_CERT", str(tmp_path / "nope.crt"))
    r = run()
    assert r.decision.value == "NO_GO" and r.explanation_source == "template"


def test_bad_reply_twice_falls_back_to_template(model):
    m = model([BAD, BAD])
    r = run()
    assert r.explanation_source == "template" and len(m.requests) == 2
    assert any("rejected" in w and "2 attempt" in w for w in r.warnings)


def test_bad_reply_then_good_reply_is_accepted(model):
    model([BAD, GOOD])
    assert run().explanation_source == "llm"


def test_decision_never_comes_from_the_model(model):
    model([BAD, BAD])
    assert run().decision.value == "NO_GO"


def test_unreachable_endpoint_falls_back(monkeypatch, model):
    model([])
    monkeypatch.setenv("CREDASSURE_LLM_BASE_URL", "http://127.0.0.1:9/v1")   # nothing listens here
    r = run()
    assert r.explanation_source == "template" and r.decision.value == "NO_GO"
    assert any("unavailable" in w for w in r.warnings)
