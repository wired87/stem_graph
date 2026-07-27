import embedder
import numpy as np

UNIPROT_TO_GO_MAPPING = {
    # -------------------------------------------------------------------------
    # KW-0407: Ion channel
    # -------------------------------------------------------------------------
    "KW-0407": [
        "GO:0005216",  # MF: ion channel activity (Die Pore selbst!)
        "GO:0034702",  # CC: ion channel complex
        "GO:0006811",  # BP: ion transport
        "GO:0022838",  # MF: substrate-specific channel activity
    ],

    # -------------------------------------------------------------------------
    # KW-9992: Molecular Function (Hier verankert man die allgemeine Enzymaktivität)
    # -------------------------------------------------------------------------
    "KW-9992": [
        "GO:0003824",  # MF: catalytic activity (Das absolute Kern-Enzym-GO)
        "GO:0008152",  # BP: metabolic process (Da wo Enzyme meistens arbeiten)
    ],

    # -------------------------------------------------------------------------
    # KW-0527: Neuropeptide (Kurze Proteine / Peptidhormone / Signalpeptide)
    # -------------------------------------------------------------------------
    "KW-0527": [
        "GO:0005179",  # MF: hormone activity
        "GO:0007218",  # BP: neuropeptide signaling pathway
        "GO:0005576",  # CC: extracellular region (Da werden Peptide meist hinsekretiert)
        "GO:0031730",  # MF: neuropeptide receptor binding
    ]
}

def loop_kwd_fields_convert_to_fun(g):
    print("loop_kwd_fields_convert_to_fun...")
    for key in ["name", "definition"]:
        link_kw_to_fun(g, kwd_embed_key = key)

    # LOOP SYNYONYMS -> PACK INTO GRAPH
    link_syn_kw_to_fun(g)

def link_kw_to_fun(g, kwd_embed_key = "name"):
    print("filter_convert_kw_to_fun...")
    score = 0.8

    fun = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "FUNCTION_ANNOTATION"
    ]

    keywords = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "KEYWORD" and attrs.get("sub_type", "") != "META"
    ]

    if not fun or not keywords:
        print("Keine Funktionen oder Keywords zum Vergleichen gefunden.")
        return

    # 2. Embeddings berechnen
    embed = embedder.embed_batch([key[0] for key in fun])
    kw_embed = embedder.embed_batch([attrs[kwd_embed_key] for _, attrs in keywords])

    # 3. Kosinus-Ähnlichkeit (Matrix-Multiplikation)
    query_norms = np.linalg.norm(embed, axis=1, keepdims=True)
    key_norms = np.linalg.norm(kw_embed, axis=1, keepdims=True)

    # Matrix-Form: (Anzahl_Funktionen, Anzahl_Keywords)
    similarity_matrix = np.dot(embed, kw_embed.T) / (query_norms @ key_norms.T)

    fun_indices, kw_indices = np.where(similarity_matrix >= score)

    # Set, um doppelt hinzugefügte Keywords zu vermeiden, falls gewünscht
    added_keywords = set()

    for fun_idx, kw_idx in zip(fun_indices, kw_indices):
        kw_id, kw_attrs = keywords[kw_idx]
        fun_id, fun_attrs = fun[kw_idx]
        kw_name = kw_attrs["name"]

        if kw_name not in added_keywords:
            g.add_edge(
                fun_id,
                kw_id,
                attrs=dict(
                    rel="similar",
                    src_layer="FUNCTION_ANNOTATION",
                    trgt_layer="KEYWORD",
                )
            )
            print(
                f"ADDED KW: {kw_name} (Match fun {fun[fun_idx][0]}, Score: {similarity_matrix[fun_idx, kw_idx]:.4f})")
            added_keywords.add(kw_name)
    print("filter_convert_kw_to_fun... done")



