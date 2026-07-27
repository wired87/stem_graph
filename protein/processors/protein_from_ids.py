import asyncio
from typing import List, Any

import aiohttp

from firegraph.graph.local_graph_utils import GUtils
from protein.processors.get_single_protein import up_by_id


async def get_proteins_from_ids(
    g:GUtils,
) -> List[Any]:
    """
    Receives a list of keywords and a list of target organs, runs queries concurrently,
    and returns a filtered list of matching human protein payloads.
    """
    proteins = [key for key, attrs in g.G.nodes(data=True) if attrs.get("type") == "PROTEIN"]

    async with aiohttp.ClientSession() as session:
        # Schedule concurrent API requests
        tasks = [up_by_id(session, p) for p in proteins]
        batched_results = await asyncio.gather(*tasks)

        # Track unique accessions to avoid duplicate entries across different keyword results
        seen_accessions = set()

        for protein in batched_results:
            accession = protein.get("primaryAccession")

            if accession and accession not in seen_accessions:
                seen_accessions.add(accession)
                g.add_node(
                    attrs=dict(
                        id=accession,
                        type="PROTEIN",
                        **protein,
                        embed_key="proteinDescription__recommendedName__fullName__value"
                    )
                )
    print("protein query finished...")
