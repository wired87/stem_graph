import httpx


BASE_URL = (
    "https://www.guidetopharmacology.org/services"
)

async def get_ligand_target_interactions(
    ligand_id: int,
    target_ids: list[int],
) -> list[dict]:
    """
    Returns one dict per target_id.

    Output index matches input target_ids.

    [
        {
            "target_id": 290,
            "interaction": {...}
        },
        {
            "target_id": 524,
            "interaction": None
        }
    ]
    """

    try:

        url = (
            f"{BASE_URL}"
            f"/ligands/{ligand_id}/interactions"
        )

        async with httpx.AsyncClient(
            timeout=30,
        ) as client:

            response = await client.get(
                url,
            )

            response.raise_for_status()

            payload = response.json()

        #
        interaction_by_target = {}

        for row in payload:

            #
            target_id = (
                row.get("targetId")
                or row.get("target_id")
            )

            if target_id is None:
                continue

            interaction_by_target[
                int(target_id)
            ] = dict(

                #
                target_id=int(
                    target_id
                ),

                #
                target_name=row.get(
                    "target"
                ),

                #
                action=row.get(
                    "action"
                ),

                #
                endogenous=row.get(
                    "endogenous"
                ),

                #
                species=row.get(
                    "species"
                ),

                #
                affinity=row.get(
                    "affinity"
                ),

                #
                affinity_units=row.get(
                    "affinityUnits"
                ),

                #
                type=row.get(
                    "type"
                ),

                #
                selectivity=row.get(
                    "selectivity"
                ),

                #
                interaction_parameter=row.get(
                    "parameter"
                ),

                #
                pKi=row.get(
                    "pKi"
                ),

                #
                pIC50=row.get(
                    "pIC50"
                ),

                #
                pEC50=row.get(
                    "pEC50"
                ),

                #
                pKd=row.get(
                    "pKd"
                ),

                #
                comments=row.get(
                    "comments"
                ),

                #
                source="GuideToPharmacology",
            )

        #
        results = []

        for target_id in target_ids:

            results.append(

                interaction_by_target.get(
                    int(target_id),
                    {
                        "target_id": target_id,
                        "interaction": None,
                    },
                )

            )

        return results

    except Exception as e:

        print(
            f"GtoP interaction error: {e}"
        )

        return [
            {
                "target_id": tid,
                "interaction": None,
                "error": str(e),
            }
            for tid in target_ids
        ]