def link_syn_kw_to_fun(g):
    print("filter_convert_kw_to_fun...")
    score = 0.8

    fun = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "FUNCTION_ANNOTATION"
    ]

    synnonyms = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "SYNONYM"
    ]


    # 2. Embeddings berechnen
    embed = embedder.embed_batch([key[0] for key in fun])
    kw_embed = embedder.embed_batch([attrs["name"] for _, attrs in synnonyms])

    # 3. Kosinus-Ähnlichkeit (Matrix-Multiplikation)
    query_norms = np.linalg.norm(embed, axis=1, keepdims=True)
    key_norms = np.linalg.norm(kw_embed, axis=1, keepdims=True)

    # Matrix-Form: (Anzahl_Funktionen, Anzahl_synnonyms)
    similarity_matrix = np.dot(embed, kw_embed.T) / (query_norms @ key_norms.T)

    fun_indices, kw_indices = np.where(similarity_matrix >= score)

    # Set, um doppelt hinzugefügte synnonyms zu vermeiden, falls gewünscht
    added_keywords = set()

    for fun_idx, kw_idx in zip(fun_indices, kw_indices):
        syn_id, syn_attrs = synnonyms[kw_idx]
        fun_id, fun_attrs = fun[kw_idx]

        neighbors = g.get_neighbor_list(syn_id, target_type="KEYWORD", just_ids=True)
        for neighor in neighbors:
            if neighor not in added_keywords:
                g.add_edge(
                    fun_id,
                    neighor,
                    attrs=dict(
                        rel="similar",
                        src_layer="FUNCTION_ANNOTATION",
                        trgt_layer="KEYWORD",
                    )
                )
                print(f"ADDED KW: {neighor}")
                added_keywords.add(neighor)
    print("filter_convert_kw_to_fun... done")




def filter_protein(g):
    """
    todo improve keyword - protein filtering (chck @vs: if match but other kw == any(item in PROTEIN_TYPE and item != PROTEIN_TYPE_NODE.id)
    """

    keep_proteins=set()
    keep_gos=set()
    keep_kw=set()

    fun = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "FUNCTION_ANNOTATION"
    ]

    #
    goterms = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "GO_TERMS"
    ]

    #
    keywords = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "KEYWORD"
           and attrs.get("type") != "META"
    ]


    proteins = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
    ]

    # GET Proteins <-> KEYWORDS <-> FUN
    for fid, fattrs in fun:
        neighbor_kwds = g.get_neighbor_list(fid, target_type="KEYWORD", just_ids=True)
        for kw in neighbor_kwds:
            for pid, pattrs in proteins:
                if kw in [kw['name'] for kw in pattrs.get('keywords', [])]:
                    keep_proteins.add(pid)
                    keep_kw.add(kw)

            # Get Proteins <-> GoTerms <-> KWD
            gt_neighbors = g.get_neighbor_list(fid, target_type="GO_TERM", just_ids=True)
            for term in gt_neighbors:
                neighbor_proteins = g.get_neighbor_list(term, target_type="PROTEIN", just_ids=True)
                for pid in neighbor_proteins:
                    if pid in [p[0] for p in proteins]:
                        keep_proteins.add(pid)
                        keep_gos.add(term)

    # ALIGN FUN -> TERM -> PROTEIN
    keep_kwds = align_function_to_term_outsrc_ntype(
        g,
        outsrc_type="PROTEIN"
    )
    for item in keep_kwds:
        keep_proteins.add(item)

    # FILTER META KWD <-> GOTERM <-> PROTEIN
    keep_kwds = filter_proteins_for_terms_for_meta_kws(g)
    for item in keep_kwds:
        keep_proteins.add(item)

    # outsrc proteins no match fun or meta
    for nid, attrs in proteins:
        if nid not in keep_proteins:
            print("delete protein:", nid)
            g.delete_node(nid)

    # WE JST TRANSFER PROTEINS AND DELETE ENTIRE GRAPH THEN...
    """# outsrc None nodes
    none_nodes = [k for k, v in g.G.nodes(data=True) if v.get("type") is None]
    for nid in none_nodes:
        print("delete NONE node:", nid)
        g.delete_node(nid)

    for nid, attrs in goterms:
        if nid not in keep_gos:
            print("delete term:", nid)
            g.delete_node(nid)

    for nid, attrs in keywords:
        if nid not in keep_kwds:
            print("delete kwd:", nid)
            g.delete_node(nid)"""
    print("channels sorted for... done")
    print("filtered proteins: ", len(keep_proteins), " / ", len(proteins), " (", len(keep_proteins)/len(proteins), "... done")










def filter_proteins_for_terms_for_meta_kws(g):
    # avoid non pt-entries
    print("filter_proteins_for_terms_for_meta_kws...")
    proteins: list[str] | str = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
    ]
    print("proteins: ", len(proteins), proteins)

    # get key for go
    key= [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "KEYWORD" and attrs.get("sub_type") == "META"
    ][0]

    gt_group = UNIPROT_TO_GO_MAPPING[key]

    keep_ps = set()
    for p in proteins:
        neighbor_gts = g.get_neighbor_list(p, target_type="GO_TERM", just_ids=True)
        if any(item in neighbor_gts for item in gt_group):
            keep_ps.add(p)

    print("outsrc proteins: ", len(keep_ps), "/", len(proteins))

    print("filter_proteins_for_terms_for_meta_kws... done")
    return keep_ps

















