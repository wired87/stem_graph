import asyncio
import httpx

BASE_URL = (
    "https://www.guidetopharmacology.org/services"
)

async def uniprot_to_pharmacology_target_ids(
    uniprot_accessions: list[str],
) -> dict[str, list[int]]:

    async with httpx.AsyncClient(
        timeout=30,
    ) as client:

        async def process(
            accession: str,
        ):
            try:
                #
                url = (
                    f"{BASE_URL}"
                    f"/targets"
                )
                #
                response = await client.get(
                    url,
                    params={
                        "database": "UniProt",
                        "databaseId": accession,
                    },
                )

                response.raise_for_status()

                payload = response.json()

                #
                target_ids = [
                    int(
                        row["targetId"]
                    )
                    for row in payload
                    if row.get(
                        "targetId"
                    )
                ]

                return (
                    accession,
                    target_ids,
                )

            except Exception as e:

                print(
                    accession,
                    e,
                )

                return (
                    accession,
                    [],
                )

        results = await asyncio.gather(
            *[
                process(
                    accession,
                )
                for accession in uniprot_accessions
            ]
        )

    return dict(
        results
    )