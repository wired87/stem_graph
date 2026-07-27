"""
Workflow: analyze code (text or file/folder path) -> build graph -> visualize -> save.
"""
import json
import os
import re
import sys

import networkx as nx

from graph_creator import StructInspector

# Keys to strip before JSON serialization (e.g. callable)
_NON_SERIALIZABLE_KEYS = {"callable"}

# Skip these dirs when walking folder (e.g. .venv, __pycache__)
_SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", ".idea", "node_modules", ".tox"}


def _get_gutils():
    """Use GUtils from graph if qbrain available; else MinimalGUtils."""
    try:
        from graph.local_graph_utils import GUtils
        return GUtils
    except ImportError:
        print("qbrain not installed, using MinimalGUtils", file=sys.stderr)
        return _MinimalGUtils




class _MinimalGUtils:
    """Minimal GUtils for standalone use (no qbrain). Same add_node/add_edge interface."""

    def __init__(self, G=None, nx_only=True, **kwargs):
        self.G = nx.MultiGraph() if G is None else G
        self.nx_only = nx_only

    def _clean(self, s):
        return re.sub(r"[^a-zA-Z0-9_]", "", str(s)) if s else ""

    def add_node(self, attrs: dict, flatten=False):
        t = attrs.get("type")
        if not t:
            raise ValueError("NODE HAS NO ATTR type")
        nid = attrs["id"]
        self.G.add_node(nid, **{k: v for k, v in attrs.items() if k != "id"})
        return True

    def add_edge(self, src=None, trgt=None, attrs: dict = None, **kwargs):
        attrs = attrs or {}
        src = src or attrs.get("src")
        trgt = trgt or attrs.get("trgt")
        src_layer = (attrs.get("src_layer") or "NODE").upper().replace(" ", "_")
        trgt_layer = (attrs.get("trgt_layer") or "NODE").upper().replace(" ", "_")
        rel = (attrs.get("rel") or "link").lower().replace(" ", "_")
        if src and trgt:
            edge_attrs = {k: v for k, v in attrs.items() if k not in ("src", "trgt", "src_layer", "trgt_layer", "rel")}
            self.G.add_edge(src, trgt, rel=rel, src_layer=src_layer, trgt_layer=trgt_layer, **edge_attrs)

    def save_graph(self, dest_file):
        _save_graph_fallback(self.G, dest_file)


