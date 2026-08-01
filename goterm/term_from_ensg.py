import asyncio

import httpx


async def fetch_go_terms_for_gene(
        session: httpx.AsyncClient,
        ensg_id: str,
        semaphore: asyncio.Semaphore
) -> list[str]:
    """Fetch all GO term IDs for a single ENSG gene ID."""
    url = f"https://rest.ensembl.org/xrefs/id/{ensg_id}?external_db=GO;content-type=application/json"

    async with semaphore:
        try:
            response = await session.get(url)
            if response.status_code != 200:
                return []

            data = response.json()
            # Extract GO IDs (e.g., "GO:0006281")
            go_terms = [item["primary_id"] for item in data if "primary_id" in item]
            # Return deduplicated list preserving order
            return list(dict.fromkeys(go_terms))

        except Exception as e:
            print(f"Error fetching GO terms for {ensg_id}: {e}")
            return []


async def get_go_terms_batch(ensg_ids: list[str], max_concurrent: int = 10) -> list[list[str]]:
    """
    Async gathers all GO term IDs for a list of ENSG IDs.
    Returns: list[list[str]] where output[i] corresponds to ensg_ids[i].
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    # Configure timeout and connection limits
    async with httpx.AsyncClient(timeout=30) as session:
        tasks = [
            fetch_go_terms_for_gene(session, ensg_id, semaphore)
            for ensg_id in ensg_ids
        ]
        # asyncio.gather maintains exact order of input tasks
        return await asyncio.gather(*tasks)


# --- Example Usage ---
if __name__ == "__main__":
    gene_ids = ["ENSG00000139618", "ENSG00000141510", "INVALID_ID"]

    # Run the async pipeline
    results = asyncio.run(get_go_terms_batch(gene_ids))

    for ensg_id, go_terms in zip(gene_ids, results):
        print(f"{ensg_id} ({len(go_terms)} GO terms): {go_terms[:5]}...")
