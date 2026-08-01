"""
ds — project-wide static datasets and shared physical-filter vocabulary.

Prompt: avoid circular imports by storing hardcoded variables (of the entire project)
within this module at the project root.

Prompt: analyze ``filter_physical_compound`` (``str`` or token list), classify tokens
against ``PHYSICAL_CATEGORY_ALIASES`` keys, and expose canonical slot names for
``query_pipe`` and ``UniprotKB`` gating.

CHAR: keep this module free of imports from ``data.*`` or ``query_pipe`` so ``ds`` stays
the acyclic leaf every consumer can import safely.
"""
from __future__ import annotations

import json
import os
import httpx
import requests

from embedder import embed
import re
from firegraph._db.manager import DBManager
import dotenv

dotenv.load_dotenv()


_TISSLIST_URL = "https://www.uniprot.org/docs/tisslist.txt"
_UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
_PUBCHEM_COMPOUND = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/JSON"

_HTTP_TIMEOUT = 30
_UNIPROT_FIELDS = "accession,protein_name,gene_names,cc_function,go,cc_disease,cc_tissue_specificity"
_MAX_PROTEINS_PER_ORGAN = 50




def cleanup_key_entries(value: str | list[str] | None) -> list[str]:
    """
    Normalize ``filter_physical_compound`` input into raw string tokens (not yet alias-resolved).

    Accepts a comma/semicolon/pipe-separated string or a list of fragments; list elements
    may themselves contain separators.
    """
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return []
        parts = re.split(r"[,;|]+", cleaned)
        return [p.strip() for p in parts if p.strip()]
    out: list[str] = []
    for x in value:
        if x is None:
            continue
        s = str(x).strip()
        if not s:
            continue
        if re.search(r"[,;|]", s):
            out.extend(cleanup_key_entries(s))
        else:
            out.append(s)
    return out




async def get_protein_sequence(protein: str, client: httpx.AsyncClient):
    """
    Fetch protein sequence from UniProt by gene/protein name.
    Returns: str | None
    """
    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {
        "query": f"gene:{protein} AND organism_id:9606",
        "format": "json",
        "size": 1
    }

    try:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

        results = data.get("results", [])
        if not results:
            return None
        return protein, results#[0]["sequence"]["value"]

    except Exception as e:
        print(f"Error fetching UniProt sequence for {protein}: {e}")
        return None








def parse_uniprot_flatfile(data_string):
    print("[*] Starte Parsing der UniProt Daten...")
    entries = []
    # Splitte den String in einzelne Blöcke basierend auf dem Trenner //
    raw_entries = data_string.strip().split('//')

    for i, raw_entry in enumerate(raw_entries):
        print("work pentry", i)
        if not raw_entry.strip():
            print("entry is none -> contine")
            continue

        entry_dict = {
            "id": None,
            "accession": None,
            "description": "",
            "organism": "",
            "sequence": "",
            "length": None
        }

        lines = raw_entry.strip().split('\n')
        capture_sequence = False

        for line in lines:
            line = line.strip()

            # ID: Identifier und Länge
            if line.startswith('ID'):
                parts = line.split()
                entry_dict["id"] = parts[1]
                entry_dict["length"] = parts[3]

            # AC: Accession Number
            elif line.startswith('AC'):
                entry_dict["accession"] = line.replace('AC', '').replace(';', '').strip()

            # DE: Description (Name des Proteins)
            elif line.startswith('DE'):
                entry_dict["description"] += line.replace('DE', '').strip() + " "

            # OS: Organism Source
            elif line.startswith('OS'):
                entry_dict["organism"] += line.replace('OS', '').strip() + " "

            # SQ: Start der Sequenz-Sektion
            elif line.startswith('SQ'):
                capture_sequence = True
                continue

            # Sequenz-Daten auslesen (Zeilen nach SQ, die eingerückt sind)
            elif capture_sequence:
                # Entferne Leerzeichen und Zahlen aus der Sequenzzeile
                clean_seq = re.sub(r'[\d\s]', '', line)
                entry_dict["sequence"] += clean_seq

        # Cleanup der Texte
        entry_dict["description"] = entry_dict["description"].strip()
        entry_dict["organism"] = entry_dict["organism"].strip()
        entries.append(entry_dict)
        print(f"[OK] Eintrag geladen: {entry_dict['id']}")

    print(f"[FINISHED] Insgesamt {len(entries)} Einträge konvertiert.")
    return entries

