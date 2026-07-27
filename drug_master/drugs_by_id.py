import asyncio

from drug_master.drug import ChemblFetcher

_CHEMBL_FETCHER = ChemblFetcher()


async def drugs_by_id(g):
    """
    drug indication
    """
    #
    molecule_ids: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    target_ids: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
    ]

    target_set = set(target_ids)

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

        matched_targets = set()

        for activity in activities:

            accession = (
                activity.get(
                    "target_components"
                )
                or {}
            )

            #
            # depends on your fetcher response
            #
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

            else:
                accessions = set()

            overlap = (
                accessions
                & target_set
            )

            if not overlap:
                continue

            matched_targets.update(
                overlap
            )

        #
        for trgt in matched_targets:
            g.add_edge(
                src=molecule_id,
                trgt=trgt,
                attrs=dict(
                    rel="drug_combination_trgt",
                    src_layer="MOLECULE",
                    trgt_layer="PROTEIN",
                )
            )