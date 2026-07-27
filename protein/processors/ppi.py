"""
string_db -- STRING protein-interaction enrichment processor.

User prompt (Cursor session):
    "use a unified class for all web request core infrastructure.
     (schema as gotermfetcher but adaptable to all types of data)
     keep specific processors rely in the current corresponding files."

The HTTP core is expressed as ``StringDbFetcher`` (a thin
``AsyncApiFetcher`` subclass); the graph-construction processor
``create_interaction_process`` stays in this file.
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

import httpx

from core.app_utils import AsyncApiFetcher
from firegraph.graph.local_graph_utils import GUtils


# Unified STRING-DB fetcher -- only declares the endpoint and method shape.
class StringDbFetcher(AsyncApiFetcher):
    BASE_URL = "https://string-db.org/api/json/network"

    async def network(self, identifiers: str, species: int = 9606):
        """Fetch the STRING interaction network for one (or pipe-joined) protein id(s)."""
        # 9606 = Homo sapiens; keep params simple so the base class signs them
        params = {"identifiers": identifiers, "species": species}
        try:
            return await self._execute_get(self.BASE_URL, params=params)
        except Exception as e:
            print("Error fetching STRING network: ", e)
            return []

# module-level singleton: one shared semaphore across all callers
_STRING_FETCHER = StringDbFetcher()




import httpx

_OMNIPATH_URL = (
    "https://omnipathdb.org/interactions"
)


async def get_string_graph(
    protein: str,
):
    return await _STRING_FETCHER.network(
        protein
    )


async def get_omnipath_graph(
    proteins: list[str],
):
    #
    params = dict(
        datasets="omnipath",
        fields=",".join(
            [
                "is_directed",
                "is_stimulation",
                "is_inhibition",
                "consensus_direction",
                "consensus_stimulation",
                "consensus_inhibition",
                "sources",
                "references",
            ]
        ),
        format="json",
    )

    async with httpx.AsyncClient(
        timeout=120,
    ) as client:

        response = await client.get(
            _OMNIPATH_URL,
        )

        response.raise_for_status()

        rows = response.json()

    proteins = set(proteins)

    interaction_map = {}

    for row in rows:
        print("row", row)
        src = row.get("source")
        trgt = row.get("target")

        if src not in proteins:
            continue

        if trgt not in proteins:
            continue

        interaction_map[
            (src, trgt)
        ] = row

    return interaction_map


def build_interaction_type(
    op_row: dict,
):
    if not op_row:
        return "unknown"

    if op_row.get(
        "consensus_stimulation"
    ):
        return "stimulation"

    if op_row.get(
        "consensus_inhibition"
    ):
        return "inhibition"

    if op_row.get(
        "consensus_direction"
    ):
        return "directed"

    return "unknown"


def load_interaction_graph(
    g: GUtils,
    string_rows: list[dict],
    omnipath_map: dict,
    ion_channel_anchestor: bool,
    min_score: float = 0.7,
):
    parent = ["PROTEIN"]

    if ion_channel_anchestor:
        parent.append(
            "ION_CHANNEL"
        )

    for e in string_rows:

        score = float(
            e.get("score", 0)
        )

        if score < min_score:
            continue

        a = e["preferredName_A"]
        b = e["preferredName_B"]

        #
        if not g.get_node(a):

            g.add_node(
                dict(
                    id=a,
                    type="PROTEIN",
                    sub_type="PURE_INFLUENCE",
                    parent=parent,
                )
            )

        #
        if not g.get_node(b):
            g.add_node(
                dict(
                    id=b,
                    type="PROTEIN",
                    sub_type="PURE_INFLUENCE",
                    parent=parent,
                )
            )

        #
        op = omnipath_map.get(
            (a, b),
            {},
        )

        influence_type = (
            build_interaction_type(op)
        )

        #
        g.add_edge(
            a,
            b,
            attrs=dict(
                rel="interacts_with",
                src_layer="PROTEIN",
                trgt_layer="PROTEIN",

                string_score=score,

                influence_type=(
                    influence_type
                ),

                omnipath_directed=op.get(
                    "is_directed"
                ),

                omnipath_stimulation=op.get(
                    "is_stimulation"
                ),

                omnipath_inhibition=op.get(
                    "is_inhibition"
                ),

                consensus_direction=op.get(
                    "consensus_direction"
                ),

                consensus_stimulation=op.get(
                    "consensus_stimulation"
                ),

                consensus_inhibition=op.get(
                    "consensus_inhibition"
                ),
            ),
        )
    print("interaction added")


async def create_interaction_process(
    g: GUtils,
):
    print(
        "create_interaction_process..."
    )

    protein_ids = [
        nid
        for nid, attrs
        in g.G.nodes(data=True)
        if attrs.get("type")
        == "PROTEIN"
    ]

    #
    omnipath_map = (
        await get_omnipath_graph(
            protein_ids
        )
    )

    #
    string_tasks = [
        get_string_graph(
            protein
        )
        for protein
        in protein_ids
    ]

    #
    string_results = (
        await asyncio.gather(
            *string_tasks
        )
    )

    #
    for rows in string_results:

        load_interaction_graph(
            g=g,
            string_rows=rows,
            omnipath_map=omnipath_map,
            ion_channel_anchestor=True,
        )

    g.print_status_G()

    print(
        "create_interaction_process... done"
    )


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for create_interaction_process.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import asyncio
    from firegraph.graph.local_graph_utils import GUtils

    async def _check_create_interaction_process():
        # CHAR: multiple PROTEIN seeds — exercises Omnipath + STRING gather per protein.
        g = GUtils()
        for pid, name in (("P35498", "SCN1A"), ("P08172", "CHRM2"), ("Q12879", "CACNA1A")):
            g.add_node(attrs=dict(id=pid, type="PROTEIN", name=name))
        n0, e0 = g.G.number_of_nodes(), g.G.number_of_edges()
        await create_interaction_process(g)
        ppi = [
            a for _, _, a in g.G.edges(data=True) if a.get("rel") == "interacts_with"
        ]
        print(
            f"[__main__] create_interaction_process OK  "
            f"nodes+={g.G.number_of_nodes()-n0} ppi_edges={len(ppi)} total_edges={g.G.number_of_edges()}"
        )

    asyncio.run(_check_create_interaction_process())



"""
async def create_string_interaction_process(g):

    async def get_string_graph(protein):
        print("get_string_graph for ", protein, " ...")
        # delegate the whole HTTP round-trip to the unified fetcher
        return await _STRING_FETCHER.network(protein)


    def load_string_graph(g: GUtils, item, ion_channel_anchestor:bool, min_score=0.7):
        print("working STRING...")

        # handle aprent
        parent = ["PROTEIN"]
        if ion_channel_anchestor:
            parent.append("ION_CHANNEL")

        for e in item:
            if e.get("score", 0) < min_score:
                continue

            a = e["preferredName_A"]
            b = e["preferredName_B"]

            # add nodes
            if not g.get_node(a):
                g.add_node(
                    dict(
                        id=a,
                        type="PROTEIN",
                        sub_type="PURE_INFLUENCE",
                        parent=parent
                    )
                )
            if not g.get_node(b):
                g.add_node(
                    dict(
                        id=b,
                        type="PROTEIN",
                        sub_type="PURE_INFLUENCE",
                        parent=parent
                    )
                )

            # add edge
            g.add_edge(
                a,
                b,
                attrs=dict(
                    rel="interacts_with",
                    src_layer="",
                    trgt_layer="PROTEIN",
                )
            )
        print("interaction added")
        return g

    get_graph_tasks = []
    protein_keys = []
    for key, data in g.G.nodes(data=True):
        if data.get("type") == "PROTEIN":
            protein_keys.append(key)
            get_graph_tasks.append(get_string_graph(key))

    await get_omnipath_interactions(protein_keys)

    protein_graph = await asyncio.gather(*get_graph_tasks)

    for item in protein_graph:
        load_string_graph(
            g=g,
            item=item,
            ion_channel_anchestor=True
        )

    g.print_status_G()
    print("get_human_entries... done")
    
    


###

create a py def whch receives all drugs from the graph -> for each get neighbor poteins -> receive edge  -> for each edge receive schame data struct:         "interactionId": 84194,

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



validate all diferent kids of "type"-attr to set specific behaviour or all kinds of omnipath for a further calculation.



receive then for each protein, all its neghbor ndoes and extract from its edges the specific omnipath interaction values (edge schema written above in our chat) to perfom a calculation start with all of the given values within the start protien with schema: XXX 

the resulting value must be the applied to all edges between single proteins

    
"""