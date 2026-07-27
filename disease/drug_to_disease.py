import httpx


async def get_diseases_for_molecules(g):
    """
    Nimmt eine Liste von ChEMBL-Molekül-IDs entgegen, fragt deren Krankheitsindikationen
    gebündelt via Open Targets GraphQL ab und fügt DISEASE-Knoten sowie 'treats'-Kanten
    direkt in die übergebene Gutils-Instanz (g) ein.
    """
    molecule_ids = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
        # cached molecules already carry their DISEASE edges from cache_walk
        and attrs.get("cached") is not True
    ]

    if not molecule_ids:
        print("[get_diseases_for_molecules] no fresh molecules (all cached or none) -> skip")
        return

    url = "https://api.platform.opentargets.org/api/v4/graphql"

    query_parts = []
    for index, mol_id in enumerate(molecule_ids):
        query_parts.append(f"""
            mol_{index}: drug(id: "{mol_id}") {{
                id
                name
                indications {{
                    rows {{
                        disease {{
                            id
                            name
                        }}
                        maxPhaseForIndication
                    }}
                }}
            }}
        """)

    #
    full_query = "query BatchDrugDiseases {\n" + "\n".join(query_parts) + "\n}"

    payload = {"query": full_query}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)

            if response.status_code != 200:
                print(f"[!] Open Targets Batch-Fehler. Status-Code: {response.status_code}")
                return

            data = response.json()
            response_data = data.get("data", {})

            if not response_data:
                return


            for index, mol_id in enumerate(molecule_ids):
                alias_key = f"mol_{index}"
                drug_data = response_data.get(alias_key)

                if not drug_data or not drug_data.get("indications"):
                    continue

                rows = drug_data["indications"].get("rows", [])

                for row in rows:
                    disease_info = row.get("disease", {})
                    disease_id = disease_info.get("id")  # EFO-ID (z.B. EFO_0001071)
                    disease_name = disease_info.get("name")  # Offizieller Name
                    max_phase = row.get("maxPhaseForIndication")

                    if not disease_id:
                        continue

                    #
                    if not g.get_node(disease_id):
                        g.add_node(
                            dict(
                                id=disease_id,
                                type="DISEASE",
                                name=disease_name
                            )
                        )

                    #
                    g.add_edge(
                        src=mol_id,
                        trgt=disease_id,
                        attrs=dict(
                            rel="treats",
                            src_layer="MOLECULE",
                            trgt_layer="DISEASE",
                            max_clinical_phase=max_phase
                        )
                    )

            print(
                f"[+] Batch-Linking beendet. Krankheits-Indikationen für {len(molecule_ids)} Moleküle im Graphen aktualisiert.")

    except Exception as e:
        print(f"[!] Unerwarteter Fehler im Open Targets Batch-Prozess: {e}")


async def enrich_diseases_with_details(g):
    """
    Stufe 2: Nimmt die EFO-IDs, fragt im Batch die tiefen Metadaten
    (Fließtext-Beschreibung, Synonyme, therapeutische Bereiche) ab
    und aktualisiert die Attribute direkt im Graphen.
    """
    efo_ids = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "DISEASE"
    ]

    if not efo_ids:
        print("[enrich_diseases_with_details] no fresh diseases (all cached or none) -> skip")
        return

    url = "https://api.platform.opentargets.org/api/v4/graphql"

    # Dynamischer Aufbau der GraphQL-Batch-Query für detaillierte Krankheitsdaten
    query_parts = []
    for index, efo_id in enumerate(efo_ids):
        query_parts.append(f"""
            dis_{index}: disease(id: "{efo_id}") {{
                id
                name
                description
                synonyms {{
                    hasExactSynonym
                    hasRelatedSynonym
                }}
                therapeuticAreas {{
                    id
                    name
                }}
            }}
        """)

    full_query = "query BatchDiseaseDetails {\n" + "\n".join(query_parts) + "\n}"
    payload = {"query": full_query}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            if response.status_code != 200:
                print(f"[!] Open Targets Enrichment-Fehler. Status-Code: {response.status_code}")
                return

            data = response.json()
            response_data = data.get("data", {})

            if not response_data:
                return

            # Durchlaufe die Ergebnisse und reichere den Graphen an
            for index, parent_efo_id in enumerate(efo_ids):
                alias_key = f"dis_{index}"
                efo_data = response_data.get(alias_key)

                if not efo_data:
                    continue

                # Extrahiere die hochauflösenden Felder der Krankheitsdaten
                description = efo_data.get("description", "Keine Beschreibung verfügbar")

                # Synonyme strukturiert flachklopfen
                syn_struct = efo_data.get("synonyms", {}) or {}
                exact_syns = syn_struct.get("hasExactSynonym", []) or []
                related_syns = syn_struct.get("hasRelatedSynonym", []) or []
                all_synonyms = list(set(exact_syns + related_syns))

                # Therapeutic Areas flachklopfen (z.B. Erlaubt Erkennung von Krebs via EFO_0000616)
                areas = efo_data.get("therapeuticAreas", []) or []
                therapeutic_areas_mapped = [
                    {"id": area.get("id"), "name": area.get("name")} for area in areas if area.get("id")
                ]


                g.add_node(
                    dict(
                        id=parent_efo_id,
                        type="DISEASE",
                        name=efo_data.get("name"),
                        description=description,  # <--- DIE DETAILLIERTE BESCHREIBUNG
                        synonyms=all_synonyms,  # <--- ALLE SYNONYME ALS LISTE
                        therapeutic_areas=therapeutic_areas_mapped  # <--- HIERARCHISCHE KATEGORIEN
                    )
                )

            print(
                f"[+] Stufe 2 beendet: {len(efo_ids)} Krankheits-Knoten erfolgreich mit Detailbeschreibungen angereichert.")

    except Exception as e:
        print(f"[!] Unerwarteter Fehler beim Disease-Enrichment: {e}")

