import sys
import json
from pathlib import Path

try:
    from protein import UniProtSearchFetcher
except ImportError:
    UniProtSearchFetcher = None
    from protein.processors.get_single_protein import _UNIPROT_FETCHER

for _p in Path(__file__).resolve().parents:
    if (_p / "core").is_dir() and (_p / "embedder").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break



_UNIPROT_TISSUE_MIN_SCORE = 0.75

if UniProtSearchFetcher is not None:
    _UNIPROT_FETCHER = UniProtSearchFetcher()
def _gene_value(attrs):
    return (
        attrs.get("symbol")
        or attrs.get("name")
        or attrs.get("Gene")
        or attrs.get("gene")
        or attrs.get("geneId")
        or attrs.get("gene_id")
        or attrs.get("ensembl_id")
    )


def _protein_evidence(protein, genes, keywords, organs, goterms):
    payload = json.dumps(protein, default=str).lower()
    matched = {
        "genes": [item for item in genes if item.lower() in payload],
        "keywords": [item for item in keywords if item.lower() in payload],
        "tissues": [item for item in organs if item.lower() in payload],
        "goterms": [item for item in goterms if item.lower().replace("_", ":") in payload],
    }
    weights = {"genes": 0.40, "goterms": 0.25, "keywords": 0.20, "tissues": 0.15}
    available = [key for key, values in (
        ("genes", genes), ("goterms", goterms),
        ("keywords", keywords), ("tissues", organs)
    ) if values]
    denominator = sum(weights[key] for key in available) or 1.0
    score = sum(
        weights[key] for key in available if matched[key]
    ) / denominator
    return matched, round(float(score), 6)



import itertools

def build_uniprot_queries(
    genes: list[str],
    keywords: list[str],
    organs: list[str],
    goterms: list[str],
    batch_size: int = 15,
) -> list[str]:
    """Generates a list of ready-to-run UniProt search queries batched by genes,

    keywords, and GO terms to prevent HTTP 400 (URL/clause length errors).
    """
    base_part = "(organism_id:9606)"

    # --- 1. Clean & Format Inputs ---
    clean_genes = sorted(
        {str(g).strip() for g in genes if g and str(g).strip()}
    )
    clean_keywords = sorted(
        {str(kw).strip() for kw in keywords if kw and str(kw).strip()}
    )
    clean_organs = sorted(
        {str(o).strip() for o in organs if o and str(o).strip()}
    )
    clean_goterms = sorted(
        {
            str(term).strip().replace("_", ":")
            for term in goterms
            if term and str(term).strip()
        }
    )

    # --- 2. Chunking Helper ---
    def chunk_list(items: list[str], size: int) -> list[list[str]]:
        if not items:
            return [[]]  # Empty slot for Cartesian product
        return [items[i : i + size] for i in range(0, len(items), size)]

    gene_chunks = chunk_list(clean_genes, batch_size)
    keyword_chunks = chunk_list(clean_keywords, batch_size)
    goterm_chunks = chunk_list(clean_goterms, batch_size)

    # Organs are usually small in number, but we handle them cleanly
    organ_query = None
    if clean_organs:
        organ_clauses = [f'tissue:"{o}"' for o in clean_organs]
        organ_query = f"({' OR '.join(organ_clauses)})"

    # --- 3. Build Batch Combination Queries ---
    queries = []

    # Cartesian product generates every combination of chunks
    for g_chunk, kw_chunk, go_chunk in itertools.product(
        gene_chunks, keyword_chunks, goterm_chunks
    ):
        query_parts = [base_part]

        # Gene clause
        if g_chunk:
            gene_clauses = [
                f"gene_exact:{g}"
                if not g.startswith("ENSG")
                else f"xref:Ensembl-{g}"
                for g in g_chunk
            ]
            query_parts.append(f"({' OR '.join(gene_clauses)})")

        # Keyword clause
        if kw_chunk:
            kw_clauses = [
                f"keyword:{kw}" if kw.startswith("KW-") else f'keyword:"{kw}"'
                for kw in kw_chunk
            ]
            query_parts.append(f"({' OR '.join(kw_clauses)})")

        # Tissue/Organ clause (Static across chunks)
        if organ_query:
            query_parts.append(organ_query)

        # GO Term clause (Fixed field name: 'go:' instead of 'go_id:')
        if go_chunk:
            go_clauses = [f'go:"{term}"' for term in go_chunk]
            query_parts.append(f"({' OR '.join(go_clauses)})")

        # Only generate query if there's evidence beyond organism_id
        if len(query_parts) > 1:
            queries.append(" AND ".join(query_parts))

    # Fallback to base organism query if no evidence terms were provided
    if not queries:
        queries.append(base_part)

    return queries


