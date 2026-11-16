"""Required report sections (scope #10, VER-04)."""

from functools import cache
from pathlib import Path

import yaml


@cache
def required_sections() -> tuple[str, ...]:
    data = yaml.safe_load((Path(__file__).with_name("sections.yaml")).read_text(encoding="utf-8"))
    return tuple(str(s) for s in data["sections"])
