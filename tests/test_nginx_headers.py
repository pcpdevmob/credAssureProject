"""Scope #52: every nginx response carries the security headers, signed-in pages included.

nginx inherits add_header from an outer block only when the inner block sets none of its own. So
any server or location block with a direct add_header must include the shared snippet again, or it
silently drops CSP/HSTS.
"""

from pathlib import Path

NGINX = Path(__file__).resolve().parents[1] / "deploy/nginx"
SNIPPET = "credassure-security-headers.conf"
REQUIRED = (
    "Content-Security-Policy",
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
    "X-Robots-Tag",
    "Permissions-Policy",
    "Cross-Origin-Opener-Policy",
)
CONFS = ("finbridge.conf", "web-container.conf")
DOCKERFILE = NGINX.parents[0] / "docker" / "Dockerfile.web"


def blocks(conf: str) -> list[tuple[str, list[str]]]:
    """(block header, its direct statements) per block; quote-aware, so CSP's ';' stays inside."""
    stack: list[tuple[str, list[str]]] = [("main", [])]
    out = [stack[0]]
    buf, quote, comment = "", "", False
    for ch in conf:
        if comment:
            comment = ch != "\n"
        elif quote:
            buf += ch
            quote = "" if ch == quote else quote
        elif ch in "\"'":
            buf, quote = buf + ch, ch
        elif ch == "#":
            comment = True
        elif ch == "{":
            block: tuple[str, list[str]] = (" ".join(buf.split()), [])
            stack.append(block)
            out.append(block)
            buf = ""
        elif ch == ";":
            stack[-1][1].append(" ".join(buf.split()))
            buf = ""
        elif ch == "}":
            stack.pop()
            buf = ""
        else:
            buf += ch
    return out


def test_scope52_every_block_with_own_add_header_reincludes_the_snippet() -> None:
    for conf in CONFS:
        parsed = blocks((NGINX / conf).read_text())
        own = [(head, st) for head, st in parsed if any(s.startswith("add_header") for s in st)]
        assert own, f"parser found no add_header blocks in {conf}"
        for head, st in own:
            assert any(s.startswith("include") and s.endswith(SNIPPET) for s in st), (conf, head)


def test_P8_web_container_serves_the_snippet() -> None:
    """The compose `web` image replaces nginx's default.conf with ours and installs the snippet,
    so the container is not the one path that serves the SPA without CSP."""
    servers = [
        st for head, st in blocks((NGINX / "web-container.conf").read_text()) if head == "server"
    ]
    assert len(servers) == 1
    assert any(s.endswith(SNIPPET) for s in servers[0] if s.startswith("include"))
    docker = DOCKERFILE.read_text()
    assert f"deploy/nginx/security-headers.conf /etc/nginx/snippets/{SNIPPET}" in docker
    assert "deploy/nginx/web-container.conf /etc/nginx/conf.d/default.conf" in docker


def test_scope52_tls_server_includes_the_snippet() -> None:
    servers = [
        st for head, st in blocks((NGINX / "finbridge.conf").read_text()) if head == "server"
    ]
    tls = [st for st in servers if any(s.startswith("listen 443") for s in st)]
    assert tls and all(
        any(s.endswith(SNIPPET) for s in st if s.startswith("include")) for st in tls
    )


def test_scope52_snippet_sets_every_required_header_always() -> None:
    lines = [s for _, st in blocks((NGINX / "security-headers.conf").read_text()) for s in st]
    for name in REQUIRED:
        assert any(s.startswith(f"add_header {name} ") and s.endswith(" always") for s in lines), (
            name
        )
