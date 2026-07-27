from args import CLIENT


async def fetch_variant_annotation(rsid ):
    url = f"https://rest.ensembl.org/variation/human/{rsid}?content-type=application/json"

    try:
        async with CLIENT.get(url) as response:
            if response.status == 404:
                return {"rsid": rsid, "status": "Not Found in db"}

            if response.status != 200:
                return {"rsid": rsid, "status": f"API Error {response.status}"}

            data = await response.json()

            return data

    except Exception as e:
        return {"rsid": rsid, "error": str(e)}


