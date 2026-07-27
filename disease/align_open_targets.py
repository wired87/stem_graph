"""
Filter diseases by patient DISEASE_ANNOTATION cosine match.

Prompt: fix align_disease_patient — do not delete all diseases; match patient input only.
"""
import numpy as np


def align_disease_patient(g, n=0.74):
    """Keep DISEASE nodes that match at least one DISEASE_ANNOTATION embedding."""
    print("align_disease_patient...")

    patient_ann = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "DISEASE_ANNOTATION" and attrs.get("embedding") is not None
    ]
    if not patient_ann:
        print("align_disease_patient: no DISEASE_ANNOTATION — skip filter")
        return

    diseases = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "DISEASE" and attrs.get("embedding") is not None
    ]
    if not diseases:
        print("align_disease_patient: no embedded DISEASE nodes")
        return

    Q = np.array([attrs["embedding"] for _, attrs in patient_ann], dtype=np.float32)
    D = np.array([attrs["embedding"] for _, attrs in diseases], dtype=np.float32)
    Q_norm = Q / np.linalg.norm(Q, axis=1, keepdims=True)
    D_norm = D / np.linalg.norm(D, axis=1, keepdims=True)
    similarity_matrix = np.dot(Q_norm, D_norm.T)
    max_scores = np.max(similarity_matrix, axis=0)

    matched_ids: set[str] = set()
    for j, score in enumerate(max_scores):
        if score > n:
            nid, attrs = diseases[j]
            matched_ids.add(nid)
            g.update_node(attrs=dict(**attrs, dis_match_user=True, id=nid))

    for nid, _ in diseases:
        if nid not in matched_ids:
            print(f"align_disease_patient: remove non-match {nid}")
            g.delete_node(nid)

    print(f"align_disease_patient... done ({len(matched_ids)}/{len(diseases)} kept)")


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for align_disease_patient.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from embedder import embed_batch
    from firegraph.graph.local_graph_utils import GUtils

    # CHAR: matched pair — epilepsy annotation aligns to epilepsy disease embedding.
    g = GUtils()
    ann_vec = embed_batch(["epilepsy, seizure disorder"])[0].tolist()
    dis_match_vec = embed_batch(["epilepsy"])[0].tolist()
    dis_other_vec = embed_batch(["diabetes mellitus type 2"])[0].tolist()
    g.add_node(attrs=dict(id="ANN_EPILEPSY", type="DISEASE_ANNOTATION", embedding=ann_vec))
    g.add_node(attrs=dict(id="EFO_000125", type="DISEASE", name="epilepsy", embedding=dis_match_vec))
    g.add_node(attrs=dict(id="EFO_000136", type="DISEASE", name="diabetes", embedding=dis_other_vec))
    n_before = g.G.number_of_nodes()
    align_disease_patient(g, n=0.74)
    kept = [nid for nid, a in g.G.nodes(data=True) if a.get("type") == "DISEASE"]
    assert "EFO_000125" in kept, "matching disease should survive filter"
    assert "EFO_000136" not in kept, "non-matching disease should be removed"
    assert g.G.number_of_nodes() < n_before, "expected prune of non-matching disease"
    print(f"[__main__] align_disease_patient OK  kept={kept}")
