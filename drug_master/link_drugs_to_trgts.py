"""
link_drugs_to_trgts -- map MOLECULE graph nodes back onto PROTEIN targets.

User prompt (Cursor session):
    "use a unified class for all web request core infrastructure.
     (schema as gotermfetcher but adaptable to all types of data)
     keep specific processors rely in the current corresponding files."

The HTTP core for every ChEMBL call (target / molecule / activity) comes
from the shared ``ChemblFetcher`` defined in ``drug.py``. This file keeps
only the graph-construction processor.
"""

import asyncio
import sys
from pathlib import Path

# CHAR: repo root on sys.path when this file is run as a script.
for _p in Path(__file__).resolve().parents:
    if (_p / "core").is_dir() and (_p / "embedder").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

from drug_master.drug import ChemblFetcher

_CHEMBL = ChemblFetcher()

async def fetch_target_details(target_id: str) -> str:
    """Holt die Details zu einem spezifischen Target asynchron direkt über die REST-API."""
    try:
        return await _CHEMBL.target_details(target_id)
    except Exception as e:
        print(f"Fehler beim Abruf von Target {target_id}: {e}")
        return target_id


async def link_drug_targets_to_protein(g) -> list:
    print("link_drug_targets_to_protein...")
    drug_ids = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]
    print("drug ids received", len(drug_ids))


    if not drug_ids:
        print("no drug nodes — skip target linking")
        return []

    async def get_drugs_molecules(drug_name):
        try:
            # delegate to the unified fetcher; extract the molecules list
            data = await _CHEMBL.molecule_by_name(drug_name)
            return data["molecules"]
        except Exception as e:
            print(f"Fehler beim Abruf der ChEMBL molecules für {drug_name}: {e}")
            return []


    molecules = await asyncio.gather(*[
        get_drugs_molecules(did)
        for did in drug_ids
    ])

    for mol_batch, did in zip(molecules, drug_ids):
        tasks = []
        for item in mol_batch:
            print("item", item)
            # all ChEMBL activity queries go through the same fetcher so the
            # connection pool + semaphore is shared across the gather()
            tasks.append(_CHEMBL.activities_for_molecule(item["molecule_chembl_id"]))

        activities = await asyncio.gather(*tasks)
        print("molecule interacts with:", activities)

        for item in activities:
            g.add_node(
                dict(**item, type="MOLECULE")
            )

            # MOLECULE -> INTERCTANT MOLECULE
            g.add_edge(
                src=did,
                trgt=item["molecule_chembl_id"],
                attrs=dict(
                    rel="activity_molecule_interactant",
                    src_layer="MOLECULE",
                    trgt_layer="MOLECULE",
                )
            )

        #
        target_ids = list({
            act["target_chembl_id"]
            for act in activities
        })



async def get_drug_targets(g):
    """
    link drugs -> targets -> compoents (proteins)
    """
    print("get targets by drug")
    molids: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    for molid in molids:
        mechs = g.get_neighbor_list(
            node=molid,
            target_type="MECHANISM"
        )

        #
        for mech_id, mech_attrs in mechs.items():
            tasks = [
                _CHEMBL.target_details(mec["target_chembl_id"])
                for mec in mechs
            ]
            target_responses = await asyncio.gather(*tasks)

            # ADD RESULTS
            for trgt in target_responses:
                target_id = trgt["target_chembl_id"]

                components = trgt.get("target_components", [])

                # targets can be groups of proteins
                g.add_node(
                    dict(
                        id=target_id,
                        type="TARGET",
                        **{k:v for k,v in trgt.items() if k not in [
                            "target_components",
                            "target_chembl_id",
                        ]}
                    )
                )

                # TRGT MOLECULE -> TARGET
                g.add_edge(
                    src=mech_id,
                    trgt=target_id,
                    attrs=dict(
                        rel="target_of",
                        src_layer="MOLECULE",
                        trgt_layer="TARGET",
                    )
                )

                for component in components:
                    # Double-check that the component actually represents a protein
                    if component.get("component_type") == "PROTEIN":
                        uniprot_acc = component.get("accession")

                        # Skip if accession is missing in this component entry
                        if not uniprot_acc:
                            continue

                        # Create the PROTEIN node if it does not exist in the graph yet
                        if not g.get_node(uniprot_acc):
                            g.add_node(
                                dict(
                                    id=uniprot_acc,
                                    type="PROTEIN",
                                    # trt_chembl id need for set_mechanism_drug_trgt
                                )
                            )

                        # TRGT PROTEIN -> CAUSE MOLECULE
                        g.add_edge(
                            src=uniprot_acc,
                            trgt=target_id,
                            attrs=dict(
                                rel="target_component_of",
                                src_layer="TARGET",
                                trgt_layer="PROTEIN",
                            )
                        )
    print("validate drug interactions... done")


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for get_drug_targets.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import asyncio
    from firegraph.graph.local_graph_utils import GUtils

    async def _check_get_drug_targets():
        # CHAR: MOLECULE + MECHANISM nodes — target_details + PROTEIN component path.
        g = GUtils()
        g.add_node(attrs=dict(id="CHEMBL25", type="MOLECULE", name="Aspirin"))
        g.add_node(
            attrs=dict(
                id="MEC_CHEMBL25_1",
                type="MECHANISM",
                mec_id="MEC_CHEMBL25_1",
                target_chembl_id="CHEMBL240",
                mechanism_of_action="INHIBITOR",
            )
        )
        g.add_edge(
            "CHEMBL25",
            "MEC_CHEMBL25_1",
            attrs=dict(rel="has_mechanism", src_layer="MOLECULE", trgt_layer="MECHANISM"),
        )
        n0 = g.G.number_of_nodes()
        await get_drug_targets(g)
        targets = [nid for nid, a in g.G.nodes(data=True) if a.get("type") == "TARGET"]
        proteins = [nid for nid, a in g.G.nodes(data=True) if a.get("type") == "PROTEIN"]
        print(
            f"[__main__] get_drug_targets OK  "
            f"targets={len(targets)} proteins={len(proteins)} nodes+={g.G.number_of_nodes()-n0}"
        )

    asyncio.run(_check_get_drug_targets())




