import httpx


async def fetch_full_gene_sequence(chrom, start, end, gene_name, id) -> dict:
    """
    Nimmt die Details aus 'get_gene_details_from_position' und holt die
    vollständige genomische DNA-Sequenz des Gens von Start bis Ende.

    Optional kann eine Mutations-Koordinate direkt in der großen Sequenz getauscht werden.
    """

    # Ensembl Sequenz-Endpunkt für Regionen
    url = f"https://rest.ensembl.org/sequence/region/human/{chrom}:{start}-{end}"
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Ensembl Sequence API Error {response.status_code}: {response.text}")

        data = response.json()
        full_sequence = data["seq"].upper()
        return {
            "gene_name": gene_name,
            "sequence_length_bp": len(full_sequence),
            "reference_sequence": full_sequence,
            "id":id,
        }

