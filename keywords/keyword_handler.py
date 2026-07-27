import json

import sys
from pathlib import Path
import numpy as np
import requests
import os
from embedder import embed_batch
from embedder.embed_node_key import _node_embed_text
from firegraph.graph.local_graph_utils import GUtils

import json
from pathlib import Path

import requests


def validate_keywords() -> Path:
    url = "https://rest.uniprot.org/keywords/stream?compressed=false&format=json&query=%28*%29"

    local_path = (
        Path(__file__).resolve().parent.parent
        / "keywords"
        / "key_words_uniprot.json"
    )

    local_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not local_path.is_file():

        print(f"{local_path} not found. Downloading...")

        response = requests.get(
            url,
            timeout=120,
        )

        response.raise_for_status()

        with open(
            local_path,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                response.json(),
                f,
                ensure_ascii=False,
                indent=2,
            )
    return local_path


#if __name__ == "__main__":
_KEYWORDS_UNIPROT_JSON = validate_keywords()


def _keyword_uniprot_term(nid: str, attrs: dict) -> str:
    return str(attrs.get("name") or attrs.get("definition") or nid)


# CHAR: repo root on sys.path when this file is run as a script.
for _p in Path(__file__).resolve().parents:
    if (_p / "core").is_dir() and (_p / "embedder").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break


def _tissue_names_from_graph(g: GUtils) -> list[str]:
    names: list[str] = []
    skipped_cached = 0
    for nid, attrs in g.G.nodes(data=True):
        if attrs.get("type") != "TISSUE":
            continue

        label = attrs.get("name")
        if label and label not in names:
            names.append(label)

    print(f"tissue labels extracted: {names} (cached-skipped: {skipped_cached})")
    return names


async def build_keyword_graph(
    g:GUtils,
) -> list[str]:
    print("build_keyword_graph...")
    dest_file = "keywords/key_word_g.json"

    def walk_parents(center_id, parents):
        """
        Recursive parent traversal.
        parent -> center
        """

        for parent in parents:
            p = parent["keyword"]

            g.add_node(
                attrs=dict(
                    id=p["id"],
                    name=p["name"],
                    definition=p.get("definition", ""),
                    type="KEYWORD",
                    embed_key='name',
                )
            )
            # center -> child
            g.add_edge(
                center_id,
                p["id"],
                attrs=dict(
                    rel="parent",
                    src_layer="KEYWORD",
                    trgt_layer="KEYWORD",
                )
            )

            # recursive parent chain
            if "parents" in parent:
                walk_parents(
                    p["id"],
                    parent["parents"]
                )

    def walk_children(center_id, children):
        """
        Recursive child traversal.
        center -> child
        """

        for child in children:
            c = child["keyword"]
            g.add_node(
                attrs=dict(
                    id=c["id"],
                    name=c["name"],
                    type="KEYWORD",
                    embed_key='name',
                )
            )

            # center -> child
            g.add_edge(
                center_id,
                c["id"],
                attrs=dict(
                    rel="children",
                    src_layer="KEYWORD",
                    trgt_layer="KEYWORD",
                )
            )

            # recursive children
            if "children" in child:
                walk_children(
                    c["id"],
                    child["children"]
                )


    def include_keywords(data):
        #
        for item in data["results"]:
            center = item["keyword"]

            # -------------------------
            # CENTER NODE
            # -------------------------
            g.add_node(
                attrs=dict(
                    id=center["id"],
                    name=center["name"],
                    definition=item.get("definition"),
                    type="KEYWORD",
                    embed_key='definition',
                )
            )

            # -------------------------
            # CATEGORY NODE
            # -------------------------
            if "category" in item:
                category = item["category"]

                g.add_node(
                    attrs=dict(
                        id=category["id"],
                        name=category["name"],
                        type="KEYWORD",
                        embed_key="name",
                    )
                )

                g.add_edge(
                    center["id"],
                    category["id"],
                    attrs=dict(
                        rel="category",
                        src_layer="KEYWORD",
                        trgt_layer="KEYWORD",
                    )
                )

            for go in item.get("geneOntologies", []):
                g.add_node(
                    attrs=dict(
                        id=go["goId"],
                        name=go["name"],
                        type="GO_TERM",
                        embed_key="name",
                    )
                )

                g.add_edge(
                    center["id"],
                    go["goId"],
                    attrs=dict(
                        rel="go_term",
                        src_layer="KEYWORD",
                        trgt_layer="GO_TERM",
                    )
                )
            # -------------------------
            # SYNONYMS
            # -------------------------
            for synonym in item.get("synonyms", []):
                syn_id = f"SYN::{synonym}"

                g.add_node(
                    attrs=dict(
                        id=syn_id,
                        name=synonym,
                        type="SYNONYM",
                        embed_key="name",
                    )
                )

                #
                g.add_edge(
                    center["id"],
                    syn_id,
                    attrs=dict(
                        rel="go_term",
                        src_layer="KEYWORD",
                        trgt_layer="SYNONYM",
                    )
                )

            # -------------------------
            # PARENTS
            # -------------------------
            walk_parents(
                center["id"],
                item.get("parents", [])
            )

            # -------------------------
            # CHILDREN
            # -------------------------
            walk_children(
                center["id"],
                item.get("children", [])
            )

    try:
        g.load_graph(dest_file)
    except Exception as e:
        print("Err load exsiitng Graph:", e, "fetch manually...")

        #
        with open(_KEYWORDS_UNIPROT_JSON, encoding="utf-8") as _kw_fh:
            data = json.load(_kw_fh)



        #
        include_keywords(data)

    print("finished keyword graph buildup...")


