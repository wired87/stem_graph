import asyncio
from typing import Any, List, Set
import aiohttp

from embedder import similarity
from firegraph.graph.local_graph_utils import GUtils


async def fetch_uniprot_xrefs(session: aiohttp.ClientSession, protein_id: str) -> str:
    """
    Holt die Krankheitsbeschreibungen (Disease Xrefs) für ein Protein von UniProt.
    Fügt Name und Beschreibung der Krankheit zu einem Text-String zusammen.
    """
    url = f"https://rest.uniprot.org/uniprotkb/{protein_id}.json"
    try:
        async with session.get(url) as response:
            if response.status != 200:
                return ""
            data = await response.json()

            disease_texts = []
            comments = data.get("comments", [])
            for comment in comments:
                # UniProt speichert genetische Krankheitsverknüpfungen unter "DISEASE"
                if comment.get("commentType") == "DISEASE":
                    disease_obj = comment.get("disease", {})
                    name = disease_obj.get("diseaseId", "")
                    description = disease_obj.get("description", "")
                    if name or description:
                        disease_texts.append(f"Disease: {name}. Description: {description}")

            return " ".join(disease_texts)
    except Exception as e:
        print(f"Fehler bei UniProt Xref-Fetch für {protein_id}: {e}")
        return ""



async def process_patient_contraindications(
        g: GUtils,
        patient_diseases: List[str],
        embed_fn: Any,
        similarity_threshold: float = 0.90
) -> Any:
    """
    Setzt den biologischen Workflow asynchron um:
    1. Lädt Protein-Knoten aus g.G
    2. Holt parallel UniProt Disease-Xrefs
    3. Berechnet semantische Ähnlichkeit zu den Krankheiten des Patienten
    4. Ermittelt bei Treffern die STRING-Interaktionspartner
    5. Löscht die betroffenen Proteine + STRING-Partner aus dem Graphen.
    """
    # 1. Extrahiere alle PROTEIN Knoten aus dem GUtils Graphen
    protein_nodes = []
    for node_id, node_data in g.G.nodes(data=True):
        if node_data.get("type") == "PROTEIN":
            protein_nodes.append((node_id, node_data))

    if not protein_nodes:
        print("Keine Proteinknoten im Graphen gefunden.")
        return g

    # Erstelle die Embeddings für die Patienten-Krankheiten vorab
    patient_vectors = [embed_fn(disease) for disease in patient_diseases]

    nodes_to_remove: Set[str] = set()
    string_partners_to_fetch: List[str] = []

    # 2. Async-Session starten, um Xrefs parallel abzufragen
    async with aiohttp.ClientSession() as session:
        # Erstelle die Tasks für alle Proteine parallel
        xref_tasks = [fetch_uniprot_xrefs(session, node_id) for node_id, _ in protein_nodes]
        xref_results = await asyncio.gather(*xref_tasks)

        # 3. Semantische Ähnlichkeit prüfen
        for (node_id, node_data), xref_text in zip(protein_nodes, xref_results):
            if not xref_text:
                continue

            # Generiere Vektor für die Krankheitsbeschreibung des Proteins
            protein_disease_vector = embed_fn(xref_text)

            # Vergleiche mit jeder Krankheit des Patienten
            is_match = False
            for p_vector in patient_vectors:
                score = similarity(p_vector, protein_disease_vector)
                if score >= similarity_threshold:
                    is_match = True
                    break

            if is_match:
                print(self_msg := f"Match gefunden! Protein {node_id} korreliert mit Patientenprofil.")
                nodes_to_remove.add(node_id)
                string_partners_to_fetch.append(node_id)

        # 4. (Maybe?) STRING-Interaktionspartner für die Treffer holen
        if string_partners_to_fetch:
            print(f"Hole STRING-Interaktionspartner für {len(string_partners_to_fetch)} Risiko-Proteine...")
            string_tasks = [fetch_string_partners(session, p_id) for p_id in string_partners_to_fetch]
            string_results = await asyncio.gather(*string_tasks)

            for partners in string_results:
                for partner in partners:
                    # Wir fügen die Partner zur Löschliste hinzu, sofern sie im Graphen existieren
                    if partner in g.G:
                        nodes_to_remove.add(partner)



    # 5. Knoten final aus dem NetworkX Graphen entfernen
    if nodes_to_remove:
        print(f"Entferne insgesamt {len(nodes_to_remove)} Knoten (Proteine + STRING-Partner) aus dem Graphen.")
        g.G.remove_nodes_from(list(nodes_to_remove))
    else:
        print("Keine kritischen Proteinknoten zum Löschen gefunden.")
    print("disease process finished")
    return g