def build_relaxed_uniprot_query(
    genes: list[str],
    keywords: list[str],
    organs: list[str],
    goterms: list[str],
) -> str:
    clauses = ["organism_id:9606"]
    clauses.extend(
        f"gene_exact:{g}" if not str(g).startswith("ENSG") else f"xref:Ensembl-{g}"
        for g in sorted({str(item).strip() for item in genes if item})
    )
    clauses.extend(
        f"keyword:{kw}" if str(kw).startswith("KW-") else f'keyword:"{kw}"'
        for kw in sorted({str(item).strip() for item in keywords if item})
    )
    clauses.extend(
        f'tissue:"{item}"'
        for item in sorted({str(item).strip() for item in organs if item})
    )
    clauses.extend(
        f'go:"{str(item).strip().replace("_", ":")}"'
        for item in sorted({str(item).strip() for item in goterms if item})
    )
    return " OR ".join(clauses)


async def fetch_uniprot_protein(g):
    # Extract nodes
    genes = [
        _gene_value(attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "GENE"
    ]
    keywords = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "KEYWORD" and attrs.get("sub_type") == "META"
    ]
    organs = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "TISSUE" and attrs.get("sub_type") == "UNIPROT"
    ]
    goterms = [
        nid.replace("GO:", "").replace("GO_", "") for nid, attrs in g.G.nodes(data=True) if attrs.get("type") == "GO_TERM"
    ]

    print(
        f"Input counts -> Genes: {len(genes)}, Keywords: {len(keywords)}, Organs: {len(organs)}, GO Terms: {len(goterms)}"
    )

    # Generate ready-to-run batched queries
    queries = build_uniprot_queries(
        genes=genes,
        keywords=keywords,
        organs=organs,
        goterms=goterms,
        batch_size=25,
    )

    print(f"Generated {len(queries)} ready-to-run queries.")

    all_protein_rows = []
    seen_accessions = set()

    retrieval_strategy = "strict"

    # Execute batch queries sequentially
    for i, q in enumerate(queries, 1):
        print(f"Executing Query [{i}/{len(queries)}]: {q}...")
        results = await _UNIPROT_FETCHER.search(query=q)
        protein_rows = (
            results.get("results", []) if isinstance(results, dict) else []
        )

        for protein in protein_rows:
            accession = protein.get("primaryAccession")
            if accession and accession not in seen_accessions:
                seen_accessions.add(accession)
                all_protein_rows.append(protein)

    if not all_protein_rows and any([genes, keywords, organs, goterms]):
        retrieval_strategy = "relaxed"
        q = build_relaxed_uniprot_query(genes, keywords, organs, goterms)
        print(f"Executing relaxed Query: {q}...")
        results = await _UNIPROT_FETCHER.search(query=q)
        protein_rows = (
            results.get("results", []) if isinstance(results, dict) else []
        )
        for protein in protein_rows:
            accession = protein.get("primaryAccession")
            if accession and accession not in seen_accessions:
                seen_accessions.add(accession)
                all_protein_rows.append(protein)

    print(f"Extracted {len(all_protein_rows)} unique proteins across all batches.")

    # Graph-building logic continues with all_protein_rows...
    for protein in all_protein_rows:
        accession = protein.get("primaryAccession")
        if not accession:
            continue
        matched, score = _protein_evidence(
            protein, genes, keywords, organs, goterms
        )
        g.add_node(
            attrs=dict(
                id=accession,
                type="PROTEIN",
                **protein,
                evidence=matched,
                protein_score=score,
                retrieval_strategy=retrieval_strategy,
                embed_key="proteinDescription__recommendedName__fullName__value",
            )
        )


        #

        for gene_id, attrs in g.G.nodes(data=True):
            value = _gene_value(attrs) if attrs.get("type") == "GENE" else None
            if value and str(value) in matched["genes"]:
                g.add_edge(
                    src=gene_id, trgt=accession,
                    attrs=dict(rel="encodes", src_layer="GENE", trgt_layer="PROTEIN"),
                )
        for go_id in matched["goterms"]:
            graph_go_id = go_id if g.G.has_node(go_id) else f"GO:{go_id}"
            if g.G.has_node(graph_go_id):
                g.add_edge(
                    src=graph_go_id, trgt=accession,
                    attrs=dict(rel="supports", src_layer="GO_TERM", trgt_layer="PROTEIN"),
                )

        protein_kwds = [kw["name"] for kw in protein.get("keywords", [])]

        for kwd_name in protein_kwds:
            kwd_node = g.get_node(value=kwd_name, key="name")
            if kwd_node is None:
                print("add keyword node:", kwd_name)
                kwd_node = dict(
                    id=kwd_name,
                    type="KEYWORD",
                    name=kwd_name,
                )
                g.add_node(kwd_node)

            g.add_edge(
                src=kwd_node["id"],
                trgt=accession,
                attrs=dict(
                    rel="describes",
                    src_layer="KEYWORD",
                    trgt_layer="PROTEIN",
                ),
            )

    count = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
    ]
    print("proteins extracted:", len(count), ":\n", count, "... done")
    return {
        "protein_count": len(count),
        "input_gene_count": len(genes),
        "input_keyword_count": len(keywords),
        "input_tissue_count": len(organs),
        "input_goterm_count": len(goterms),
        "retrieval_strategy": retrieval_strategy,
    }