def extract_outsrc_keywords(g, similarity_threshold: float = 0.75, top_k: int = 20):
    """
    Match FUNCTION_ANNOTATION nodes to UniProt KEYWORD nodes by embedding similarity.

    Prompt (user): no protein nodes — repair keyword extraction so matches survive
    and downstream UniProt protein fetch can run.
    """
    fun_list = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "FUNCTION_ANNOTATION"
    ]

    dis_list = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "DISEASE_ANNOTATION"
    ]

    fun_list = [*fun_list, *dis_list]

    print("fun_list", len(fun_list), fun_list)

    if not fun_list:
        print("no function annotations — skip keyword filter")
        return

    keyword_nodes = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "KEYWORD" and attrs.get("embed_key")
    ]

    if not keyword_nodes:
        print("no keyword nodes — skip keyword filter")
        return

    # PERFORM VS IDENTIFY KEYWORDS
    fun_vec = embed_batch([_node_embed_text(nid, attrs) for nid, attrs in fun_list])
    key_vec = embed_batch([_node_embed_text(nid, attrs) for nid, attrs in keyword_nodes])

    fun_vec_norms = np.linalg.norm(fun_vec, axis=1, keepdims=True)
    key_vec_norms = np.linalg.norm(key_vec, axis=1, keepdims=True)

    similarity_matrix = np.dot(fun_vec, key_vec.T) / (fun_vec_norms @ key_vec_norms.T)

    above_threshold = np.any(similarity_matrix >= similarity_threshold, axis=0)

    match_nodes = [
        (nid, attrs)
        for idx, (nid, attrs) in enumerate(keyword_nodes)
        if above_threshold[idx]
    ]

    for nid, matched_node in match_nodes:
        print("match node", nid, matched_node.get("name", nid))
        matched_node["match"] = True

        neighbors = g.get_neighbor_list(nid)
        if neighbors:
            for nnid, _nattrs in neighbors.items():
                g.G.nodes[nnid]["match"] = True

    keyword_ids = [
        nid for nid, attrs in g.G.nodes(data=True)
        if attrs.get("match") is True
           and attrs.get("type") == "KEYWORD"
    ]

    all_keywords = [
        nid for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "KEYWORD"
    ]

    # DELETE KEYWORDS
    if keyword_ids:
        for nid in all_keywords:
            if nid not in keyword_ids:
                g.delete_node(nid)
    else:
        print("keyword filter found no matches — keeping full keyword graph")
    print("keywords extracted:", keyword_ids)




