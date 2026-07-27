
from typing import List
from embedder import embed, similarity
from tissue.tissue import fetch_uniprot_tissue_vocabulary


async def organs_process(g, input_organs: List[str]) -> list[str]:
    """
    classify organs to
    """
    if not input_organs:
        return []

    print("Fetching master tissue vocabulary from UniProt...")
    fetch_uniprot_tissue_vocabulary(g)

    matched_uniprot_organs = set()

    for target in input_organs:
        target_vector = embed(target)
        print(f"Evaluating matches for input target: '{target}'...")
        for key, v in [(key, v) for key, v in g.G.nodes(dat=True) if v["type"] == "ORGAN"]:
            score = similarity(target_vector, v["embedding"])
            if score < 0.85:
                # score not enough -> rm node from G
                g.delete_node(key)

    print(f"\nDiscovered {len(list(matched_uniprot_organs))} matches exceeding threshold:")
    print(list(matched_uniprot_organs))

    for organ in list(matched_uniprot_organs):
        g.add_node(
            attrs=dict(
                id=organ,
                type="ORGAN",
                embedding=embed(organ),
            )
        )







