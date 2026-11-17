"""Fail on a breaking change in openapi.json against a git ref (scope #28, ADR 0004).

Usage: python scripts/openapi_diff.py [base_ref] [head_file]   (defaults: main, openapi.json)

Breaking: a removed path or operation, a removed success (no 2xx left) or response
property, a changed property type, a new required parameter or request property, or a request
body that became required.
Additions are not breaking. Stdlib only; $ref is resolved within each spec.
"""

# ruff: noqa: S603, S607
import json
import subprocess  # nosec B404 - fixed git command, no shell
import sys
from pathlib import Path
from typing import Any

METHODS = ("get", "post", "put", "patch", "delete")
JSON = "application/json"


def _resolve(spec: dict[str, Any], node: Any) -> Any:
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 20:
        target: Any = spec
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        node, seen = target, seen + 1
    return node


def _type(spec: dict[str, Any], s: Any) -> Any:
    s = _resolve(spec, s)
    if not isinstance(s, dict):
        return None
    if "anyOf" in s:  # Optional[X] etc.: compare the set of member types
        return sorted(str(_type(spec, m)) for m in s["anyOf"])
    return s.get("type")


def _enum(spec: dict[str, Any], s: Any) -> set[str]:
    s = _resolve(spec, s)
    return {str(v) for v in s.get("enum", [])} if isinstance(s, dict) else set()


def _props(spec: dict[str, Any], s: Any) -> tuple[dict[str, Any], set[str]]:
    s = _resolve(spec, s) or {}
    return s.get("properties", {}), set(s.get("required", []))


def _body(spec: dict[str, Any], container: Any) -> Any:
    return ((_resolve(spec, container) or {}).get("content", {}).get(JSON) or {}).get("schema")


def diff(base: dict[str, Any], head: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for path, item in base.get("paths", {}).items():
        new_item = head.get("paths", {}).get(path)
        if new_item is None:
            out.append(f"removed path {path}")
            continue
        for m in METHODS:
            if m not in item:
                continue
            where = f"{m.upper()} {path}"
            if m not in new_item:
                out.append(f"removed operation {where}")
                continue
            old, new = item[m], new_item[m]
            # parameters: a new required one, or one that became required
            old_p = {
                (p["name"], p["in"]): p
                for p in map(lambda p: _resolve(base, p), old.get("parameters", []))
            }
            for p in (_resolve(head, p) for p in new.get("parameters", [])):
                prev = old_p.get((p["name"], p["in"]))
                if p.get("required") and not (prev and prev.get("required")):
                    out.append(f"{where}: new required parameter {p['name']}")
            # request body
            ob, nb = old.get("requestBody"), new.get("requestBody")
            if (
                nb
                and _resolve(head, nb).get("required")
                and not (ob and _resolve(base, ob).get("required"))
            ):
                out.append(f"{where}: request body became required")
            if ob and nb:
                (op, oreq), (np_, nreq) = (
                    _props(base, _body(base, ob)),
                    _props(head, _body(head, nb)),
                )
                for name in sorted(nreq - oreq):
                    out.append(f"{where}: new required request property {name}")
                for name in sorted(set(op) & set(np_)):
                    if _type(base, op[name]) != _type(head, np_[name]):
                        out.append(f"{where}: request property {name} changed type")
                    gone = _enum(base, op[name]) - _enum(head, np_[name])
                    if gone:  # a value clients may send is no longer accepted
                        out.append(f"{where}: request property {name} drops {sorted(gone)}")
            # responses
            for code, resp in old.get("responses", {}).items():
                if not code.startswith("2"):
                    continue
                ok2 = [c for c in new.get("responses", {}) if c.startswith("2")]
                if code not in ok2 and not ok2:
                    out.append(f"{where}: removed response {code}")
                    continue
                # 200 -> 202 stays a success; the body it now returns must still be compatible
                now = new["responses"][code if code in ok2 else ok2[0]]
                os_, ns = _body(base, resp), _body(head, now)
                if os_ is None or ns is None:
                    continue
                if _type(base, os_) not in (None, _type(head, ns)):  # untyped {} accepts anything
                    out.append(f"{where} {code}: response type changed")
                (op, _), (np_, _) = _props(base, os_), _props(head, ns)
                for name in sorted(op):
                    if name not in np_:
                        out.append(f"{where} {code}: removed response property {name}")
                    elif _type(base, op[name]) != _type(head, np_[name]):
                        out.append(f"{where} {code}: response property {name} changed type")
    return out


def main(argv: list[str]) -> int:
    ref = argv[1] if len(argv) > 1 else "main"
    head_file = Path(argv[2] if len(argv) > 2 else "openapi.json")
    raw = subprocess.run(  # nosec B603 B607 - fixed argv
        ["git", "show", f"{ref}:openapi.json"], capture_output=True, text=True, check=True
    ).stdout
    findings = diff(json.loads(raw), json.loads(head_file.read_text()))
    for f in findings:
        print(f"BREAKING: {f}")
    print(f"openapi-diff vs {ref}: {len(findings)} breaking change(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
