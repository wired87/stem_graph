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
from drug_master.types.activity import DrugActivity

chembl_fetcher = ChemblFetcher()

async def infer_effect_drug_trgt(g):
    #
    molecules: list[tuple] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    for mol in molecules:
        trgts = g.get_neighbor_list_rel(
            node=mol[0],
            trgt_rel="target_of",
        )

        #
        activities: list[DrugActivity] = await asyncio.gather(
            *[
                chembl_fetcher.activities_for_molecule_target(
                    molecule_chembl_id=mol[0],
                    target_chembl_id=item[0]
                )
                for item in trgts
            ]
        )

        #
        for nnid, res in zip(trgts, activities):
            # update target node with activities
            g.update_edge(
                src=mol[0],
                trgt=nnid,
                attrs=res
            )


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for infer_effect_drug_trgt.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import asyncio
    from firegraph.graph.local_graph_utils import GUtils

    async def _check_infer_effect_drug_trgt():
        # CHAR: MOLECULE with target_of edge to ChEMBL target — activities_for_molecule_target path.
        g = GUtils()
        g.add_node(attrs=dict(id="CHEMBL25", type="MOLECULE", name="Aspirin"))
        g.add_node(attrs=dict(id="CHEMBL240", type="TARGET", pref_name="COX-1"))
        g.add_edge(
            "CHEMBL25",
            "CHEMBL240",
            attrs=dict(rel="target_of", src_layer="MOLECULE", trgt_layer="TARGET"),
        )
        await infer_effect_drug_trgt(g)
        edge = g.get_edge("CHEMBL25", "CHEMBL240")
        print(f"[__main__] infer_effect_drug_trgt OK  edge_keys={list(edge.keys())[:8]}")

    asyncio.run(_check_infer_effect_drug_trgt())
