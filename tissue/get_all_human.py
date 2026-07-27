import asyncio
import json
import os

import aiohttp


OLS_URL = "https://www.ebi.ac.uk/ols4/api/ontologies/uberon/terms"


async def get_all_human_uberon_terms():
    terms = []
    page = 0

    async with aiohttp.ClientSession() as session:
        while True:
            url = f"{OLS_URL}?page={page}&size=1000"

            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()

            for term in data.get("_embedded", {}).get("terms", []):
                obo_id = term.get("obo_id")

                if not obo_id:
                    continue

                terms.append({
                    "id": obo_id,
                    "label": term.get("label"),
                })

            if page >= data["page"]["totalPages"] - 1:
                break

            page += 1

    return terms


async def main():
    ub_tiss_dest = os.path.abspath("data/uberon_tissue_labels.json")

    if not os.path.isfile(ub_tiss_dest):
        os.makedirs(ub_tiss_dest, exist_ok=True)

        terms = await get_all_human_uberon_terms()

        print(f"Found {len(terms)} Uberon terms")

        for term in terms:
            print(term["id"], term["label"])

        with open(ub_tiss_dest, "w") as _kw_fh:
            json.write(_kw_fh)

    else:
        with open(ub_tiss_dest, encoding="utf-8") as _kw_fh:
            json.load(_kw_fh)



if __name__ == "__main__":
    asyncio.run(main())