from tissue.anatomy import get_uberon_anatomy_children
from tissue.get_main_region import search_uberon_region
from tissue.regions import get_major_brain_uberon_regions
from tissue.tissue_descendants import get_uberon_subclasses


async def build_tissue_graph(organ, g):
    result = search_uberon_region(organ)
    tissue_name = get_major_brain_uberon_regions()[result]
    print("UBERON_REGION name identifeid:", tissue_name)
    tissue_nid = result.replace(":", "_")

    #
    g.add_node(
        attrs=dict(
            id=tissue_nid,
            description=tissue_name,
            type="TISSUE",
            sub_type="UBERON",
            embed_key="description",
        )
    )

    #
    await get_uberon_anatomy_children(g, result)
    print("finisehd tissue buildup process...")

async def build_cell_subgraph(g):
    print("Creating hierarchy edges...")
    try:
        tissue_nodes = [nid for nid, attrs in g.G.nodes(data=True) if attrs.get("sub_type") == "anatomy_children"]
        print("request", len(tissue_nodes), "sub components tissue_nodes")

        sub_classes = await asyncio.gather(
            *[
                get_uberon_subclasses(term)
                for term in tissue_nodes
            ]
        )

        for tissue_parent, sub_class_batch in zip(tissue_nodes, sub_classes):
            for subid, description in sub_class_batch.items():
                #print("working UBERON child", )
                if subid.startswith("CL:"):
                    g.add_node(
                        attrs=dict(
                            id=subid,
                            type="CELL",
                            sub_type="sub_class",
                            description=description,
                            embed_key="description",
                        )
                    )

                    g.add_edge(
                        tissue_parent,
                        subid,
                        attrs=dict(
                            rel="includes ",
                            src_layer="TISSUE",
                            trgt_layer="CELL",
                        ),
                    )
    except Exception as e:
        print("Err build ell subgraph:", e)
    print("Done")


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for build_tissue_graph.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import asyncio
    from firegraph.graph.local_graph_utils import GUtils

    async def _check_build_tissue_graph():
        # CHAR: Thalamus resolves via search_uberon_region + OLS children fetch.
        g = GUtils()
        n0 = g.G.number_of_nodes()
        await build_tissue_graph("Thalamus", g)
        n1 = g.G.number_of_nodes()
        tissues = [nid for nid, a in g.G.nodes(data=True) if a.get("type") == "TISSUE"]
        assert n1 > n0, "expected UBERON tissue nodes after build_tissue_graph"
        assert any(a.get("sub_type") == "UBERON" for _, a in g.G.nodes(data=True)), "missing UBERON root"
        print(f"[__main__] build_tissue_graph OK  tissues={len(tissues)} nodes={n1}")

    asyncio.run(_check_build_tissue_graph())
