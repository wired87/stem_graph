
def set_term_from_protein(g, proteins):
    for nid, entry in proteins:
        _go_terms = []
        uni_prot_db_cross_references = entry.get("uniProtKBCrossReferences", [])

        for xref in uni_prot_db_cross_references:
            if xref.get("database") == "GO":
                go_id = xref.get("id")
                g.add_node(
                    attrs=dict(
                        id=go_id,
                        type="GO_TERM",

                    )
                )
                g.add_edge(
                    src=nid,
                    trgt=go_id,
                    attrs=dict(
                        rel="describes",
                        src_layer="PROTEIN",
                        trgt_layer="GO_TERM",
                    ),
                )
