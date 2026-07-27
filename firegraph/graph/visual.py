import os
import sys
import networkx as nx
from   pyvis.network import Network

# ── Code-structure node styles ───────────────────────────────────────────────
_NODE_STYLES = {
    "MODULE":    {"color": "#4a90d9", "shape": "box",     "size": 28},
    "CLASS":     {"color": "#7b68ee", "shape": "diamond", "size": 24},
    "METHOD":    {"color": "#50c878", "shape": "dot",     "size": 18},
    "PARAM":     {"color": "#f0e68c", "shape": "triangle","size": 14},
    "CLASS_VAR": {"color": "#daa520", "shape": "star",    "size": 16},
    "FOLDER":    {"color": "#20b2aa", "shape": "box",     "size": 22},
    "TECHNIQUE": {"color": "#e74c3c", "shape": "hexagon", "size": 20},
}

# ── Biological / UniprotKB node styles ───────────────────────────────────────
# Each type gets a distinct hue that stays readable on the dark canvas (#1a1a2e).
_BIO_NODE_STYLES: dict[str, dict] = {
    "PROTEIN":              {"color": "#e74c3c", "shape": "dot",      "size": 22},
    "GENE":                 {"color": "#3498db", "shape": "diamond",  "size": 20},
    "GO_TERM":              {"color": "#2ecc71", "shape": "square",   "size": 16},
    "DISEASE":              {"color": "#e67e22", "shape": "triangle", "size": 20},
    "REACTOME_PATHWAY":     {"color": "#9b59b6", "shape": "hexagon",  "size": 22},
    "TISSUE":               {"color": "#1abc9c", "shape": "dot",      "size": 15},
    "CELL_TYPE":            {"color": "#f39c12", "shape": "dot",      "size": 15},
    "FOOD_SOURCE":          {"color": "#27ae60", "shape": "star",     "size": 16},
    "ALLERGEN":             {"color": "#c0392b", "shape": "triangle", "size": 18},
    "PROTEIN_DOMAIN":       {"color": "#8e44ad", "shape": "box",      "size": 16},
    "COMPARTMENT":          {"color": "#16a085", "shape": "ellipse",  "size": 16},
    "PHARMA_COMPOUND":      {"color": "#d35400", "shape": "diamond",  "size": 16},
    "CLINICAL_ANNOTATION":  {"color": "#c0392b", "shape": "square",   "size": 14},
    "GENETIC_VARIANT":      {"color": "#e84c3c", "shape": "triangle", "size": 14},
    "BIOELECTRIC_STATE":    {"color": "#00b5d8", "shape": "dot",      "size": 16},
    "CELL_STATE":           {"color": "#f1c40f", "shape": "dot",      "size": 14},
    "TISSUE_STATE":         {"color": "#2980b9", "shape": "dot",      "size": 14},
    "ORGAN":                {"color": "#e91e63", "shape": "box",      "size": 22},
    "ORGAN_STATE":          {"color": "#880e4f", "shape": "dot",      "size": 14},
    "VMH_METABOLITE":       {"color": "#4caf50", "shape": "dot",      "size": 14},
    "MICROBIAL_STRAIN":     {"color": "#795548", "shape": "dot",      "size": 14},
    "ECO_EVIDENCE":         {"color": "#607d8b", "shape": "square",   "size": 12},
    "MOLECULE_CHAIN":       {"color": "#00acc1", "shape": "dot",      "size": 14},
    "MINERAL":              {"color": "#b0bec5", "shape": "dot",      "size": 12},
    "VITAMIN":              {"color": "#ffcc80", "shape": "diamond", "size": 14},
    "FATTY_ACID":           {"color": "#81c784", "shape": "dot",     "size": 13},
    "COFACTOR":             {"color": "#ba68c8", "shape": "hexagon", "size": 14},
    "ATOMIC_STRUCTURE":     {"color": "#78909c", "shape": "square",   "size": 14},
    "SEQUENCE_HASH":        {"color": "#546e7a", "shape": "dot",      "size": 10},
    "GOCAM_ACTIVITY":       {"color": "#00897b", "shape": "ellipse",  "size": 16},
    "IMMUNE_RESPONSE":      {"color": "#e53935", "shape": "triangle", "size": 16},
    "CELLULAR_COMPONENT":   {"color": "#43a047", "shape": "dot",      "size": 14},
    "NON_CODING_GENE":      {"color": "#7cb9e8", "shape": "diamond",  "size": 16},
    "ELECTRICAL_COMPONENT": {"color": "#ffd700", "shape": "star",     "size": 16},
    "EXCITATION_FREQUENCY": {"color": "#ff69b4", "shape": "dot",      "size": 14},
    "ANATOMY_PART":         {"color": "#20b2aa", "shape": "box",      "size": 16},
    "CELL_POSITION":        {"color": "#dda0dd", "shape": "dot",      "size": 12},
    "EM_SIGNATURE":         {"color": "#48d1cc", "shape": "dot",      "size": 14},
    "SCAN_SIGNAL":          {"color": "#ff7f50", "shape": "dot",      "size": 14},
    "RAW_SCAN":             {"color": "#ff6347", "shape": "hexagon",  "size": 20},
    "SPATIAL_REGION":       {"color": "#00ced1", "shape": "square",   "size": 16},
    "PATHOLOGY_FINDING":    {"color": "#dc143c", "shape": "triangle", "size": 18},
}

# Merged lookup: biological types take precedence over generic code types.
_ALL_NODE_STYLES = {**_NODE_STYLES, **_BIO_NODE_STYLES}
_DEFAULT_NODE = {"color": "#888888", "shape": "dot", "size": 16}

