"""Compatibility embedder facade used by the local workflows.

The original project imports ``embedder`` as a top-level package.  Keep that
contract available and avoid network downloads during workflow startup.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache

import numpy as np


os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", os.path.abspath("embed_models"))


def _text(value) -> str:
    if isinstance(value, dict):
        value = json.dumps(value, sort_keys=True)
    return str(value or "").lower()


def _fallback_vector(value, dim: int = 384) -> np.ndarray:
    seed = hashlib.sha256(_text(value).encode("utf-8")).digest()
    values = []
    counter = 0
    while len(values) < dim:
        block = hashlib.sha256(seed + counter.to_bytes(4, "little")).digest()
        values.extend((byte / 255.0) - 0.5 for byte in block)
        counter += 1
    vector = np.asarray(values[:dim], dtype=np.float64)
    norm = np.linalg.norm(vector)
    return vector / norm if norm else vector


@lru_cache(maxsize=1)
def get_embedder():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    except Exception as exc:
        print("Embedder local model unavailable; using deterministic fallback:", exc)
        return None


EMBEDDER = get_embedder()


def embed(text):
    if EMBEDDER is None:
        return _fallback_vector(text)
    return np.asarray(EMBEDDER.encode(_text(text)), dtype=np.float64)


def embed_batch(texts: list) -> np.ndarray:
    if EMBEDDER is None:
        return np.asarray([_fallback_vector(text) for text in texts], dtype=np.float64)
    return np.asarray([EMBEDDER.encode(_text(text)) for text in texts], dtype=np.float64)


def similarity(vec1_tuple, vec2_tuple):
    v1 = np.asarray(vec1_tuple, dtype=np.float64)
    v2 = np.asarray(vec2_tuple, dtype=np.float64)
    denominator = np.linalg.norm(v1) * np.linalg.norm(v2)
    return float(np.dot(v1, v2) / denominator) if denominator else 0.0
