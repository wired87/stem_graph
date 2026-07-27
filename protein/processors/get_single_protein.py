import asyncio

import aiohttp

from protein.processors.request_handler import  UNIPROT_LIMITER
from tissue.regions import get_major_brain_uberon_regions

_TISSUE_NAME_BY_NODE_ID = {
    uid.replace(":", "_"): name for uid, name in get_major_brain_uberon_regions().items()
}
async def fetch_uniprot_protein(
        keywords: list[str] or str = None,
        organs:list[str] or str = None,
):
    """
    Asynchronously queries UniProt for a single keyword under human (9606) restriction.
    """
    print("keyword", keywords)
    print("organs" , organs)

    #
    tasks = []
    if organs:
        if not isinstance(organs, list):
            organs = [organs]

        for o in organs:
            query = (
                f'(organism_id:9606) '
            )
            if keywords is not None:
                if not isinstance(keywords, list):
                    keywords = [keywords]
                keyword_query = " OR ".join(
                    f'keyword:"{kw.strip()}"'
                    for kw in keywords
                )
                query += f" AND ({keyword_query})"

                organ_query = f'tissue:{o}'
                query += f' AND ({organ_query})'
                tasks.append(_UNIPROT_FETCHER.search(query))

        #
        batched_results = []
        result = await asyncio.gather(*tasks)

        for item in result:
            batched_results.extend(item["results"])
        return batched_results

async def up_by_id(
    session: aiohttp.ClientSession,
    uniprot_id: str,
) -> dict:
    """
    Fetch a single UniProt protein by accession.
    """

    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"

    async with UNIPROT_LIMITER:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()

        except Exception as e:
            print(f"Error fetching UniProt entry {uniprot_id}: {e}")
            return {}
