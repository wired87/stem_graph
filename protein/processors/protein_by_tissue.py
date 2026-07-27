import asyncio
import httpx
import urllib.parse


async def get_tissue_label_from_ols4(
    client: httpx.AsyncClient, uberon_id: str
) -> str | None:
    """Helper: Fetches the clean English name of an UBERON ID from OLS4."""
    formatted_id = uberon_id.replace(":", "_")
    iri = f"http://purl.obolibrary.org/obo/{formatted_id}"
    double_encode = urllib.parse.quote(
        urllib.parse.quote(iri, safe=""), safe=""
    )

    url = f"https://www.ebi.ac.uk/ols4/api/ontologies/uberon/terms/{double_encode}"
    try:
        response = await client.get(url, timeout=5.0)
        if response.status_code == 200:
            return response.json().get("label")
    except Exception:
        pass
    return None


async def get_proteins_by_uberon_anatomy(
    uberon_id: str, limit: int = 50
) -> dict:
    """Fetches expressed proteins/genes by resolving the UBERON ID to its

    English name and querying MyGene.info's HPA data layers safely.
    """
    url = "https://mygene.info/v3/query"
    protein_list = []

    async with httpx.AsyncClient() as client:
        try:
            # 1. Resolve ID to English name first to avoid Elasticsearch colon bugs
            tissue_name = await get_tissue_label_from_ols4(client, uberon_id)

            if not tissue_name:
                return {
                    "input_uberon_id": uberon_id,
                    "error": "Could not resolve UBERON ID to a tissue label via OLS4.",
                    "proteins": [],
                }

            # 2. Query HPA structures using the clean string literal
            # No colons or backslashes used here
            query_str = f'hpa.tissue_expression.tissue:"{tissue_name}" OR hpa.rna_expression.tissue:"{tissue_name}"'

            params = {
                "q": query_str,
                "species": "9606",  # Human
                "fields": "symbol,name,uniprot",
                "size": limit,
            }

            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            hits = data.get("hits", [])

            # 3. Parse out the protein metadata matrix
            for hit in hits:
                uniprot_data = hit.get("uniprot", {})
                uniprot_id = (
                    uniprot_data.get("Swiss-Prot")
                    if isinstance(uniprot_data, dict)
                    else None
                )

                if isinstance(uniprot_id, list) and uniprot_id:
                    uniprot_id = uniprot_id[0]

                protein_list.append(
                    {
                        "gene_symbol": hit.get("symbol"),
                        "protein_name": hit.get("name"),
                        "uniprot_id": uniprot_id,
                        "relevance_score": hit.get("_score"),
                    }
                )

            return {
                "input_uberon_id": uberon_id,
                "resolved_tissue_name": tissue_name,
                "total_proteins_found": len(protein_list),
                "proteins": protein_list,
            }

        except Exception as e:
            return {"input_uberon_id": uberon_id, "error": str(e), "proteins": []}


# --- Execution Sandbox ---
if __name__ == "__main__":
    import json

    async def main():
        # UBERON:0002021 = Occipital Lobe
        target_anatomy = "UBERON:0002021"

        print(
            f"Querying safe text-mapped protein discovery pipeline for: {target_anatomy}..."
        )
        result = await get_proteins_by_uberon_anatomy(target_anatomy, limit=10)

        print(json.dumps(result, indent=4))

    asyncio.run(main())