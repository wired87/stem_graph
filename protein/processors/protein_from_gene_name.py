from protein import UniProtSearchFetcher

_UNIPROT_FETCHER = UniProtSearchFetcher()

async def fetch_uniprot_protein_from_gene_name(
    genes:list[str],
    keywords:list[str] or None = None,
):
    #
    query_parts = [
        "(organism_id:9606)"
    ]

    #
    if genes:

        if not isinstance(
            genes,
            list,
        ):
            genes = [genes]

        gene_query = " OR ".join(

            (
                f"gene_exact:{g.strip()}"
                if not g.startswith("ENSG")
                else f"xref:Ensembl-{g.strip()}"
            )

            for g in genes
            if g and g.strip()
        )

        if gene_query:
            query_parts.append(
                f"({gene_query})"
            )

    # fitler for protein sub type (e.g. io channel
    if keywords:
        if not isinstance(
            keywords,
            list,
        ):
            keywords = [keywords]

        keyword_query = " OR ".join(

            (
                f"keyword:{kw.strip()}"
                if kw.startswith("KW-")
                else f'keyword:"{kw.strip()}"'
            )

            for kw in keywords
            if kw and kw.strip()
        )

        if keyword_query:
            query_parts.append(
                f"({keyword_query})"
            )

    #
    query = " AND ".join(
        query_parts
    )

    print("UniProt query:", query)

    results = await _UNIPROT_FETCHER.search(
        query=query,
        size=500,
    )

    protein_rows = results["results"]
    print("uniprot response type:", type(protein_rows))
    print("uniprot rows extracted:", len(protein_rows))
    accessions = [protein.get("primaryAccession") for protein in protein_rows]

    print("proteins extracted:", len(accessions), ":\n", accessions, "... done")
    return accessions
