import asyncio
import httpx


async def search_open_targets_ids(text_input: str) -> list[dict]:
    """
    Sendet einen natürlichsprachlichen Text an die Open Targets GraphQL API
    und extrahiert passende Krankheits- (EFO) und Target-IDs (Ensembl).

    :param text_input: Freitext der Suche (z. B. "chronic inflammation", "lung tumor")
    :return: Eine Liste von Dictionaries mit IDs, Namen und dem Entitätstyp.
    """
    if not text_input or not text_input.strip():
        return []

    url = "https://api.platform.opentargets.org/api/v4/graphql"

    # Die GraphQL-Query nutzt den internen Search-Index von Open Targets
    graphql_query = """
    query OpenTargetsSearch($queryString: String!) {
      search(queryString: $queryString) {
        hits {
          id
          entity
          name
          description
        }
      }
    }
    """

    # Payload für den POST-Request vorbereiten
    payload = {
        "query": graphql_query,
        "variables": {
            "queryString": text_input.strip()
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=15.0)

            if response.status_code != 200:
                print(f"[!] Open Targets API Fehler: Status {response.status_code}")
                return []

            data = response.json()

            # Extraktion der Hits aus der GraphQL-Struktur
            search_data = data.get("data", {}).get("search", {})
            if not search_data:
                return []

            hits = search_data.get("hits", [])

            results = []
            for hit in hits:
                results.append({
                    "id": hit.get("id"),  # Die gesuchte EFO- oder Ensembl-ID
                    "type": hit.get("entity"),  # 'disease' oder 'target'
                    "name": hit.get("name"),  # Offizieller Name in der Ontologie
                    "description": hit.get("description")
                })

            return results

        except Exception as e:
            print(f"[!] Fehler bei der Open Targets Suche: {e}")
            return []


# --- TEST-RUN FÜR DEIN SYSTEM ---
if __name__ == "__main__":
    suchbegriff = "lung cancer"


    async def main():
        search_results = await search_open_targets_ids(suchbegriff)

        print(f"\n[+] Suchergebnisse für den Freitext: '{suchbegriff}'")
        for res in search_results[:5]:  # Zeige die Top 5 Treffer
            print(f"  -> ID: {res['id']} | Typ: {res['type'].upper()} | Name: {res['name']}")


    asyncio.run(main())