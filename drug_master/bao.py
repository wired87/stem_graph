def insert_and_map_bao_metadata(g_utils, activity_entry: dict):
    """
    Parses BioAssay Ontology (BAO) fields from a ChEMBL activity dictionary,
    creates corresponding ontology nodes, and maps them to the unique activity instance.

    Args:
        g_utils: An instance of GUtils managing the graph operations (add_node, add_edge).
        activity_entry (dict): A dictionary representing a single ChEMBL activity record.
    """
    # 1. Extract the primary activity identifier to anchor the edges
    activity_id = activity_entry.get("activity_id")
    if not activity_id:
        print("[!] Missing activity_id. Skipping BAO extraction.")
        return

    # Formulate a unique identifier for the activity node instance
    activity_node_id = f"ACTIVITY_{activity_id}"

    # Ensure the parent Activity Node exists in the graph before attaching metadata
    g_utils.add_node(
        dict(
            id=activity_node_id,
            type="ACTIVITY_EVENT",
            sub_type="EXPERIMENTAL_MEASUREMENT",
            parent=activity_entry.get("target_chembl_id")  # Map to biological target context
        )
    )

    # 2. Extract BAO attributes safely from the JSON entry
    bao_endpoint = activity_entry.get("bao_endpoint")
    bao_format = activity_entry.get("bao_format")
    bao_label = activity_entry.get("bao_label")  # e.g., "assay format"

    # 3. Process the BAO Format Entry (e.g., BAO_0000019 / "assay format")
    if bao_format:
        # Create the specialized Ontology node
        g_utils.add_node(
            dict(
                id=bao_format,
                type="BIOLOGICAL_ONTOLOGY",
                sub_type="EXPERIMENT_METADATA",
                label=bao_label or "BAO Format Metric",
                parent="BAO_ROOT"  # Optional root categorizer
            )
        )

        # Draw the edge mapping the Activity Event to its BAO Format classification
        g_utils.add_edge(
            activity_node_id,
            bao_format,
            attrs=dict(
                rel="classified_by_format",
                src_layer="ACTIVITY_EVENT",
                trgt_layer="BIOLOGICAL_ONTOLOGY",
                description=f"Activity tested under format structural model: {bao_label}"
            )
        )
        print(f"[+] Mapped {activity_node_id} -> Format: {bao_format}")

    # 4. Process the BAO Endpoint Entry (e.g., BAO_0003036)
    if bao_endpoint:
        # Create the specialized Endpoint node
        g_utils.add_node(
            dict(
                id=bao_endpoint,
                type="BIOLOGICAL_ONTOLOGY",
                sub_type="ENDPOINT_METADATA",
                label="BAO Endpoint Metric",
                parent="BAO_ROOT"
            )
        )

        # Draw the edge mapping the Activity Event to its functional BAO Endpoint criteria
        g_utils.add_edge(
            activity_node_id,
            bao_endpoint,
            attrs=dict(
                rel="measured_via_endpoint",
                src_layer="ACTIVITY_EVENT",
                trgt_layer="BIOLOGICAL_ONTOLOGY",
                description="Activity evaluated against this specific bioassay endpoint definition"
            )
        )
        print(f"[+] Mapped {activity_node_id} -> Endpoint: {bao_endpoint}")