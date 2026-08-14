"""Reproducible id generation. Python's uuid.uuid4() reads os.urandom and
cannot be seeded -- everything that needs a stable id under `make data
SEED=42` draws its bytes from the run's numpy Generator instead.
"""

from __future__ import annotations

import uuid

import numpy as np


def new_uuid(rng: np.random.Generator) -> str:
    """A RFC 4122 v4-shaped uuid string, deterministic given `rng`'s state."""
    raw = bytearray(rng.integers(0, 256, size=16, dtype=np.uint8).tobytes())
    raw[6] = (raw[6] & 0x0F) | 0x40  # version 4
    raw[8] = (raw[8] & 0x3F) | 0x80  # variant RFC 4122
    return str(uuid.UUID(bytes=bytes(raw)))
