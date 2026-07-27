import urllib.parse
from typing import Any

from core.app_utils import AsyncApiFetcher
from firegraph.graph.local_graph_utils import GUtils
from goterm.term_details import term_details

_DETAILS_SEEN: set[str] = set()
_CAM_SEEN: set[str] = set()


def _node_has_text(g, goid: str) -> bool:
    """True when the graph already carries the textual metadata for ``goid``."""
    # lookup once, fall back to falsy if missing
    node = g.get_node(goid)
    return bool(node and node.get("text"))

class GoApiFetcher(AsyncApiFetcher):
    """GO API fetcher -- thin endpoint layer over ``AsyncApiFetcher``.

    The base class owns rate limiting, error handling and JSON parsing
    (formerly duplicated as ``_execute_get`` + ``RATE_LIMITER`` here).
    """

    BASE_URL = "https://api.geneontology.cloud"

    async def get_term_hierarchy(self, goid: str) -> Any:
        """Holt die hierarchischen Beziehungen (Parents/Children) eines GO-Terms."""
        clean_id = goid.strip().replace(":", "_").split("/")[-1]
        url = f"{self.BASE_URL}/go/{clean_id}/hierarchy"
        return await self._execute_get(url)

    async def get_cam_pathway(self, go_term: str) -> Any:
        """Holt alle verknüpften GO-CAM Modell-IDs für einen spezifischen GO-Term."""
        clean_id = go_term.strip().split("/")[-1]
        url = f"{self.BASE_URL}/go/{clean_id}/models"
        return await self._execute_get(url)

    async def get_cam_detailed(self, go_cam: str) -> Any:
        """
        Holt die detaillierten Informationen (goids, goclasses) eines GO-CAM Modells.
        Nutzt URL-Encoding, um Probleme mit Slashes in Modell-URIs zu vermeiden.
        """
        clean_cam = []
        if isinstance(go_cam, str):
            clean_cam = [go_cam]
        elif isinstance(go_cam, list):
            for c in go_cam:
                clean_cam = c.strip()
        joined_cams = ",".join(clean_cam)
        encoded_cam = urllib.parse.quote(joined_cams, safe="")
        url = f"{self.BASE_URL}/models/go?gocams={encoded_cam}"
        return await self._execute_get(url)

    async def get_term_details(self, term: str) -> Any:
        """Holt die Kern-Metadaten (Label, Definition, Synonyms) eines GO-Terms."""
        clean_id = term.strip().split("/")[-1]
        url = f"{self.BASE_URL}/go/{clean_id}"
        return await self._execute_get(url)









def get_terms(g):
    # start marker
    print("[get_terms] start")
    go_terms = []
    for k, v in g.G.nodes(data=True):
        if v.get("type") == "GO_TERM" and "id" in v:
            go_terms.append(k)
    # end marker with count so callers can correlate cost
    print(f"[get_terms] done (count={len(go_terms)})")
    return go_terms


def extract_proteins_goterms(
    g,
    protein_id: str,
    protein_entry: dict,
):
    for xref in protein_entry.get("uniProtKBCrossReferences", []):
        # keep only GO entries
        if xref.get("database") != "GO":
            continue

        go_id = xref.get("id")

        if not go_id:
            continue

        # build optional text
        properties = {
            p.get("key"): p.get("value")
            for p in xref.get("properties", [])
        }

        go_text = properties.get("GoTerm", "")

        # GO node
        g.add_node(
            attrs=dict(
                id=go_id,
                type="GO_TERM",
                text=go_text,
                embed_key="text",
            )
        )

        # GO -> PROTEIN
        g.add_edge(
            go_id,
            protein_id,
            attrs=dict(
                rel="annotates",
                src_layer="GO_TERM",
                trgt_layer="PROTEIN",
            )
        )
    print(f"Added GO terms for protein {protein_id}")

async def go_term_by_protein(g):
    print("[go_term_by_protein] start")
    proteins = [
        (key, attrs)
        for key, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
    ]

    # INCLUDE RAW TERMS -> PROTEIN
    for pid, attrs in proteins:
        extract_proteins_goterms(
            g,
            protein_id=pid,
            protein_entry=attrs,
        )

    await go_term_graph(g)
    count = [nid for nid, attrs in g.G.nodes(data=True) if attrs.get("type") == "GO_TERM"]
    print("goterms extracted:", len(count))





async def go_term_graph(g: GUtils) -> None:
    print("[go_term_graph] start...")
    fetcher = GoApiFetcher()
    go_terms = get_terms(g)
    await term_details(fetcher, go_terms, g)
    print("[go_term_graph] done")
