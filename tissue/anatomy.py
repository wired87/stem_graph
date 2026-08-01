import asyncio
import pprint

import httpx
import urllib.parse

from core import CLIENT


async def get_uberon_anatomy_children(
    g,
    uberon_id: str,
) -> dict[str, str]:
    """
    Asynchronously fetches only the direct, macro-anatomical sub-regions

    (children) of a specific UBERON ID, skipping cellular (CL) classifications.

    ALERT: UBeron is not species spcific but that is ok (MVP) because
    protien (expression) entries we receive for humans
    """
    formatted_id = uberon_id.replace(":", "_")
    iri = f"http://purl.obolibrary.org/obo/{formatted_id}"
    first_encode = urllib.parse.quote(iri, safe="")
    double_encode = urllib.parse.quote(first_encode, safe="")

    url = (
        f"https://www.ebi.ac.uk/ols4/api/ontologies/"
        f"uberon/terms/{double_encode}/hierarchicalDescendants"
    )
    params = {"size": 5000, "page": 0}
    anatomy_map = {}

    async with httpx.AsyncClient() as client:

        try:
            response = await client.get(
                url, params=params, timeout=15.0
            )
            response.raise_for_status()
            data = response.json()

            print("UBERON DATA rcvd")
            #pprint.pp(data)

            terms = data.get("_embedded", {}).get("terms", [])
            if terms:
                for term in terms:
                    try:
                        if term.get("is_obsolete"):
                            continue
                        #print("term", term)
                        subsets = set(term.get("in_subset", []))

                        if "human_subset" not in subsets:
                            continue

                        child_id = term.get("obo_id") or term.get("short_form")
                        name = term.get("label")

                        if child_id and child_id.startswith("UBERON:"):
                            anatomy_map[child_id] = name
                    except Exception as e:
                        print("Err", e)
        except Exception as e:
            print(f"Network error: {e}")

    #
    urls = [
        "https://www.ebi.ac.uk/ols4/api/ontologies/uberon/terms"
        for _ in anatomy_map.keys()
    ]

    uberon_details = await asyncio.gather(
        *[
            CLIENT.get(
                url,
                params={
                    "iri": f"http://purl.obolibrary.org/obo/{ubid.replace('-', '_').replace(':', '_')}"
                }
            )
            for url, ubid in zip(urls, anatomy_map.keys())
        ],
        return_exceptions=True,
    )

    for response, (ubid, description) in zip(uberon_details, anatomy_map.items()):
        if isinstance(response, Exception):
            continue

        if response.status_code != 200:
            continue

        try:
            data = response.json()
        except Exception:
            print("BAD RESPONSE", response.url)

        terms = data.get("_embedded", {}).get("terms", [])

        if not terms:
            continue

        term = terms[0]

        annotations = term.get("annotation", {})

        taxons = annotations.get("present in taxon", [])

        is_human = any(
            "NCBITaxon_9606" in taxon
            for taxon in taxons
        )

        if not is_human:
            continue
        #
        g.add_node(
            dict(
                id=ubid.replace(":", "_"),
                description=description,
                type="TISSUE",
                sub_type="UBERON",
                embed_key="description",
            )
        )

        # PARENT -> ANATOMICAL CHILDREN
        g.add_edge(
            uberon_id,
            ubid,
            attrs=dict(
                rel="category",
                src_layer="TISSUE",
                trgt_layer="TISSUE",
            )
        )
    print("TISSUE ATOAY BUILD... DONE")


