"""Export openapi.json at the repo root (ADR 0004). Run with `make openapi`."""

from __future__ import annotations

import json
from pathlib import Path

from credassure.gateway.main import create_app
from credassure.gateway.settings import Settings


def main(path: Path = Path("openapi.json")) -> None:
    schema = create_app(Settings(_env_file=None, app_env="test")).openapi()
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
