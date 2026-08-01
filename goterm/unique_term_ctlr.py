from dataclasses import dataclass


@dataclass
class GOTermMapping:
    unique_go_terms: list[str]
    mapped_indices: list[list[int]]


def unique_term_ctlr(go_terms_per_gene: list[list[str]]) -> GOTermMapping:
    """
    Transforms nested list of GO terms into a unique GO terms list 
    and a mapped list of integer indices.

    Args:
        go_terms_per_gene: list[list[str]] where each outer index represents a gene.

    Returns:
        GOTermMapping containing:
          - unique_go_terms: list[str] of all unique GO terms across all genes.
          - mapped_indices: list[list[int]] mirroring input structure with term indices.
    """
    unique_go_terms: list[str] = []
    term_to_idx: dict[str, int] = {}

    mapped_indices: list[list[int]] = []

    for gene_terms in go_terms_per_gene:
        gene_indices: list[int] = []

        for term in gene_terms:
            # Add to lookup table and list if encountered for the first time
            if term not in term_to_idx:
                term_to_idx[term] = len(unique_go_terms)
                unique_go_terms.append(term)

            gene_indices.append(term_to_idx[term])

        mapped_indices.append(gene_indices)

    return GOTermMapping(
        unique_go_terms=unique_go_terms,
        mapped_indices=mapped_indices
    )


# --- Example Usage ---
if __name__ == "__main__":
    # Simulated output from get_go_terms_batch
    raw_results = [
        ["GO:0006281", "GO:0003677", "GO:0005634"],  # Gene 0
        ["GO:0005634", "GO:0008150"],  # Gene 1
        ["GO:0006281", "GO:0008150", "GO:0003677"]  # Gene 2
    ]

    res:GOTermMapping = unique_term_ctlr(raw_results)

    print("Unique GO Terms:")
    for idx, term in enumerate(res.unique_go_terms):
        print(f"  [{idx}] {term}")

    print("\nMapped Indices per Gene:")
    for gene_idx, idx_list in enumerate(res.mapped_indices):
        print(f"  Gene {gene_idx}: {idx_list}")