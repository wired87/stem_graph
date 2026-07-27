
def get_edge_sign(
    edge_attrs: dict,
) -> float:

    if edge_attrs.get(
        "consensus_stimulation"
    ):
        return 1.0

    if edge_attrs.get(
        "consensus_inhibition"
    ):
        return -1.0

    return 0.0

def propagate_network_drug_effect_rules(
    g,
):
    print(
        "propagate_drug_effects..."
    )

    molecules: list[tuple] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    for mol in molecules:
        neighbors = g.get_neighbor_list_rel(
            node=mol[0],
            trgt_rel="target_of",
            just_ids=True,
        )

        #
        for trgt_id in neighbors:
            proteins = g.get_neighbor_list_rel(
                node=trgt_id,
                trgt_rel="target_component_of",
                just_ids=True,
            )

            #




    #
    for drug_id, protein_id, edge_attrs in g.G.edges(
        data=True
    ):

        #
        effect = edge_attrs.get(
            "effect"
        )

        if effect is None:
            continue

        #
        if g.G.nodes.get(
            drug_id,
            {},
        ).get("type") != "MOLECULE":
            continue

        #
        if g.G.nodes.get(
            protein_id,
            {},
        ).get("type") != "PROTEIN":
            continue

        #
        for nbr in g.G.neighbors(
            protein_id
        ):

            if nbr == drug_id:
                continue

            #
            nbr_attrs = g.G.nodes[
                nbr
            ]

            if nbr_attrs.get(
                "type"
            ) != "PROTEIN":
                continue

            #
            edge_data = g.get_edge(
                protein_id,
                nbr,
            )

            if not edge_data:
                continue

            #
            sign = get_edge_sign(
                edge_data
            )

            #
            string_score = float(
                edge_data.get(
                    "string_score",
                    1.0,
                )
            )

            #
            propagated_effect = (
                effect
                *
                sign
                *
                string_score
            )

            #
            edge_data[
                "propagated_effect"
            ] = propagated_effect

            edge_data[
                "propagation_source"
            ] = protein_id

            edge_data[
                "source_drug"
            ] = drug_id

            #
            edge_data[
                "calculation"
            ] = (
                f"{effect}"
                f"*{sign}"
                f"*{string_score}"
            )

    print(
        "propagate_drug_effects... done"
    )


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for propagate_network_drug_effect_rules.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from firegraph.graph.local_graph_utils import GUtils

    # CHAR: drug→protein effect + PPI stimulation/inhibition branches.
    g = GUtils()
    g.add_node(attrs=dict(id="CHEMBL25", type="MOLECULE"))
    g.add_node(attrs=dict(id="P35498", type="PROTEIN", name="SCN1A"))
    g.add_node(attrs=dict(id="P08172", type="PROTEIN", name="CHRM2"))
    g.add_edge(
        "CHEMBL25",
        "P35498",
        attrs=dict(rel="target_of", src_layer="MOLECULE", trgt_layer="PROTEIN", effect=-2.5),
    )
    g.add_edge(
        "P35498",
        "P08172",
        attrs=dict(
            rel="interacts_with",
            src_layer="PROTEIN",
            trgt_layer="PROTEIN",
            consensus_stimulation=True,
            string_score=0.82,
        ),
    )
    assert get_edge_sign(dict(consensus_stimulation=True)) == 1.0
    assert get_edge_sign(dict(consensus_inhibition=True)) == -1.0
    propagate_network_drug_effect_rules(g)
    ppi_edge = g.get_edge("P35498", "P08172")
    assert "propagated_effect" in ppi_edge, "PPI edge should carry propagated_effect"
    print(f"[__main__] propagate_network_drug_effect_rules OK  propagated={ppi_edge.get('propagated_effect')}")