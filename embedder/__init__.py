import json
import os

import numpy as np
from functools import lru_cache

os.environ["SENTENCE_TRANSFORMERS_HOME"] = os.path.abspath("embed_models")

EMBEDDER = None
@lru_cache(maxsize=1)
def get_embedder(dim=3):
    from sentence_transformers import SentenceTransformer
    global EMBEDDER
    try:
        EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    except Exception as e:
        print("Err get embedder local", e, "download")
    if EMBEDDER is None:
        if dim == 7:
            model="all-mpnet-base-v2"
        else:
            model="all-MiniLM-L6-v2"
        model = SentenceTransformer(model)
    else:
        return EMBEDDER

EMBEDDER = get_embedder()

def embed(text):
    if EMBEDDER is not None:
        if isinstance(text, dict):
            text=json.dumps(text)
        return np.array(EMBEDDER.encode(str(text.lower())), dtype=np.float64)
    else:
        print("Embedder ot avaialble...")

import json
import numpy as np


def embed_batch(texts: list) -> np.ndarray:
    processed_texts = []
    for text in texts:
        if isinstance(text, dict):
            text = json.dumps(text)
        processed_texts.append(str(text).lower())

    embeddings = EMBEDDER.encode(processed_texts)

    result = np.array(embeddings, dtype=np.float64)
    print("result.shape", result.shape)
    return result

#@lru_cache(maxsize=1024)
def similarity(vec1_tuple, vec2_tuple):
    v1 = np.frombuffer(np.array(vec1_tuple, dtype=np.float32))
    v2 = np.frombuffer(np.array(vec2_tuple, dtype=np.float32))

    return float(np.dot(v1, v2))