def _create_g_visual_standalone(G: nx.Graph, dest_path: str):
    """Pyvis visualization for code structure graph."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("visual", os.path.join(os.path.dirname(__file__), "graph", "visual.py"))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.create_g_visual(G, dest_path=dest_path, ds=False)
            print(f"Visualization saved: {dest_path}", file=sys.stderr)
            return
    except Exception:
        pass
    try:
        from pyvis.network import Network
        _PALETTE = ["#ff6b6b", "#4ecdc4", "#45b7d1", "#96ceb4", "#ffeaa7", "#fd79a8",
                    "#a29bfe", "#00b894", "#e17055", "#0984e3", "#6c5ce7", "#fdcb6e"]
        _rel_color = lambda rel: _PALETTE[hash(rel) % len(_PALETTE)]
        _ns = {"MODULE": ("#4a90d9", "box", 28), "CLASS": ("#7b68ee", "diamond", 24), "METHOD": ("#50c878", "dot", 18),
               "PARAM": ("#f0e68c", "triangle", 14), "FOLDER": ("#20b2aa", "box", 22)}
        new_G = nx.MultiGraph()
        for nid, attrs in G.nodes(data=True):
            ntype = attrs.get("type", "NODE")
            c, sh, sz = _ns.get(ntype, ("#888", "dot", 16))
            new_G.add_node(nid, label=str(nid), title=f"{ntype}: {nid}", color=c, shape=sh, size=sz)
        for src, trgt, attrs in G.edges(data=True):
            if new_G.has_node(src) and new_G.has_node(trgt):
                rel = attrs.get("rel", "link")
                new_G.add_edge(src, trgt, color=_rel_color(rel), width=1.2, title=rel)
        net = Network(notebook=False, cdn_resources="in_line", height="1000px", width="100%", bgcolor="#1a1a2e", font_color="white")
        net.barnes_hut()
        net.toggle_physics(True)
        net.set_options('{"nodes":{"borderWidth":2,"font":{"size":14}},"edges":{"smooth":{"type":"continuous"}}}')
        net.from_nx(new_G)
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        net.save_graph(dest_path)
        print(f"Visualization saved: {dest_path}", file=sys.stderr)
    except ImportError:
        print("pyvis not installed, skipping HTML visualization", file=sys.stderr)
    except Exception as e:
        print(f"Err create_g_visual: {e}", file=sys.stderr)


def _save_graph_fallback(G, dest_path: str):
    """Save graph to JSON, stripping non-serializable node/edge attrs."""
    G_copy = nx.MultiGraph() if isinstance(G, nx.MultiGraph) else nx.Graph()
    for nid, attrs in G.nodes(data=True):
        clean = {k: v for k, v in attrs.items() if k not in _NON_SERIALIZABLE_KEYS}
        G_copy.add_node(nid, **clean)
    for src, trgt, *rest in G.edges(data=True):
        attrs = rest[0] if rest else {}
        G_copy.add_edge(src, trgt, **{k: v for k, v in attrs.items() if k not in _NON_SERIALIZABLE_KEYS})
    data = nx.node_link_data(G_copy, edges="edges")
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def _load_content(source: str, is_path: bool) -> tuple[str, str]:
    """Return (content, name). name is module name for paths, 'inline' for text."""
    if is_path:
        path = os.path.abspath(source)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        name = os.path.splitext(os.path.basename(path))[0]
        print(f"Loaded file: {path} -> {name}", file=sys.stderr)
        return content, name
    return source, "inline"


def _path_to_node_id(path: str) -> str:
    """Normalize path to graph node id (forward slashes, no drive)."""
    p = os.path.normpath(path).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = p[2:].lstrip("/")
    return p or "."


def _add_folder_mapping(g_utils, root_path: str) -> set[str]:
    """
    os.walk root_path, add FOLDER nodes and contains edges.
    Returns set of .py file paths for later analysis.
    """
    root_abs = os.path.abspath(root_path)
    root_id = _path_to_node_id(root_abs)
    g_utils.add_node(attrs=dict(id=root_id, type="FOLDER", name=os.path.basename(root_abs) or root_id, path=root_abs))
    print(f"FOLDER node created: {root_id}", file=sys.stderr)

    py_files = set()
    for dirpath, dirnames, filenames in os.walk(root_abs):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        parent_id = _path_to_node_id(dirpath)
        if not g_utils.G.has_node(parent_id):
            g_utils.add_node(attrs=dict(id=parent_id, type="FOLDER", name=os.path.basename(dirpath) or ".", path=dirpath))
        # FOLDER -> FOLDER: link to parent dir (when inside tree)
        if dirpath != root_abs:
            par_dir = os.path.dirname(dirpath)
            if par_dir:
                par_id = _path_to_node_id(par_dir)
                if not g_utils.G.has_edge(par_id, parent_id):
                    g_utils.add_edge(src=par_id, trgt=parent_id, attrs=dict(rel="contains", src_layer="FOLDER", trgt_layer="FOLDER"))

        for d in dirnames:
            sub_path = os.path.join(dirpath, d)
            sub_id = _path_to_node_id(sub_path)
            if not g_utils.G.has_node(sub_id):
                g_utils.add_node(attrs=dict(id=sub_id, type="FOLDER", name=d, path=sub_path))
                print(f"FOLDER node created: {sub_id}", file=sys.stderr)
            g_utils.add_edge(src=parent_id, trgt=sub_id, attrs=dict(rel="contains", src_layer="FOLDER", trgt_layer="FOLDER"))

        for f in filenames:
            if f.endswith(".py"):
                py_files.add(os.path.join(dirpath, f))

    return py_files


def run_workflow(source: str, is_path: bool = True, output_dir: str = "firegraph-output"):
    """
    Analyze source (file path, folder path, or code string), build graph, visualize, save.
    If path is folder: os.walk adds FOLDER nodes + contains edges, then analyzes each .py file.
    output_dir: relative paths resolved from cwd (works when installed via pip).
    """
    # Validate input
    if not source or not isinstance(source, str):
        raise ValueError("source must be a non-empty string")
    source = source.strip()
    if not source:
        raise ValueError("source must be a non-empty string")
    if not output_dir or not isinstance(output_dir, str):
        output_dir = "firegraph-output"
    output_dir = output_dir.strip() or "firegraph-output"
    # Resolve relative to cwd so output lands in user's project when run via pip
    output_dir = os.path.abspath(output_dir) if not os.path.isabs(output_dir) else output_dir

    G = nx.MultiGraph()
    GUtilsCls = _get_gutils()
    g_utils = GUtilsCls(G=G, nx_only=True)

    if is_path:
        path = os.path.abspath(source)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")

        if os.path.isdir(path):
            # FOLDER: add dir mapping, then analyze each .py
            print(f"Walking folder: {path}", file=sys.stderr)
            py_files = _add_folder_mapping(g_utils, path)
            inspector = StructInspector(G=G, g=g_utils)
            root_abs = os.path.abspath(path)
            for fp in sorted(py_files):
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Unique module id: rel path with dots (e.g. pkg.__init__)
                    rel = os.path.relpath(fp, root_abs).replace("\\", "/").replace("/", ".").replace(".py", "")
                    module_name = rel or "root"
                    dir_id = _path_to_node_id(os.path.dirname(fp))
                    print(f"Analyzing: {fp} -> {module_name}", file=sys.stderr)
                    result = inspector.convert_module_to_graph(content, module_name)
                    if isinstance(result, dict) and "Error" in result:
                        print(f"Skip {fp}: {result['Error']}", file=sys.stderr)
                        continue
                    # FOLDER -> MODULE (dir contains module)
                    if g_utils.G.has_node(dir_id) and g_utils.G.has_node(module_name):
                        g_utils.add_edge(src=dir_id, trgt=module_name, attrs=dict(rel="contains", src_layer="FOLDER", trgt_layer="MODULE"))
                except Exception as e:
                    print(f"Err analyzing {fp}: {e}", file=sys.stderr)
        else:
            # FILE: single file flow
            content, module_name = _load_content(source, is_path)
            print(f"Analyzing module: {module_name}", file=sys.stderr)
            inspector = StructInspector(G=G, g=g_utils)
            result = inspector.convert_module_to_graph(content, module_name)
            if isinstance(result, dict) and "Error" in result:
                raise ValueError(result["Error"])
            # Optional: link to parent dir
            dir_id = _path_to_node_id(os.path.dirname(path))
            if dir_id and g_utils.G.has_node(module_name):
                g_utils.add_node(attrs=dict(id=dir_id, type="FOLDER", name=os.path.basename(os.path.dirname(path)), path=os.path.dirname(path)))
                g_utils.add_edge(src=dir_id, trgt=module_name, attrs=dict(rel="contains", src_layer="FOLDER", trgt_layer="MODULE"))
    else:
        # Inline text
        content, module_name = _load_content(source, is_path)
        print(f"Analyzing module: {module_name}", file=sys.stderr)
        inspector = StructInspector(G=G, g=g_utils)
        result = inspector.convert_module_to_graph(content, module_name)
        if isinstance(result, dict) and "Error" in result:
            raise ValueError(result["Error"])

    # SemanticMaster: embed nodes, add technique nodes, similarity edges (when embedder available)
    try:
        from graph.semantic_master import SemanticMaster
        if SemanticMaster:
            sm = SemanticMaster(g_utils)
            sm.run(threshold=0.5)
    except ImportError:
        # graph package may fail (qbrain deps); load semantic_master directly
        try:
            import importlib.util
            _sm_path = os.path.join(os.path.dirname(__file__), "graph", "semantic_master.py")
            if os.path.isfile(_sm_path):
                spec = importlib.util.spec_from_file_location("semantic_master", _sm_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if getattr(mod, "SemanticMaster", None):
                    mod.SemanticMaster(g_utils).run(threshold=0.5)
        except Exception:
            pass

    # Save graph JSON
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "graph.json")
    try:
        g_utils.save_graph(json_path)
    except Exception as e:
        print(f"GUtils.save_graph failed ({e}), using fallback save", file=sys.stderr)
        _save_graph_fallback(G, json_path)
    print(f"Graph saved: {json_path}", file=sys.stderr)

    # Visualize and save HTML
    html_path = os.path.join(output_dir, "graph.html")
    _create_g_visual_standalone(G, html_path)

    return G, json_path, html_path
