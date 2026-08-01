"""DuckDB-backed Human Protein Atlas brain-region expression cache."""

from __future__ import annotations

import ast
import json
import os
import re

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from protein.expression.validate_expression_data import validate_download_expression

from _db.queries import get_column
from core.app_utils import DB
from embedder import embed
from firegraph.embedder.perform_vs_from_str import vs

HPA_TABLE = "HPA"
HPA_BRAIN_REGION_URL = "https://www.proteinatlas.org/download/tsv/rna_brain_region_hpa.tsv.zip"
HPA_SCHEMA = {
    "id": "STRING PRIMARY KEY",
    "tissue": "STRING",
    "subregion": "STRING",
    "text": "STRING",
    "gene_ids": "STRING",
    "gene_symbols": "STRING",
    "embedding": "STRING",
    "source_url": "STRING",
}


def _norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _json_load(value, fallback):
    if value in (None, ""):
        return fallback
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        try:
            return ast.literal_eval(value)
        except Exception:
            return fallback


def _rows_for_db(tsv_path, source_url: str) -> list[dict]:
    grouped = defaultdict(lambda: {"gene_ids": set(), "gene_symbols": {}})
    # 2. Load TSV file
    df = pd.read_csv(
        tsv_path,
        sep="\t",
        dtype=str,
    ).fillna("")

    rows: list[dict] = df.to_dict("records")
    if not rows:
        print(f"No expression rows in {tsv_path}")
        return

    print(f"rows: {len(rows)}")
    final_struct= {}
    for item in rows:
        key = item.get("Brain region", item.get("Subregion"))
        if key not in final_struct:
            final_struct[key] = {
                "genes": [],
                "embedding": embed(key),
                "source_url": source_url,
            }
        final_struct[key]["genes"].append(item["Gene"])

    final_rows = []
    for k,v in final_struct.items():
        final_rows.append({
            "id": k,
            "embedding": v["embedding"],
            "genes": v["genes"]
        })

    #
    DB.insert(
        table=HPA_TABLE,
        rows=final_rows,
        upsert=True,
        schema=HPA_SCHEMA,
    )
    return DB.row_count(HPA_TABLE)


def ensure_hpa_table():
    """Create and populate the local HPA table when empty."""
    try:
        DB.create_table(HPA_TABLE, schema=HPA_SCHEMA)
        if DB.row_count(HPA_TABLE) > 0:
            return DB.row_count(HPA_TABLE)
        #
        trgt_dir = Path(__file__).resolve().parent.parent.parent / "protein" / "expression"
        if len(list(os.listdir(trgt_dir))) == 0:
            validate_download_expression()
        #
        rows_count = 0
        for item in os.listdir(trgt_dir):
            if item.endswith(".tsv"):
                rows_count += _rows_for_db(
                    os.path.join(trgt_dir, item),
                    HPA_BRAIN_REGION_URL
                )
        print("rows created... done")
    except Exception as e:
        print("Err ensure_hpa_table", e)



def query_hpa_gene_ids(tissue_query: str) -> dict:
    """Return HPA genes for DB rows aligned to the requested brain region."""
    ensure_hpa_table()
    entries: list = get_column(
        DB._con,
        table="HPA",
        columns=[
            "id",
            "embedding",
        ]
    )
    try:
        hpa_unique_tissue_embeds = [
            np.asarray(ast.literal_eval(i[1]))
            for i in entries
        ]

        total_alignment, alignment_matrix = vs(
            tissue_query,
            hpa_unique_tissue_embeds
        )

        #
        match_ids = set()
        for i, item in enumerate(total_alignment):
            if item == 0: # alignment
                match_ids.add(entries[i])

        # get genes
        rows = DB.get_rows(
            HPA_TABLE,
            ids=match_ids,
            select="genes"
        )

        #
        all_genes = set()
        for i in rows:
            all_genes.update(i[0])

        #
        return all_genes
    except Exception as e:
        print("Err query_hpa_gene_ids", e)