"""Hosted deployment (deployment plan §5, docs/deployment/azure.md): static checks of the
production stack, since the VM itself is not reachable from CI.

Only Caddy publishes ports (80/443); the gateway loads the hosted model profile before the
server's .env; secrets are never written into the compose file; the API is routed under /v1 only.
"""

import re
import stat
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy/compose/production.yaml"
CADDY = ROOT / "deploy/caddy/Caddyfile"


def services() -> dict[str, dict[str, object]]:
    doc = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    out: dict[str, dict[str, object]] = doc["services"]
    return out


def test_deploy_only_caddy_publishes_ports() -> None:
    svc = services()
    published = {name for name, s in svc.items() if s.get("ports")}
    assert published == {"caddy"}
    assert svc["caddy"]["ports"] == ["80:80", "443:443"]


def test_deploy_gateway_profile_then_server_env_and_no_inline_secrets() -> None:
    gw = services()["gateway"]
    assert gw["env_file"] == ["../env/models-hosted.env", "../../.env"]  # later file wins
    env = gw["environment"]
    assert isinstance(env, dict)
    assert not [k for k in env if re.search(r"KEY|SECRET|PASSWORD|TOKEN", k)]
    assert gw["build"] == {
        "context": "../..",
        "dockerfile": "deploy/docker/Dockerfile.gateway",
        "args": {"HOSTED": "true"},
    }


def test_deploy_every_service_restarts_and_caps_logs() -> None:
    for name, s in services().items():
        assert s.get("restart") == "unless-stopped", name
        logging = s.get("logging")
        assert isinstance(logging, dict) and logging["options"]["max-size"], name


def test_deploy_caddy_routes_api_under_v1_only_and_streams() -> None:
    text = CADDY.read_text(encoding="utf-8")
    assert re.search(r"handle /v1/\* \{\s*#[^\n]*\n\s*reverse_proxy gateway:8000", text)
    assert "flush_interval -1" in text  # SSE progress and copilot streams
    assert "reverse_proxy web:8080" in text
    assert "/docs" not in text.replace("/docs page", "")  # API docs are not routed


def test_deploy_scripts_are_executable() -> None:
    for name in ("server-setup.sh", "prod.sh", "smoke.sh", "nightly-backup.sh"):
        mode = (ROOT / "deploy/scripts" / name).stat().st_mode
        assert mode & stat.S_IXUSR, name
