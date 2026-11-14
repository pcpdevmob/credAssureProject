import hashlib
import math
import re
from collections.abc import Callable

import pytest


def hash_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words embedder: shared words → similar vectors. No network."""
    out = []
    for text in texts:
        vec = [0.0] * 64
        for word in re.findall(r"\w+", text.lower()):
            vec[int(hashlib.sha256(word.encode()).hexdigest(), 16) % 64] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


@pytest.fixture
def embed() -> Callable[[list[str]], list[list[float]]]:
    return hash_embed
