
async def filter_drugs_by_mechanism(
    g,
    allowed_mechanisms: list[str],
):
    allowed = {m.upper() for m in allowed_mechanisms}

    drugs = g.nodes_by_type("DRUG")

    for drug in drugs:
        keep_drug = False

        mechanisms = g.get_neighbor_list(
            node=drug,
            target_type="MECHANISM",
        )

        for mechanism in mechanisms:

            action_type = (
                mechanism.get("action_type")
                or mechanism.get("schema", {}).get("action_type")
                or ""
            ).upper()

            if action_type in allowed:
                keep_drug = True
                break

        if not keep_drug:
            g.delete_node(drug["id"])