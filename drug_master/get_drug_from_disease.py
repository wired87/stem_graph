from typing import Dict


def get_drug_from_disease(g):
    print("[*] Starting drug-from-disease classification workflow...")

    # Extracting both the ID and attributes to properly log the pipeline's progress
    mols: list[tuple[str, dict]] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    print(f"[*] Found {len(mols)} MOLECULE node(s) in the local graph to inspect.")
    updated_nodes_count = 0

    for molid, mol_attrs in mols:
        mol_name = mol_attrs.get("name", molid)

        # Fetching neighboring DISEASE nodes for the specific molecule
        neighbors: Dict[str, Dict] = g.get_neighbor_list(node=molid, target_type="DISEASE")

        for nid, attrs in neighbors.items():
            disease_name = attrs.get("name", nid)

            # Check conditions: Must match user query and must be classified as a drug mechanism
            if attrs.get("dis_match_user", False) is True and attrs.get("is_drug") is True:
                print(f"  -> Match found! Molecule '{mol_name}' matches criteria for Disease '{disease_name}' ({nid}).")

                # Update the node attributes in the Gutils-instance
                g.update_node(dict(id=nid, treatment=True, **attrs))

    print(
        f"[+] Workflow finished. Successfully flagged and updated DISEASE node(s) with 'treatment=True'.\n")