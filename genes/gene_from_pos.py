import httpx


async def get_gene_details_from_position(chromosome: str, position: int) -> dict:
    """
    Fragt Ensembl nach Genen ab, die auf dieser exakten Position liegen,
    und ermittelt deren Start- und Stopp-Sequenzgrenzen.
    """
    chrom = chromosome.replace("chr", "")

    # Wir fragen ein winziges Fenster (nur die eine Base) ab, um zu sehen, welches Gen dort liegt
    url = f"https://rest.ensembl.org/overlap/region/human/{chrom}:{position}-{position}?feature=gene"
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Ensembl API Error: {response.status_code}")

        genes = response.json()

        if not genes:
            return {
                "message": f"Kein Gen an Position {position} auf Chromosom {chrom} gefunden (Intergenische Region)."}

        # Wir nehmen das erste Gen, das auf dieser Position gematcht wird
        target_gene = genes[0]

        return {
            "id": target_gene.get("id"),
            "description": target_gene.get("description"),
            "biotype": target_gene.get("biotype"),  # z.B. protein_coding
            "chromosome": chrom,
            "gene_start": target_gene.get("start"),  # Start-Koordinate des gesamten Gens
            "gene_end": target_gene.get("end"),  # Stopp-Koordinate des gesamten Gens
            "strand": "Forward (+)" if target_gene.get("strand") == 1 else "Reverse (-)"
        }


# --- TEST ---
async def main():
    # Wir testen deine Position auf Chromosom 7
    result = await get_gene_details_from_position("chr7", 55229255)
    import json
    print(json.dumps(result, indent=4))

# asyncio.run(main())