import asyncio

from drug_master.drug import ChemblFetcher

_CHEMBL_FETCHER = ChemblFetcher()


async def drug_activity_on_target(
        g
):
    """
    does drud influences local trgt?
    todo: if drug trgt not in local trgt: outsrc drug (just if too many drugs)
    """
    #
    molecule_ids: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]
    trgt_ids: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
    ]

    #
    # batch fetch activities
    #
    activity_tasks = [
        _CHEMBL_FETCHER.activities_for_molecule(
            molecule_id
        )
        for molecule_id in molecule_ids
    ]

    activity_results = await asyncio.gather(
        *activity_tasks,
        return_exceptions=True,
    )

    for molecule_id, result in zip(
            molecule_ids,
            activity_results,
    ):

        if not isinstance(result, dict):
            continue

        activities = result.get(
            "activities",
            []
        )

        for activity in activities:
            """
            IC50 = 1 nM      → extrem stark
            IC50 = 10 nM     → sehr stark
            IC50 = 100 nM    → stark
            IC50 = 1000 nM   → mittel
            IC50 = 100000 nM → praktisch keine Wirkung
            """
            accession = (
                activity.get(
                    "target_components"
                )
                or {}
            )

            if isinstance(
                    accession,
                    list,
            ):

                accessions = {
                    x.get("accession")
                    for x in accession
                    if x.get(
                        "accession"
                    )
                }

                if not any(item in accessions for item in trgt_ids):
                    continue

                for ac in accessions:
                    # create trgt PROTEIN node if not exists
                    if not g.get_node(ac):
                        g.add_node(
                            dict(
                                id=ac,
                                type="PROTEIN"
                            )
                        )

                    # MOL -> PROT
                    g.add_edge(
                        src=molecule_id,
                        trgt=ac,
                        attrs=dict(
                            rel="drug_combination_trgt",
                            src_layer="MOLECULE",
                            trgt_layer="PROTEIN",
                            standard_type=activity.get("standard_type"),
                            standard_value=activity.get("standard_value"),
                            standard_units=activity.get("standard_units"),
                        )
                    )