# ── Edge palette ─────────────────────────────────────────────────────────────
_PALETTE = [
    "#ff6b6b", "#4ecdc4", "#45b7d1", "#96ceb4", "#ffeaa7", "#fd79a8",
    "#a29bfe", "#00b894", "#e17055", "#0984e3", "#6c5ce7", "#fdcb6e",
]


def _rel_color(rel: str) -> str:
    """Deterministic color per relation type from palette."""
    return _PALETTE[hash(rel) % len(_PALETTE)]


def _style_node(ntype: str, nid) -> dict:
    s = _ALL_NODE_STYLES.get(ntype, _DEFAULT_NODE)
    return {"label": str(nid), "title": f"{ntype}: {nid}", **s}


def _build_legend_html(present_types: list) -> str:
    """
    Generates a compact, semi-transparent legend panel (fixed, bottom-right).
    Only the node types actually present in the graph are listed.
    """
    items = ""
    for ntype in sorted(present_types):
        style = _ALL_NODE_STYLES.get(ntype, _DEFAULT_NODE)
        color = style["color"]
        label = ntype.replace("_", " ").title()
        items += (
            f'<div style="display:flex;align-items:center;gap:7px;margin:3px 0;">'
            f'<div style="width:11px;height:11px;border-radius:3px;'
            f'background:{color};flex-shrink:0;border:1px solid rgba(255,255,255,.18);"></div>'
            f'<span style="font-size:11px;color:#ccc;white-space:nowrap;">{label}</span>'
            f'</div>'
        )

    return (
        '<div id="acid-legend" style="'
        "position:fixed;bottom:20px;right:20px;z-index:9999;"
        "background:rgba(18,18,35,0.84);border:1px solid rgba(255,255,255,.10);"
        "border-radius:8px;padding:10px 14px;max-height:55vh;overflow-y:auto;"
        "box-shadow:0 4px 18px rgba(0,0,0,.45);backdrop-filter:blur(5px);"
        "min-width:165px;font-family:'Segoe UI',sans-serif;"
        '">'
        '<div style="font-size:12px;font-weight:600;color:#eee;'
        'margin-bottom:7px;letter-spacing:.05em;border-bottom:1px solid rgba(255,255,255,.08);'
        'padding-bottom:5px;">Node Types</div>'
        + items
        + "</div>"
    )


def create_g_visual(G, dest_path=None, ds=True, add_legend=True):
    """
    Build a pyvis Network from graph G with custom styles + optional legend.

    Parameters
    ----------
    G          : networkx graph
    dest_path  : if given, write HTML to this file; otherwise return HTML string
    ds         : True  → datastore format (nodes carry graph_item attr)
                 False → plain nx graph (G.nodes / G.edges directly)
    add_legend : inject a compact node-type legend into the HTML (default True)
    """
    print("create_g_visual G:", G, file=sys.stderr)
    try:
        new_G = nx.MultiGraph()
        present_types: set = set()   # collect types actually added to track legend entries

        if ds:
            for nid, attrs in G.nodes(data=True):
                if attrs.get("graph_item") == "node":
                    ntype = attrs.get("type", "NODE")
                    present_types.add(ntype)
                    new_G.add_node(nid, **_style_node(ntype, nid))
            for nid, attrs in G.nodes(data=True):
                if attrs.get("graph_item") == "edge":
                    src, trgt = attrs.get("src"), attrs.get("trgt")
                    if src and trgt and new_G.has_node(src) and new_G.has_node(trgt):
                        rel = attrs.get("rel", "edge")
                        new_G.add_edge(src, trgt, color=_rel_color(rel), title=rel)
        else:
            for nid, attrs in G.nodes(data=True):
                ntype = attrs.get("type", "NODE")
                present_types.add(ntype)
                new_G.add_node(nid, **_style_node(ntype, nid))
            for src, trgt, attrs in G.edges(data=True):
                if new_G.has_node(src) and new_G.has_node(trgt):
                    rel = attrs.get("rel", "link")
                    new_G.add_edge(src, trgt, color=_rel_color(rel), width=1.2, title=rel)

        options = '''
            const options = {
              "nodes": {
                "borderWidth": 2,
                "borderWidthSelected": 4,
                "font": { "size": 13, "face": "Segoe UI", "color": "#ffffff" },
                "shadow": { "enabled": true, "color": "rgba(0,0,0,0.25)", "size": 10, "x": 2, "y": 2 }
              },
              "edges": {
                "smooth": { "type": "continuous", "roundness": 0.45 },
                "font": { "size": 10, "color": "#aaaaaa" },
                "arrows": { "to": { "enabled": false } }
              },
              "physics": {
                "barnesHut": {
                  "gravitationalConstant": -3500,
                  "centralGravity": 0.08,
                  "springLength": 160,
                  "springConstant": 0.035,
                  "damping": 0.1
                }
              },
              "interaction": {
                "tooltipDelay": 150,
                "hideEdgesOnDrag": true
              }
            }
            '''

        net = Network(
            notebook=False,
            cdn_resources="in_line",
            height="1000px",
            width="100%",
            bgcolor="#1a1a2e",
            font_color="white",
        )

        net.barnes_hut()
        net.toggle_physics(True)
        net.set_options(options)
        net.from_nx(new_G)

        html = net.generate_html()

        # ── Inject legend overlay before </body> ──────────────────────────────
        if add_legend and present_types:
            legend_html = _build_legend_html(list(present_types))
            html = html.replace("</body>", legend_html + "\n</body>", 1)

        if dest_path is not None:
            parent = os.path.dirname(dest_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(html)
            print("html created and saved under:", dest_path, file=sys.stderr)
        else:
            return html
    except Exception as e:
        print("Err create_g_visual:", e, file=sys.stderr)
