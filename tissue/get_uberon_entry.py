import httpx
import urllib.parse


async def get_single_uberon_entry_async(uberon_id: str) -> dict | None:
    """Asynchronously fetches a single UBERON term entry from the OLS4 API.

    Args:
        uberon_id: The ID of the tissue/anatomy term (e.g., "UBERON:0000955")

    Returns:
        A dictionary containing the term metadata, or None if not found.
    """
    # 1. Normalize the ID format (ensure colon is replaced by underscore for the IRI)
    formatted_id = uberon_id.replace(":", "_")

    # 2. Construct the full IRI required by OLS4
    iri = f"http://purl.obolibrary.org/obo/{formatted_id}"

    # 3. OLS4 requires the IRI to be double URL-encoded in the path
    first_encode = urllib.parse.quote(iri, safe="")
    double_encode = urllib.parse.quote(first_encode, safe="")

    url = f"https://www.ebi.ac.uk/ols4/api/ontologies/uberon/terms/{double_encode}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)

            if response.status_code == 404:
                print(f"Term {uberon_id} not found.")
                return None

            response.raise_for_status()
            data = response.json()

            # Extract key properties safely
            return {
                "id": uberon_id,
                "name": data.get("label"),
                "description": data.get("description", [None])[0],
                "synonyms": data.get("synonyms", []),
                "is_obsolete": data.get("is_obsolete", False),
                "iri": iri
            }

        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred while fetching {uberon_id}: {e}")
            return None
        except httpx.RequestError as e:
            print(f"Network error occurred while fetching {uberon_id}: {e}")
            return None


# --- Example Usage ---
if __name__ == "__main__":
    import asyncio


    async def main():
        # Fetch metadata for "Brain"
        tissue_id = "UBERON:0000955"

        print(f"Fetching data for {tissue_id}...")
        result = await get_single_uberon_entry_async(tissue_id)

        if result:
            import json
            print("\nSuccessfully retrieved entry:")
            print(json.dumps(result, indent=4))


    # Run the async loop
    asyncio.run(main())