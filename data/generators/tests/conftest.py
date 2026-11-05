"""Shared corpus test helpers as fixtures (no network; importlib mode cannot import conftest)."""

from collections.abc import Callable
from typing import Any

import pytest


def _text_pdf(text: str) -> bytes:
    """A minimal PDF with a real text layer and a valid xref table."""
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>stream\n" % len(stream) + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def _entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "doc_id": "R-X-001",
        "tag": "x",
        "collection": "public",
        "jurisdiction": "IN",
        "legal_basis": "L4",
        "format": "html",
        "title": "t",
        "publisher": "p",
        "effective_from": "2025-01-01",
        "superseded_by": None,
        "source_url": "https://ex.org/doc",
        "source": 4,
        "applies_to": "all",
        "method": "script",
    }
    return base | overrides


@pytest.fixture
def text_pdf() -> Callable[[str], bytes]:
    return _text_pdf


@pytest.fixture
def entry() -> Callable[..., dict[str, Any]]:
    return _entry
