"""
tissue.tissue_descendants -- OLS4 / Uberon descendant lookup.

User prompt (Cursor session):
    "use a unified class for all web request core infrastructure.
     (schema as gotermfetcher but adaptable to all types of data)
     keep specific processors rely in the current corresponding files."

The OLS4 HTTP core is expressed via ``OlsTissueFetcher`` (subclass of
``app_utils.AsyncApiFetcher``); the dictionary-shaped post-processor
``get_uberon_subclasses`` stays in this file.
"""

import urllib.parse

import httpx

from core.app_utils import AsyncApiFetcher


# Unified OLS4 fetcher -- one endpoint, but plumbing matches every other source
class OlsTissueFetcher(AsyncApiFetcher):
    BASE_URL = "https://www.ebi.ac.uk/ols4/api/ontologies/uberon/terms"

    async def hierarchical_descendants(self, uberon_id: str, *, size: int = 500, page: int = 0):
        """Fetch one page of hierarchical descendants for ``uberon_id`` (e.g. UBERON:0000970)."""
        # Format ID and double URL-encode the standard OBO IRI
        formatted_id = uberon_id.replace(":", "_")
        iri = f"http://purl.obolibrary.org/obo/{formatted_id}"
        first_encode = urllib.parse.quote(iri, safe="")
        double_encode = urllib.parse.quote(first_encode, safe="")
        # Target the hierarchical descendants endpoint
        url = f"{self.BASE_URL}/{double_encode}/hierarchicalDescendants"
        # Fetch 500 records per page to optimize network roundtrips
        params = {"size": size, "page": page}
        return await self._execute_get(url, params=params, timeout=15.0)


# module-level singleton
_OLS_FETCHER = OlsTissueFetcher()


async def get_uberon_subclasses(uberon_id: str) -> dict[str, str]:
    """Asynchronously fetches all subclasses (descendants) for a specific UBERON ID.

    Returns:
        A dictionary mapping subclass UBERON IDs to their English labels/names.
    """
    print("get_uberon_subclasses...")
    subclasses: dict[str, str] = {}

    try:
        # delegate the HTTP work to the unified fetcher
        data = await _OLS_FETCHER.hierarchical_descendants(uberon_id)

        # Extract terms on the current page
        terms = data.get("_embedded", {}).get("terms", [])
        for term in terms:
            if term.get("is_obsolete"):
                continue

            sub_id = term.get("obo_id") or term.get("short_form")
            name = term.get("label")

            if sub_id and name:
                subclasses[sub_id] = name

    except httpx.HTTPStatusError as e:
        # OLS4 returns 404 for unknown / leaf terms -- treat as "no descendants"
        if e.response.status_code == 404:
            return {}
        print(f"Error occurred: {e}")
    except Exception as e:
        print(f"Error occurred: {e}")
    return subclasses


# --- Example Usage ---
if __name__ == "__main__":
    import asyncio
    import json

    async def main():
        # Example: Get all subclasses of "Eye" (UBERON:0000970)
        target_id = "UBERON:0000970"

        print(f"Fetching all subclasses for {target_id}...")
        results = await get_uberon_subclasses(target_id)

        print(f"\nFound {len(results)} subclasses.")
        # Print the first 10 results as a sample
        sample = {k: results[k] for k in list(results)[:10]}
        print("Sample entries:")
        print(json.dumps(sample, indent=4))

    asyncio.run(main())

