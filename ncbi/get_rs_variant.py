from __future__ import annotations

import asyncio
import httpx


DBSNP_API = "https://api.ncbi.nlm.nih.gov/variation/v0/refsnp/"


async def classify_rsid(rsid: str, client: httpx.AsyncClient) -> dict:
    """
    Classify a dbSNP rsID.

    Returns:
        {
            "rsid": "rs429358",
            "type": "SNV",
            "clinical": False,
            "gene": None,
            "status": "ok"
        }
    """
    rsid = rsid.lower().replace("rs", "")

    try:
        r = await client.get(
            f"{DBSNP_API}{rsid}",
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return data

    except Exception as e:
        return {
            "rsid": f"rs{rsid}",
            "status": "error",
            "error": str(e),
        }


async def classify_rsids(rsids: list[str]) -> list[dict]:
    async with httpx.AsyncClient() as client:
        tasks = [classify_rsid(rsid, client) for rsid in rsids]
        return await asyncio.gather(*tasks)


if __name__ == "__main__":
    rsids = [
        "rs429358",
        "rs7412",
        "rs1801133",
        "rs3094315",
    ]

    results = asyncio.run(classify_rsids(rsids))

    print(results[0])