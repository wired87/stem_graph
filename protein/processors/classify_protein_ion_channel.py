def classify_protein_ion_channel(g):
    print("classify_protein_ion_channel...")
    proteins = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
    ]

    for pid in proteins:
        neighbor_gos = g.get_neighbor_list(
            node=pid, target_type="GO_TERM", just_ids=True
        )

        is_ion_channel = any(
            gid in {
                "GO:0005216",
                "GO:0005244",
                "GO:0022839",
            }
            for gid in neighbor_gos
        )
        # update entry
        g.G.nodes[pid]["is_ion_channel"] = is_ion_channel

    count = [nid for nid, attrs in g.G.nodes(data=True) if attrs.get("is_ion_channel", False) is True and attrs.get("type") == "PROTEIN"]
    print("ion channels extracted:", len(count))
    print("classify_protein_ion_channel... done")