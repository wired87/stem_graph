"""
Persistent disease embedding cache — batch embed only missing rows.

Prompt: implement point 4 — check missing embed lines and batch embed them stepwise.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from embedder import embed_batch

# CHAR: local cache keyed by disease id + text hash + model id
_CACHE_PATH = Path("data/disease_embeddings.parquet")
_MODEL_ID = "all-MiniLM-L6-v2"
_EMBED_BATCH = 512


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_cache() -> dict[str, dict]:
    if not _CACHE_PATH.is_file() or not pq.ParquetFile(_CACHE_PATH).metadata.num_rows:
        return {}
    table = pq.read_table(_CACHE_PATH)
    rows = table.to_pylist()
    out: dict[str, dict] = {}
    for row in rows:
        if row.get("model") != _MODEL_ID:
            continue
        nid = row.get("id")
        if nid:
            out[str(nid)] = row
    return out


def _write_cache(cache: dict[str, dict]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = list(cache.values())
    if not rows:
        return
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, _CACHE_PATH, compression="snappy")
    print(f"disease_emb_cache: wrote {len(rows)} rows -> {_CACHE_PATH}")


def embed_diseases_with_cache(
    g,
    disease_ids: set[str] | None = None,
) -> int:
    """
    Apply embeddings to DISEASE nodes: load cache, embed missing texts in batches, persist.
    Returns count of diseases that received an embedding on this run.
    """
    cache = _load_cache()
    pending: list[tuple[str, str]] = []

    for nid, attrs in g.G.nodes(data=True):
        if attrs.get("type") != "DISEASE":
            continue
        if disease_ids is not None and nid not in disease_ids:
            continue
        text = str(attrs.get("text") or attrs.get("name") or nid)
        th = _text_hash(text)
        cached = cache.get(nid)
        if cached and cached.get("text_hash") == th and cached.get("embedding"):
            g.G.nodes[nid]["embedding"] = cached["embedding"]
            continue
        pending.append((nid, text))

    if not pending:
        print("disease_emb_cache: all disease embeddings present")
        return 0

    print(f"disease_emb_cache: embedding {len(pending)} missing (cached {len(cache)})")
    applied = 0
    for start in range(0, len(pending), _EMBED_BATCH):
        chunk = pending[start:start + _EMBED_BATCH]
        texts = [t for _, t in chunk]
        vectors = embed_batch(texts)
        for (nid, text), vec in zip(chunk, vectors):
            emb = vec.tolist() if hasattr(vec, "tolist") else list(vec)
            g.G.nodes[nid]["embedding"] = emb
            cache[nid] = {
                "id": nid,
                "text_hash": _text_hash(text),
                "model": _MODEL_ID,
                "embedding": emb,
            }
            applied += 1

    _write_cache(cache)
    print(f"disease_emb_cache: applied {applied} new embeddings")
    return applied
