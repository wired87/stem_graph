import asyncio

from firegraph.graph.local_graph_utils import GUtils
from goterm.term_from_ensg import get_go_terms_batch
from goterm.term_from_id import align_term_to_fun
from goterm.unique_term_ctlr import GOTermMapping, unique_term_ctlr
from protein.processors.from_geneids import protein_from_genids
from protein.processors.go_to_prot import set_term_from_protein
from protein.processors.protein_from_gene import fetch_uniprot_protein
from embedder import embed
from protein.processors.uberon_to_uniprot_tissue import uberon_to_uniprot_tissue
from tissue.uberon import build_tissue_graph
from keywords.meta_kw_validation import classify_protein_type_to_upkwd


async def predict_proteins(
    functional_annotation=("memory formation",),
    tissue="Thalamus",
    protein_type = "Neuropeptide"
):
    print("predict_proteins...")
    g = GUtils()
    warnings = []

    if functional_annotation:
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

    #
    if protein_type is not None:

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
            print("Start tissue process")
            await build_tissue_graph(tissue, g)
            print("Link Uberon to UniProt")
            await uberon_to_uniprot_tissue(g)
            print("Tissue process finished...")
        except Exception as exc:
            warning = f"tissue enrichment skipped: {exc}"
            warnings.append(warning)
            print(warning)


    # GENE EXPRESSION direkte schnittstelle von uberon -> gene : PARALLELIZE
    if tissue:
        try:
            print("start hpa process...")
            from protein.expression.include_expression import include_brain_expression_hpa
            # GET ALL GENES EXPRESSED IN TISSUE
            include_brain_expression_hpa(g, tissue_query=tissue)
            print("include_brain_expression_hpa... done")
        except Exception as exc:
            warning = f"HPA expression enrichment skipped: {exc}"
            warnings.append(warning)
            print(warning)
        print("start protein process...")

        gene_node = g.get_node("GENE_IDS")
        hpa_gene_ids = list((gene_node or {}).get("data") or [])
        if not hpa_gene_ids:
            warning = "HPA expression enrichment produced no gene ids for this tissue."
            warnings.append(warning)
            print(warning)
        else:
            results = await get_go_terms_batch(hpa_gene_ids)

            res: GOTermMapping = unique_term_ctlr(results)

            g.add_node(
                dict(
                    id="GO_TERM_IDS",
                    type="TERM_MASTER",
                    data=results,
                    unique=res.unique_go_terms,
                    gene_ctlr=res.mapped_indices,
                )
            )
            # Coffee101.
            # term from db + align fun to term
            align_term_to_fun(g)

            # GET ALL PROTEINS FROM EXPRESSED GENES everywhere gid has alignment
            alignment = g.get_node("GO_TERM_IDS").get("total_alignment")
            if alignment:
                genes = [i for i, j in zip(hpa_gene_ids, alignment) if j == 0]
            else:
                genes = hpa_gene_ids
                warning = "GO/function alignment unavailable; using HPA tissue genes directly."
                warnings.append(warning)
                print(warning)
            await protein_from_genids(g, genes)
            print("protein_from_genids... done")

            protein = [
                (nid, attrs)
                for nid, attrs in g.G.nodes(data=True)
                if attrs.get("type") == "PROTEIN"
            ]
            print("proteins outsrcd", len(protein))

    #
    if protein_type is not None:
        try:
            classify_protein_type_to_upkwd(g, protein_type)
            print("classify_protein_type_to_upkwd... done")
        except Exception as exc:
            warning = f"protein-type enrichment skipped: {exc}"
            warnings.append(warning)
            print(warning)

    # GET FUNCITONAL TERMS
    if functional_annotation:
        try:
            from goterm.workflows.term_from_keyword import term_from_fun
            await term_from_fun(g)

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
