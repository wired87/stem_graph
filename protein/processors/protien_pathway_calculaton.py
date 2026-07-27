from collections import deque


def propagate_drug_scores(
    g,
    threshold: float = 0.1,
):
    """
    Drug
      -> Targets(score)
      -> Proteins
      -> Protein neighbors
    """

    drugs: list[tuple] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    for drug_id, _drug_attrs in drugs:

        targets = g.get_neighbor_list_rel(
            node=drug_id,
            trgt_rel="target_of",
            just_ids=True,
        )

        for target_id in targets:

            target_node = g.get_node(target_id)

            start_score = target_node.get(
                "score",
                0.0,
            )

            proteins = g.get_neighbor_list_rel(
                node=target_id,
                trgt_rel="protein_of",
                just_ids=True,
            )

            for protein_id in proteins:

                walk_scores(
                    g=g,
                    start_node=protein_id,
                    start_score=start_score,
                    threshold=threshold,
                )



def walk_scores(
    g,
    start_node: str,
    start_score: float,
    threshold: float,
):
    queue = deque()

    queue.append(
        (
            start_node,
            start_score,
            0,
        )
    )

    visited = {}

    while queue:

        (
            center,
            center_score,
            depth,
        ) = queue.popleft()

        #
        # Keep strongest score
        #
        old_score = visited.get(
            center,
            0.0,
        )

        if abs(old_score) >= abs(center_score):
            continue

        visited[center] = center_score

        #
        # Save node score
        #
        g.update_node(
            dict(
                id=center,
                propagated_score=center_score,
            )
        )

        #
        # STOP CONDITION
        #
        if abs(center_score) < threshold:
            continue

        neighbors = g.get_neighbor_list_rel(
            node=center,
            trgt_rel="interacts_with",
            just_ids=True,
        )

        for neighbor in neighbors:

            edge = g.get_edge(
                src=center,
                trgt=neighbor,
            )

            edge_attrs = edge.get(
                "attrs",
                edge,
            ) if isinstance(edge, dict) else {}

            multiplier = (
                get_edge_multiplier(
                    edge_attrs
                )
            )

            new_score = (
                center_score
                * multiplier
                * 0.7
            )

            #
            # Store propagated edge score
            #
            g.update_edge(
                src=center,
                trgt=neighbor,
                attrs=dict(
                    propagated_score=new_score
                )
            )

            queue.append(
                (
                    neighbor,
                    new_score,
                    depth + 1,
                )
            )


def get_edge_multiplier(
    edge_attrs: dict,
):
    #
    # Strong stimulation
    #
    if edge_attrs.get(
        "consensus_stimulation"
    ):
        return 1.0

    #
    # Strong inhibition
    #
    if edge_attrs.get(
        "consensus_inhibition"
    ):
        return -1.0

    #
    # Direction known
    #
    if edge_attrs.get(
        "consensus_direction"
    ):
        return 0.5

    #
    # Weak evidence
    #
    if edge_attrs.get(
        "omnipath_stimulation"
    ):
        return 0.75

    if edge_attrs.get(
        "omnipath_inhibition"
    ):
        return -0.75

    #
    # Unknown
    #
    return 0.0


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for propagate_drug_scores.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from firegraph.graph.local_graph_utils import GUtils

    # CHAR: drug→target(score)→protein→PPI chain for walk_scores / get_edge_multiplier.
    g = GUtils()
    g.add_node(attrs=dict(id="CHEMBL25", type="MOLECULE"))
    g.add_node(attrs=dict(id="CHEMBL240", type="TARGET", score=6.5))
    g.add_node(attrs=dict(id="P35498", type="PROTEIN", name="SCN1A"))
    g.add_node(attrs=dict(id="P08172", type="PROTEIN", name="CHRM2"))
    g.add_edge(
        "CHEMBL25",
        "CHEMBL240",
        attrs=dict(rel="target_of", src_layer="MOLECULE", trgt_layer="TARGET"),
    )
    g.add_edge(
        "CHEMBL240",
        "P35498",
        attrs=dict(rel="protein_of", src_layer="TARGET", trgt_layer="PROTEIN"),
    )
    g.add_edge(
        "P35498",
        "P08172",
        attrs=dict(
            rel="interacts_with",
            src_layer="PROTEIN",
            trgt_layer="PROTEIN",
            consensus_inhibition=True,
            string_score=0.75,
        ),
    )
    assert get_edge_multiplier(dict(consensus_stimulation=True)) == 1.0
    assert get_edge_multiplier(dict(consensus_inhibition=True)) == -1.0
    propagate_drug_scores(g, threshold=0.05)
    prot_scores = {
        nid: a.get("propagated_score")
        for nid, a in g.G.nodes(data=True)
        if a.get("type") == "PROTEIN" and a.get("propagated_score") is not None
    }
    assert prot_scores, "expected propagated_score on at least one PROTEIN node"
    print(f"[__main__] propagate_drug_scores OK  protein_scores={prot_scores}")