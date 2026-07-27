from embedder import similarity
import numpy as np
from embedder import embed_batch

PROTEIN_TYPE_SYNONYMS = {
    "KW-0391": [

    "ion channel",

    "channel",

    "channel protein",

    "voltage-gated",

    "ligand-gated",



    # Sodium

    "sodium channel",

    "scn",



    # Potassium

    "potassium channel",

    "kcn",

    "kir",

    "kv",

    "k2p",

    "sk channel",

    "bk channel",



    # Calcium

    "calcium channel",

    "cacna",



    # Chloride

    "chloride channel",

    "clc",

    "clcn",

    "cftr",



    # TRP

    "trp channel",

    "trpv",

    "trpm",

    "trpc",

    "trpa",

    "trpp",



    # HCN

    "hcn",



    # ASIC

    "asic",



    # P2X

    "p2x",



    # Gap Junction

    "connexin",

    "pannexin",



    # Ligand-gated receptors that are channels

    "nicotinic acetylcholine receptor",

    "gaba-a receptor",

    "glycine receptor",

    "ionotropic glutamate receptor",

    "nmda receptor",

    "ampa receptor",

    "kainate receptor",



    # Common gene families

    "chrna",

    "chrnb",

    "chrnd",

    "chrne",

    "gabra",

    "gabrb",

    "gabrg",

    "glra",

    "gria",

    "grin",

    "grik",

    # Voltage-gated Sodium

    "scn",



    # Voltage-gated Calcium

    "cacna",



    # Voltage-gated Potassium

    "kcn",

    "kcna",

    "kcnb",

    "kcnc",

    "kcnd",

    "kcnf",

    "kcng",

    "kcnh",

    "kcni",

    "kcnj",

    "kcnk",

    "kcnma",

    "kcnn",

    "kcnq",

    "kcns",

    "kcnt",

    "kcnv",



    # Chloride

    "clcn",

    "clc",

    "cftr",

    "ano",

    "tmem16",



    # TRP

    "trp",

    "trpa",

    "trpc",

    "trpm",

    "trpp",

    "trpv",



    # HCN

    "hcn",



    # ASIC

    "asic",

    "accn",



    # ENaC / DEG

    "scnn",



    # P2X

    "p2rx",



    # Gap junction

    "gj",

    "connexin",

    "gjb",

    "gja",

    "gjc",

    "gjd",

    "pannexin",

    "panx",



    # Nicotinic receptors

    "chrna",

    "chrnb",

    "chrnd",

    "chrne",

    "chrng",



    # GABA-A

    "gabra",

    "gabrb",

    "gabrg",

    "gabrd",

    "gabre",

    "gabrp",

    "gabrq",



    # Glycine

    "glra",

    "glrb",



    # Ionotropic glutamate

    "gria",

    "grik",

    "grin",



    # Serotonin ion channel

    "htr3",



    # Zinc channel

    "zacn",



    # Ryanodine receptor

    "ryr",



    # IP3 receptor

    "itpr",



    # Mitochondrial

    "vdac",



    # Mechano.sensitive

    "piezo",

    "piezo1",

    "piezo2",



    # Proton channel

    "hvcn",



    # Water channels (oft separat behandelt)

    "aquaporin",

    "aqp",

],
    "KW-9990": [

    "peptidase",

    "protease",

    "kinase",

    "phosphatase",

    "transferase",

    "ligase",

    "hydrolase",

    "oxidase",

    "reductase",

    "isomerase",

    "lyase",

    "synthetase",

    "synthase",

    "polymerase",

    "nuclease",

    "helicase",

    "topoisomerase",

    "dehydrogenase",

    "carboxylase",

    "decarboxylase",

    "oxygenase",

    "dioxygenase",

    "monooxygenase",

    "phosphorylase",

    "transaminase",

    "aminotransferase",

    "methyltransferase",

    "acetyltransferase",

    "glycosyltransferase",

    "lipase",

    "esterase",

    "amidase",

    "phosphodiesterase",

    "epimerase",

    "racemase",

],
    "KW-0527": [

    "peptide",

    "neuropeptide",

    "propeptide",

    "prepropeptide",

    "opioid peptide",

    "endorphin",

    "enkephalin",

    "dynorphin",

    "nociceptin",

    "orphanin",

    "substance p",

    "tachykinin",

    "neurokinin",

    "somatostatin",

    "neuropeptide y",

    "npy",

    "galanin",

    "orexin",

    "hypocretin",

    "vasopressin",

    "oxytocin",

    "bombesin",

    "gastrin",

    "cholecystokinin",

    "cck",

    "secretin",

    "glucagon",

    "ghrelin",

    "motilin",

    "insulin",

    "amylin",

    "calcitonin",

    "adrenomedullin",

    "urotensin",

    "kisspeptin",

    "relaxin",

    "hepcidin",

    "thymosin",

    "chemokine",

    "cytokine",

    "growth factor",

    "hormone",

],
}


