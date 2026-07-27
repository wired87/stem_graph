import re

import numpy as np
import requests

from embedder import embed_batch
from tissue.tissue import fetch_uniprot_tissue_vocabulary

UNIPROT_TISSUE_URL = (
    "https://ftp.uniprot.org/pub/databases/uniprot/"
    "current_release/knowledgebase/complete/docs/tisslist.txt"
)


def get_uniprot_tissues() -> list[str]:
    """
    Download UniProt tissue vocabulary and return
    all tissue names.

    Returns
    -------
    list[str]
        Example:
        [
            "Brain",
            "Liver",
            "Thalamus",
            ...
        ]
    """

    response = requests.get(
        UNIPROT_TISSUE_URL,
        timeout=60,
    )
    response.raise_for_status()

    tissues = []

    for line in response.text.splitlines():

        line = line.strip()

        # Tissue entries start with:
        # ID   Brain
        if line.startswith("ID"):
            match = re.match(
                r"^ID\s+(.+?)\s*$",
                line,
            )

            if match:
                tissues.append(
                    match.group(1).strip()
                )

    return sorted(set(tissues))


async def uberon_to_uniprot_tissue(g):
    print("uberon_to_uniprot_tissue...")

    up_tissues = await fetch_uniprot_tissue_vocabulary()
    print("up tissues fetched...")

    uberon_tissues = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "TISSUE"
           and attrs.get("sub_type") == "UBERON"
    ]

    print(f"Found {len(uberon_tissues)} UB tissues", uberon_tissues)

    # embeddings
    uberon_vecs = embed_batch([a[a["embed_key"]] for _, a in uberon_tissues])
    print("ub vecs created...")

    uniprot_vecs = embed_batch(up_tissues)
    print("up vecs created...")

    # normalize
    uberon_vecs = uberon_vecs / np.linalg.norm(
        uberon_vecs,
        axis=1,
        keepdims=True,
    )

    uniprot_vecs = uniprot_vecs / np.linalg.norm(
        uniprot_vecs,
        axis=1,
        keepdims=True,
    )

    similarity_matrix = uberon_vecs @ uniprot_vecs.T
    final_ids = []

    for idx, uberon_id in enumerate(uberon_tissues):
        best_idx = np.argmax(similarity_matrix[idx])
        score = similarity_matrix[idx, best_idx]
        if score < 0.95:
            final_ids.append(None)
            continue
        final_ids.append(up_tissues[best_idx])
        print(f"mapped UBERON {uberon_id} to {up_tissues[best_idx]}")

    for uberon_id, item in zip(uberon_tissues, final_ids):
        if item is None:
            continue

        #
        item = item.strip().rstrip(".")
        g.add_node(
            dict(
                id=item,
                type="TISSUE",
                sub_type="UNIPROT",
                description="",
            )
        )

        #
        g.add_edge(
            src=uberon_id[0],
            trgt=item,
            attrs=dict(
                rel="uniprot_compound",
                src_layer="TISSUE",
                trgt_layer="TISSUE",
            )
        )

    count = [nid for nid, attrs in g.G.nodes(data=True) if attrs.get("type") == "TISSUE" and attrs.get("sub_type") == "UNIPROT"]
    print("uniprot tissues extracted:", len(count), count, "\n... done")


if __name__ == "__main__":
    tissues = get_uniprot_tissues()

    print(f"Found {len(tissues)} tissues")
