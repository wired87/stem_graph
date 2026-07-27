import asyncio
import sys
from pathlib import Path

# CHAR: repo root on sys.path when this file is run as a script.
for _p in Path(__file__).resolve().parents:
    if (_p / "core").is_dir() and (_p / "embedder").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

from drug_master.chembl_drug_to_pcy_ligand import chembl_to_ligand_ids
from drug_master.drug import ChemblFetcher
from drug_master.drug_trgt_mechanism import MechanismResponse
from drug_master.pharmacology_trgt_id import uniprot_to_pharmacology_target_ids
from drug_master.set_interaction_type_drug_trgt import get_ligand_target_interactions
chembl_fetcher = ChemblFetcher()

async def set_drug_mechanism(g):
    molecules: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    # RECEIVE MECHANSIMS
    mechanism:MechanismResponse = await asyncio.gather(
        *[
            chembl_fetcher.mechanisms_for_molecule(
                molecule_chembl_id=mol,
            )
            for mol in molecules
        ]
    )

    # UPDATE EDGE DRUG -> TRGT with mechanism
    for mol, res in zip(molecules, mechanism):
        print("mechanism", mechanism)

        for mec in res["mechanisms"]:
            print("work mechansim", mec["mec_id"])
            existing_mech = g.get_node(nid=mec["mec_id"])
            print("existing_mech", existing_mech)

            print("add mechanism", mec["mec_id"])
            g.add_node(
                dict(
                    id=mec["mec_id"],
                    type="MECHANISM",
                    **mec
                )
            )

            # update target node with activities
            g.add_edge(
                mol,
                mec["mec_id"],
                attrs={
                    "rel": "has_mechanism",
                    "src_layer": "MOLECULE",
                    "trgt_layer": "MECHANISM",
                },
            )

    #
    print("mechansism process finished...")



async def classify_interaction_type_drug_trgt_gtpcy(g):
    # e.g. antagonist
    molecules: list[tuple] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    # molecule -> ligand
    ligand_ids = await chembl_to_ligand_ids([item[0] for item in molecules])

    # update node with ligand
    for lid, item in zip(ligand_ids, molecules):
        g.update_node(dict(id=item[0], ligand_id=lid))



    proteins: list[tuple] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
    ]


    # gtop does not accept chmbl trgt ids
    pharmacology_target_ids = await uniprot_to_pharmacology_target_ids(
        uniprot_accessions=[item[0] for item in proteins]
    )

    # update node with ligand
    for trgt_pcy_id, item in zip(
            pharmacology_target_ids,
            proteins,
    ):
        # get parent trgt -> update ndoe


        g.update_node(dict(
            id=item[0],
            trgt_pcy_id=trgt_pcy_id
        ))

    targets_for_ligands = [
        [(nid, attrs["trgt_pcy_id"]) for nid, attrs in g.get_neighbor_list(
            node=lid,
            target_type="PROTEIN",
        )]
        for lid in ligand_ids
    ]

    # get ligand trgt interaction
    results = await asyncio.gather(
        *[
            get_ligand_target_interactions(
                ligand_id=int(lid),
                target_ids=item,
            )
            for item, lid in zip(
                [[j[1] for j in i] for i in targets_for_ligands],
                ligand_ids
            )
        ]
    )

    # update edge
    for i, (lig, res_batch, ligands_trgt_batch) in enumerate(
            zip(ligand_ids, results, targets_for_ligands)
    ):
        for res_item, trgt_id in zip(res_batch, [[j[0] for j in i] for i in targets_for_ligands]):
            """
            "interactionId": 84194,
            "targetId": 290,
            "targetName": "mGlu<sub>2</sub> receptor",
            "ligandAsTargetId": 0,
            "targetSpecies": "Human",
            "primaryTarget": false,
            "targetBindingSite": "",
            "ligandId": 1369,
            "ligandName": "L-glutamic acid",
            "ligandContext": "",
            "endogenous": true,
            "type": "Agonist",
            "action": "Agonist",
            "actionComment": "",
            "selectivity": "Not Determined",
            "concentrationRange": "",
            "affinity": "4.7 - 5.4",
            "affinityParameter": "pEC50",
            "originalAffinity": "",
            "originalAffinityType": "",
            "originalAffinityRelation": "=",
            "assayDescription": "",
            "assayConditions": "",
            "useDependent": false,
            "voltageDependent": false,
            "voltage": "",
            "physiologicalVoltag
            
            """
            # UPDATE TARGET NODE
            g.update_node(
                src=lig,
                trgt=trgt_id,
                **res_item,
            )
    print("interaction type infered... done")


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for set_drug_mechanism.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import asyncio
    from firegraph.graph.local_graph_utils import GUtils

    async def _check_set_drug_mechanism():
        # CHAR: real ChEMBL molecule id — exercises mechanisms_for_molecule API path.
        g = GUtils()
        g.add_node(attrs=dict(id="CHEMBL25", type="MOLECULE", name="Aspirin"))
        g.add_node(attrs=dict(id="CHEMBL1200982", type="MOLECULE", name="Metformin"))
        n0 = g.G.number_of_nodes()
        await set_drug_mechanism(g)
        mechs = [nid for nid, a in g.G.nodes(data=True) if a.get("type") == "MECHANISM"]
        mech_edges = [
            a for _, _, a in g.G.edges(data=True) if a.get("rel") == "has_mechanism"
        ]
        print(
            f"[__main__] set_drug_mechanism OK  "
            f"mechanisms={len(mechs)} edges={len(mech_edges)} nodes+={g.G.number_of_nodes()-n0}"
        )

    asyncio.run(_check_set_drug_mechanism())