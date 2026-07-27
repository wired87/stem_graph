import asyncio

import httpx

BASE_URL = (
    "https://www.guidetopharmacology.org/services"
)

async def chembl_to_ligand_ids(
    chembl_ids: list[str],
) -> dict[str, list[int]]:

    async with httpx.AsyncClient(
        timeout=30,
    ) as client:

        async def process(
            chembl_id: str,
        ):
            try:

                #
                url = (
                    f"{BASE_URL}"
                    f"/ligands"
                )

                #
                response = await client.get(
                    url,
                    params={
                        "database":
                            "ChEMBL",
                        "databaseId":
                            chembl_id,
                    },
                )

                response.raise_for_status()

                payload = response.json()

                #
                ligand_ids = [
                    int(
                        row["ligandId"]
                    )
                    for row in payload
                    if row.get(
                        "ligandId"
                    )
                ]

                return (
                    chembl_id,
                    ligand_ids,
                )

            except Exception as e:

                print(
                    chembl_id,
                    e,
                )

                return (
                    chembl_id,
                    [],
                )

        results = await asyncio.gather(
            *[
                process(
                    chembl_id,
                )
                for chembl_id in chembl_ids
            ]
        )

    return dict(
        results
    )
