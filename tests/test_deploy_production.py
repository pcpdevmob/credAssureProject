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


def test_deploy_gateway_image_copies_every_workspace_member_it_installs() -> None:
    """The image runs `uv sync --all-packages`: a member whose folder is not copied fails the
    build ("Distribution not found"). The agents were missing until 21 Nov 2026."""
    import tomllib

    members = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["uv"][
        "workspace"
    ]["members"]
    docker = (ROOT / "deploy/docker/Dockerfile.gateway").read_text(encoding="utf-8")
    copied = re.findall(r"^COPY (?!--from)(\S+) \S+$", docker, re.M)
    assert "--all-packages" in docker
    for member in members:
        for needed in (f"{member}/pyproject.toml", f"{member}/src"):
            assert any(needed == c or needed.startswith(c + "/") for c in copied), needed
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "!evaluation/src/" in ignore and "!data/generators/" in ignore  # not ignored away


def test_deploy_web_image_installs_from_the_lockfile_ci_uses() -> None:
    docker = (ROOT / "deploy/docker/Dockerfile.web").read_text(encoding="utf-8")
    assert "package-lock.json" in docker and "npm ci" in docker
    assert "pnpm" not in docker.replace("the pnpm lockfile is not kept current", "")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "npm ci" in ci  # same installer, so a green CI build means the image builds


def test_deploy_compose_gateways_mount_the_data_the_image_leaves_out() -> None:
    dev = yaml.safe_load((ROOT / "deploy/compose/compose.yaml").read_text(encoding="utf-8"))
    assert "../../data:/app/data:ro" in dev["x-gateway"]["volumes"]
    assert "../../data:/app/data:ro" in list(services()["gateway"]["volumes"])  # type: ignore[call-overload]