def get_data():
    if os.getenv("LOCAL_DATA", None) is not None:

        def embed_protein_fun(results):
            for r in results:
                protein_function = get_p_fun(r)
                embedding = embed(protein_function)
                r["embedding"] = embedding
            return results

        url = "https://rest.uniprot.org/uniprotkb/stream"
        params = {
            "query": "organism_id:9606",  # syn:32630
            "format": "json",
        }
        r = requests.get(url, params=params, stream=True, timeout=990)
        r.raise_for_status()
        data = r.json()
        results = embed_protein_fun(data["results"])
    else:
        print("Fetch sprot data lcoal...")
        results = parse_uniprot_flatfile(open("_db/uniprot_sprot.dat", "r").read())
        for entry in results:
            entry["embedding"] = embed(entry["description"])
    return results



async def _fetch_organ_annotations(organs: list[str]) -> list[str]:
    """Query UniProt REST per organ → aggregate functional annotation strings."""
    annotations: list[str] = []
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        for organ in organs:
            query = f'(cc_tissue_specificity:"{organ}") AND (reviewed:true) AND (organism_id:9606)'
            params = {
                "query": query,
                "fields": _UNIPROT_FIELDS,
                "format": "json",
                "size": str(500),
            }
            try:
                r = await client.get(_UNIPROT_SEARCH, params=params)
                r.raise_for_status()
                data = r.json()
            except (httpx.HTTPError, json.JSONDecodeError):
                continue

            for entry in data.get("results", []):
                acc = entry.get("primaryAccession", "?")
                pname = ""
                rec = entry.get("proteinDescription", {}).get("recommendedName")
                if rec:
                    pname = rec.get("fullName", {}).get("value", "")

                genes = ", ".join(
                    g.get("geneName", {}).get("value", "")
                    for g in entry.get("genes", [])
                    if g.get("geneName")
                )

                funcs = []
                for comment in entry.get("comments", []):
                    if comment.get("commentType") == "FUNCTION":
                        for txt in comment.get("texts", []):
                            funcs.append(txt.get("value", ""))

                go_terms = []
                for xref in entry.get("uniProtKBCrossReferences", []):
                    if xref.get("database") == "GO":
                        props = {p["key"]: p["value"] for p in xref.get("properties", [])}
                        go_terms.append(props.get("GoTerm", xref.get("id", "")))

                diseases = []
                for comment in entry.get("comments", []):
                    if comment.get("commentType") == "DISEASE":
                        dis = comment.get("disease", {})
                        if dis.get("diseaseId"):
                            diseases.append(dis["diseaseId"])

                line = (
                    f"[{acc}] {pname} | genes={genes} | "
                    f"function={'; '.join(funcs)} | "
                    f"GO={'; '.join(go_terms[:10])} | "
                    f"disease={'; '.join(diseases)}"
                )
                annotations.append(line)

    return annotations






def get_human_entries(prompt) -> dict[str, list[float]]:
    db = get_db_manager()

    # check duck db status
    if db.row_count("PROTEIN") == 0:
        print("read human entries...")
        results = get_data()
        print("results extracted...")
        # save
        db.insert(table="PROTEIN", rows=results)
        print("db insert")
    return db.get_rows(table_name="PROTEIN", select="primaryAccession, embedding")



def get_p_fun(entry) -> str:
    functions = []
    for c in entry.get("comments", []):
        if c.get("commentType") == "FUNCTION":
            for t in c.get("texts", []):
                if t.get("value"):
                    functions.append(t["value"][:500])
    return " | ".join(functions)





if __name__ == "__main__":
    print("done")


