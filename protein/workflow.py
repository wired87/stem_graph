import asyncio

from firegraph.graph.local_graph_utils import GUtils
from protein.processors.protein_from_gene import fetch_uniprot_protein

async def predict_proteins(
    functional_annotation=("synaptic transmission",),
    tissue="Thalamus",
    protein_type = "Ion channel"
):
    print("predict_proteins...")
    g = GUtils()
    warnings = []

    #
    if protein_type is not None:
        from embedder import embed

        protein_type = str(protein_type).strip()
        g.add_node(
            dict(
                id=f"PROTEIN_TYPE::{protein_type}",
                embedding=embed(protein_type),
                embed_key="id",
                type="PROTEIN_TYPE_INPUT"
            )
        )
        print("Protein type set in G")

    #
    if tissue:
        try:
            from protein.processors.uberon_to_uniprot_tissue import uberon_to_uniprot_tissue
            from tissue.uberon import build_tissue_graph

            print("Start tissue process")
            await build_tissue_graph(tissue, g)
            print("Link Uberon to UniProt")
            await uberon_to_uniprot_tissue(g)
            print("Tissue process finished...")
        except Exception as exc:
            warning = f"tissue enrichment skipped: {exc}"
            warnings.append(warning)
            print(warning)

    #
    if functional_annotation:
        from embedder import embed

        print("Build functional annotation...")
        annotations = (
            [functional_annotation]
            if isinstance(functional_annotation, str)
            else list(functional_annotation)
        )
        for annotation in annotations:
            if not annotation or not str(annotation).strip():
                continue
            text = str(annotation).strip()
            g.add_node(
                attrs=dict(
                    id=f"FUNCTION::{text}",
                    type="FUNCTION_ANNOTATION",
                    description=text,
                    embedding=embed(text),
                    embed_key="description",
                )
            )
        print("Functional annotation finished")

    # GENE EXPRESSION direkte schnittstelle von uberon -> gene
    """if tissue:
        try:
            from protein.expression.include_expression import include_brain_expression_hpa

            include_brain_expression_hpa(g)
            print("include_brain_expression_hpa... done")
        except Exception as exc:
            warning = f"HPA expression enrichment skipped: {exc}"
            warnings.append(warning)
            print(warning)
    """
    if protein_type is not None:
        try:
            from keywords.meta_kw_validation import classify_protein_type_to_upkwd

            classify_protein_type_to_upkwd(g, protein_type)
            print("classify_protein_type_to_upkwd... done")
        except Exception as exc:
            warning = f"protein-type enrichment skipped: {exc}"
            warnings.append(warning)
            print(warning)

    # GET FUNCITONAL TERMS
    if functional_annotation:
        try:
            from goterm.workflows.term_from_keyword import term_from_keywords

            await term_from_keywords(g)
        except Exception as exc:
            warning = f"GO enrichment skipped: {exc}"
            warnings.append(warning)
            print(warning)

    # GET PROTIENS
    retrieval = await fetch_uniprot_protein(g)
    print("fetch_uniprot_protein_from_gene... done")

    g.add_node(
        attrs=dict(
            id="PROTEIN_WORKFLOW_RESULT",
            type="WORKFLOW_RESULT",
            status="partial" if warnings else "success",
            warnings=warnings,
            **retrieval,
        )
    )
    g.print_status_G()
    print("Finished Protien Retrieval... done")
    return g

if __name__ == "__main__":
    asyncio.run(predict_proteins())