UNIPROT_MAIN_CLASSES = {
    "KW-0407": "Ion channel",
    "KW-0808": "Enzyme",  # Transferase (Oder KW-9992 für meta Molecular Function)
    "KW-0527": "Neuropeptide",
}


def classify_protein_type_to_upkwd(
    g,
    text: str,
    minimum_score: float = 0.45,
):
    """
    Classify free text into one of the major
    UniProt keyword classes and add result
    as graph node.

    """
    print("classify_protein_type_to_upkwd...", text)
    if text is not None and len(text) > 0:
        #
        _description = text
        keyword_ids = list(
            UNIPROT_MAIN_CLASSES.keys()
        )

        keyword_names = list(
            UNIPROT_MAIN_CLASSES.values()
        )

        #
        key_vec = embed_batch(
            keyword_names
        )

        query_vec = embed_batch(
            [text]
        )

        #
        query_norms = np.linalg.norm(
            query_vec,
            axis=1,
            keepdims=True,
        )

        key_norms = np.linalg.norm(
            key_vec,
            axis=1,
            keepdims=True,
        )

        #
        similarity_matrix = (
            np.dot(
                query_vec,
                key_vec.T,
            )
            /
            (
                query_norms
                @
                key_norms.T
            )
        )

        #
        best_idx = int(
            np.argmax(
                similarity_matrix[0]
            )
        )

        keyword_id = keyword_ids[
            best_idx
        ]

        keyword_name = keyword_names[
            best_idx
        ]

        score = float(
            similarity_matrix[
                0,
                best_idx,
            ]
        )
        if score < minimum_score:
            print(
                f"No reliable UniProt class for {text!r} "
                f"(best score={score:.3f})"
            )
            return None

        #
        g.add_node(
            attrs=dict(
                id=text,
                type="KEYWORD_INPUT",
                embed_key="name",
                score=score,
            )
        )

        #for kwid in keyword_ids:
        print("ADD keyword_id", keyword_id)
        g.add_node(
            attrs=dict(
                id=keyword_id,
                name=keyword_name,
                type="KEYWORD",
                embed_key="name",
                sub_type="META",
            )
        )

        #
        g.add_edge(
            _description,
            keyword_id,
            attrs=dict(
                rel="uniprot_keyword",
                src_layer="KEYWORD_INPUT",
                trgt_layer="KEYWORD",
            )
        )
        return keyword_id
    else:
        print("classify_protein_type_to_upkwd text is None... done")



"""

TODO:
SAVE KEYWORD INPUT -> GET LIST FROM KEYWORD ID
PERFORM HARD SEARCH ON GOTERMS AND PROTEINS AFTER PRTEIN PROCESS 

"""



def process_protein_type(g, key, similarity_threshold=.8):
    print("process_protein_type...")
    keywords= [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "KEYWORD"
    ]

    protein_type_node = g.get_node(key="type", value="PROTEIN_TYPE_INPUT")

    #
    kw_names_embed = embed_batch([
        attrs[key] for _, attrs in keywords
    ])

    #
    similarity_matrix = [similarity(protein_type_node["embedding"], item) for item in kw_names_embed]

    #
    center_id = protein_type_node["id"]

    matches = set()

    #### NAME

    for i, (item, name) in enumerate(zip(similarity_matrix, [attrs[key] for _, attrs in keywords])):
        if center_id.lower() == "ion channel":
            if item > similarity_threshold or any(n.lower() in name.lower() for n in ION_CHANNEL_TERMS):
                matches.add(i)

        if center_id.lower() == "enzyme":
            if item > similarity_threshold or any(n.lower() in name.lower() for n in ENZYME_TERMS):
                matches.add(i)

        if center_id.lower() == "peptide":
            if item > similarity_threshold or any(n.lower() in name.lower() for n in PEPTIDE_TERMS):
                matches.add(i)

    # DELETE KEYWORDS from G
    for i, (nid, attrs) in enumerate(keywords):
        if i not in matches:
            g.delete_node(nid)
    print("process_protein_type... done")









def filter_kw_nodes_for_protein_type(g):
    print("filter_kw_nodes...")
    for vs_key in ["name", "definition"]:
        process_protein_type(
            g,
            key=vs_key
        )
    print("filter_kw_nodes... done")


def filter_proteins_for_description_name(g):
    print("filter_kw_nodes...")
    for vs_key in ["name", "definition"]:
        process_protein_type(
            g,
            key=vs_key
        )
    print("filter_kw_nodes... done")
