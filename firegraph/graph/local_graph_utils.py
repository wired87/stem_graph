"""

"""

import json
import os
import time
from tempfile import TemporaryDirectory

from typing import List, Dict
import networkx as nx
import numpy as np

from firegraph.utils.serialize_complex import check_serialize_dict
from firegraph.graph.visual import create_g_visual
from firegraph.utils.manipulator import Manipulator
from firegraph.graph.utils import Utils

class GUtils(Utils):
    """
    Handles State G local and 
    History G through DataManager
    
    ALERT:
    DB Pushs need to be ahndled externally (DBManager -> _google) 
    """

    def __init__(
            self,
            G=None,
            g_from_path=None,
            nx_only=False,
            # queue: queue.Queue or None = None,
            enable_data_store=True,
            history_types=None,
            file_store=None,
            # When True, every add_node / add_edge / update_node / delete_node
            # is mirrored into the two-table DuckDB store via GraphStore.
            enable_db_store=False,
            # Optional pre-built GraphStore (e.g. shared connection in tests / CLI).
            db_store=None,
    ):
        super().__init__()
        self.G = None
        self.enable_data_store = enable_data_store
        self.g_from_path = g_from_path
        self.get_nx_graph(G)
        self.nx_only = nx_only
        self.history = {}
        self.batch_ids = set()
        self.edge_store = []

        #todo just tempora"ry look for demo G in QFS and BB
        demo_G_save_path = r"C:\Users\bestb\PycharmProjects\BestBrain\admin_data\demo_G.json" if os.name == "nt" else "admin_data/demo_G.json"
        if os.path.isfile(demo_G_save_path):
            self.demo_G_save_path = demo_G_save_path
        else:
            self.demo_G_save_path = r"C:\Users\bestb\PycharmProjects\BestBrain\admin_data\demo_G.json" if os.name == "nt" else "admin_data/demo_G.json"

        self.manipulator = Manipulator()

        if self.enable_data_store is True:
            self.datastore = nx.Graph()
            self.history_types = history_types  # list of nodetypes captured by dataqstore  ALL_SUBS + ["ENV"]

        self.file_store=file_store or TemporaryDirectory()

        self.metadata_fields = [
            "graph_item",
            "index",
            "entry_index",
            "time",
        ]

        # Sim timestep must be updated externally for each loop
        self.timestep = None
        self.key_map = set()
        self.id_map = set()
        self.schemas = {}

        self.enable_db_store = enable_db_store
        self.db_store = db_store
        if self.enable_db_store and self.db_store is None:
            try:
                from firegraph._db.graph_store import GraphStore
                self.db_store = GraphStore()
                print("[GUtils] DB store enabled (nodes, edges tables)")
            except Exception as e:
                # never crash the in-memory pipeline because the DB is down
                print(f"[GUtils] DB store disabled (init failed): {e}")
                self.enable_db_store = False
                self.db_store = None

        print("GUtils initialized")

    def nodes_by_type(self, ntype):
        count = [(nid, attrs) for nid, attrs in self.G.nodes(data=True) if
                 attrs.get("type") == ntype]
        print(len(count), ntype,"nodes extracted")
        return count

    def _db_upsert_edge(self, attrs: dict) -> None:
        """Mirror an add_edge call into the edges table (check + add/save)."""
        if not self.enable_db_store or self.db_store is None:
            return
        eid = attrs.get("id")
        if not eid:
            return
        try:
            existed = self.db_store.has_edge(eid)
            ok = self.db_store.upsert_edge(attrs)
            if ok:
                print(f"[GUtils.db] edge {'EDITED' if existed else 'ADDED'}: {eid}")
        except Exception as e:
            print(f"[GUtils.db] edge sync failed for {eid}: {e}")

    def _db_edit_node(self, attrs: dict) -> None:
        """Mirror an update_node call (merge existing row with new attrs)."""
        if not self.enable_db_store or self.db_store is None:
            return
        nid = attrs.get("id")
        if not nid:
            return
        try:
            ok = self.db_store.update_node(attrs)
            if ok:
                print(f"[GUtils.db] node MERGED: {nid}")
        except Exception as e:
            print(f"[GUtils.db] node merge failed for {nid}: {e}")

    def _db_delete_node(self, nid: str) -> None:
        """Mirror a delete_node call so the DB stays consistent with G."""
        if not self.enable_db_store or self.db_store is None:
            return
        try:
            self.db_store.delete_node(nid)
            print(f"[GUtils.db] node DELETED: {nid}")
        except Exception as e:
            print(f"[GUtils.db] node delete failed for {nid}: {e}")

    # ------------------------------------------------------------------
    # CACHE LAYER -- used by pre-fetch sites to skip web requests for
    # ids that are already known in the DB. Returns the set of ids that
    # were restored (node row + every edge touching it) into self.G.
    # ------------------------------------------------------------------
    def cache_load(self, ids) -> set:
        """Try to hydrate ``ids`` from the DB store. No-op when disabled."""
        if not self.enable_db_store or self.db_store is None:
            return set()
        try:
            return self.db_store.hydrate(self, ids)
        except Exception as e:
            print(f"[GUtils.cache_load] failed: {e}")
            return set()

    # ------------------------------------------------------------------
    # INPUT ALIGNMENT + GRAPH CACHE WALK
    # ------------------------------------------------------------------
    # align_input: compare a freshly embedded user input to every prior
    # <TYPE>_INPUT row in the DB store. If cosine similarity > threshold,
    # the previously processed input is considered equivalent and the
    # caller can short-circuit through cache_walk.
    #
    # cache_walk: BFS from a cached input node through the DB graph and
    # hydrate every reachable node + edge into the in-memory G. One brand
    # new input ("Brain") thus brings back its TISSUE root, anatomy
    # children, proteins, GO terms, drugs - whatever was persisted on the
    # previous run - with zero web traffic.
    # ------------------------------------------------------------------
    def align_input(self, embedding, ntype: str, threshold: float = 0.95, exclude_id: str = None):
        """Find the closest prior ``<TYPE>_INPUT`` row in the DB store.

        Returns ``(best_id, score)`` when ``score > threshold``, else ``None``.
        ``exclude_id`` lets callers ignore the row they just wrote (otherwise
        a fresh input would always match itself with score 1.0).
        """
        # No DB layer -> no cache to align against; this is a clean no-op.
        if not self.enable_db_store or self.db_store is None:
            return None
        # The DBManager handle lives under the GraphStore facade.
        try:
            rows = self.db_store._db.run_query(
                "SELECT id, embedding FROM nodes WHERE type = ?",
                params=[str(ntype).upper()],
                conv_to_dict=True,
            )
        except Exception as e:
            print(f"[GUtils.align_input] DB probe failed for type={ntype}: {e}")
            return None

        if not rows:
            return None

        # decode JSON-encoded embedding column + drop self / empty rows
        candidates = []
        for r in rows:
            rid = r.get("id")
            if not rid or rid == exclude_id:
                continue
            emb = r.get("embedding")
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except (json.JSONDecodeError, ValueError):
                    continue
            if not emb:
                continue
            candidates.append((rid, emb))

        if not candidates:
            return None

        # Cosine similarity: normalize once, dot-product per candidate.
        q = np.asarray(embedding, dtype=np.float32)
        q_norm = q / (np.linalg.norm(q) or 1.0)

        best_id, best_score = None, -1.0
        for cid, cemb in candidates:
            c = np.asarray(cemb, dtype=np.float32)
            denom = np.linalg.norm(c) or 1.0
            score = float(np.dot(q_norm, c / denom))
            if score > best_score:
                best_id, best_score = cid, score

        if best_score > threshold:
            print(f"[GUtils.align_input] HIT {best_id} (score={best_score:.3f}) for type={ntype}")
            return best_id, best_score
        return None

    def cache_walk(self, node_id: str, max_depth: int = 4) -> set:
        """
        Hydrate every node reachable from ``node_id`` in the DB store into G.

        Uses ``cache_load`` (which already pulls a node + every edge touching
        it in one round-trip) as the per-layer primitive, then expands BFS
        through the in-memory neighbors that just appeared. ``max_depth``
        bounds the walk so a dense cached graph never explodes the working
        set in one call (4 is enough for INPUT -> TISSUE -> PROTEIN -> GO).
        """
        if not self.enable_db_store or self.db_store is None or not node_id:
            return set()

        visited: set = set()
        frontier: set = {node_id}
        for depth in range(max_depth):
            if not frontier:
                break
            # Pull this layer's rows + every edge touching them.
            restored = self.cache_load(frontier)
            visited.update(restored)
            # Expand: NetworkX neighbors include the stub endpoints that hydrate
            # already added for any edge that crosses into / out of the layer.
            next_frontier: set = set()
            for nid in restored:
                if not self.G.has_node(nid):
                    continue
                for nnid in self.G.neighbors(nid):
                    if nnid not in visited:
                        next_frontier.add(nnid)
            frontier = next_frontier - visited

        print(f"[GUtils.cache_walk] {len(visited)} nodes hydrated starting from {node_id}")
        return visited

    def get_edge(self, src, trgt):
        edge_data = self.G.get_edge_data(src, trgt)
        if not edge_data:
            return None
        if isinstance(self.G, (nx.MultiGraph, nx.MultiDiGraph)):
            return next(iter(edge_data.values()))
        return edge_data

    def get_graph(self):
        return self.G

    def get_node(self, nid=None, key=None, value=None):
        try:
            node_attrs = None
            if nid is not None:
                if self.G.has_node(nid):
                    return {"id":nid, **{k:v for k,v in self.G.nodes[nid].items() if k not in ["id"]}}

            elif key is not None and value is not None:
                for k, v in self.G.nodes(data=True):
                    if v.get(key) == value or k == value:
                        node_attrs = {"id":k, **{k:v for k,v in v.items() if k not in ["id"]}}

            if node_attrs is None:
                return None
            return node_attrs
        except Exception as e:
            print("Err get_node:", e)
        return None

    def print_edges(self, trgt_l, src_l):
        print("len edges", len([
            attrs
            for src, trgt, attrs in self.G.edges(data=True)
            if attrs.get("src_layer").upper() == src_l.upper()
            and attrs.get("trgt_layer").upper() == trgt_l.upper()
        ]))


    def add_node(self, attrs: dict, flatten=False):
        try:
            #print("Add node:", attrs)
            attrs = self.manipulator.clean_attr_keys(
                attrs, flatten
            )

            if attrs.get("type") is None:
                raise Exception("NODE HAS NO ATTR type")

            attrs["type"] = attrs["type"].upper()
            nid = attrs["id"]

            if self.nx_only is False:
                self.local_batch_loader(attrs)

            # CHECK UPDATE
            if self.G.has_node(nid):
                self.G.nodes[nid].update(attrs)

            self.G.add_node(nid, **{k: v for k, v in attrs.items() if k != "id"})

            # Extedn keys
            self._extend_key_map(attrs)
            self._extend_id_map(nid)

            return True
        except Exception as e:
            print("Err add_node:", e)



    def h_entry(self, id, attrs, timestep=None, graph_item="node"):
        ntype = attrs.get("type", "")
        if ntype is None:
            ntype = graph_item  # -> SET EDGE

        if self.enable_data_store is True:
            if timestep is None:
                timestep = attrs.get("time", 0)

            history_id = f"{id}_{int(time.time())}_{timestep}"

            len_type_entries = len(
                [
                    (inid, iattrs)
                    for inid, iattrs in self.datastore.nodes(data=True) if
                    iattrs.get("type", "0").upper() == attrs.get("type", "1").upper()
                ]
            )

            attrs = dict(
                type=id,
                entry_index=len_type_entries,
                graph_item=graph_item,
                base_type=ntype,
                **{k: v for k, v in attrs.items() if k not in ["id", "type"]}
            )

            #print("Add H Entry:")
            #pprint.pp(attrs)

            # Extedn keys
            self._extend_key_map(attrs)
            self._extend_id_map(id)

            self.datastore.add_node(
                history_id,
                **attrs
            )
            #print("H entry node added", self.datastore.nodes[history_id])
        else:
            raise ValueError("Invalid admin_data!!!!", id, attrs)


    def add_edge(
            self,
            src=None,
            trgt=None,
            attrs: dict or None = None,
            flatten=False,
            timestep=None,
            index=None
    ):
        #print(f"Add edge: {src} -> {trgt}")

        # Color
        color = None

        # Check
        if index is None:
            index = attrs.get("index", None)

        if index is not None:
            color = f"rgb({index + .5}, {index + .5}, {index + .5})"

        try:
            src_layer = self.manipulator.replace_special_chars(attrs.get("src_layer")).upper()
            trgt_layer = self.manipulator.replace_special_chars(attrs.get("trgt_layer")).upper()

            if src is None:
                src = attrs.get("src") or src
            if trgt is None:
                trgt = attrs.get("trgt") or trgt

            if src and trgt and src_layer and trgt_layer:
                if isinstance(src, int):
                    src = str(src)
                if isinstance(trgt, int):
                    trgt = str(trgt)


                attrs = self.manipulator.clean_attr_keys(attrs, flatten)
                # #print("attrs_new", attrs )
                rel = attrs["rel"].lower().replace(" ", "_")

                edge_id = f"{src}_{rel}_{trgt}"

                attrs = {
                    **attrs,
                    "src": src,
                    "trgt": trgt,
                    "id": edge_id,
                    "tid": 0,
                    "color": color,
                }

                # Add keys
                self._extend_key_map(attrs)
                self._extend_id_map(
                    attrs["id"]
                )

                # #print(f"ids {src} -> {trgt}; Layer {src_layer} -> {trgt_layer}")
                edge_table_name = f"{src_layer}_{rel}_{trgt_layer}"
                attrs["type"] = edge_table_name

                src_node_attr = {"id": src, "type": src_layer}
                trgt_node_attr = {"id": trgt, "type": trgt_layer}

                if self.nx_only is False:
                    # todo run in executor
                    # #print("Upsert Local Batch Loader")
                    self.local_batch_loader(src_node_attr)
                    self.local_batch_loader(trgt_node_attr)
                    self.local_batch_loader(attrs)

                #print(src, "<->", trgt)
                self.G.add_edge(src, trgt, **{k: v for k, v in attrs.items()})

                if not self.G.has_node(src):
                    print(f"Add missing src node {src} in add_edge", attrs)
                    self.add_node(src_node_attr)

                if not self.G.has_node(trgt):
                    print(f"Add missing trgt node {trgt} in add_edge", attrs)
                    self.add_node(trgt_node_attr)

                self.edge_store.append(attrs)
                if len(self.edge_store) > 0:
                    self._db_upsert_edge(attrs)
                    self.edge_store = []
            else:
                raise ValueError(f"Wrong edge fromat")

        except Exception as e:
            raise ValueError(f"Skipping link src: {src} -> trgt: {trgt} cause:", e, attrs)


    def _extend_key_map(self, attrs):
        for k in list(attrs.keys()):
            if k not in self.key_map:
                self.key_map.add(k)


    def _extend_id_map(self, nid):
        if nid not in self.id_map:
            self.id_map.add(nid)


    def get_edges(self, src, trgt):
        edges = []
        if "MultiGraph" in str(type(self.G)):
            for key, edge in self.G.get_edge_data(src, trgt).items():
                edges.append(edge)
        else:
            edges.append(self.G.edges[src, trgt])
        return edges

    """def get_edges(self, datastore=True, just_id=False):
        if datastore is False:
            if just_id is True:
                edges = [attrs.get("id") for _, _, attrs in self.G.edges(data=True)]
            else:
                edges = [{"src": src, "trgt": trgt, "attrs": attrs} for src, trgt, attrs in self.G.edges(data=True)]

        else:
            edges = [{"attrs": attrs} for eid, attrs in self.datastore.edges(data=True) if
                    attrs.get("graph_item").lower() == "edge"]
        return edges"""

    def get_edges_from_node(self, nid, datastroe=True):
        new_all_edges = []

        if datastroe is False:
            all_edges = [{"src": src, "trgt": trgt, "attrs": attrs} for src, trgt, attrs in self.G.edges(data=True)]
            for edge in all_edges:
                if edge["src"] == nid or edge["trgt"] == nid:
                    new_all_edges.append(edge)
        else:
            return [{"attrs": attrs, "id": eid} for eid, attrs in self.datastore.edges(data=True) if
                    attrs.get("graph_item").lower() == "edge"]

        if len(new_all_edges):
            all_edges = new_all_edges
        return all_edges


    def update_node(self, attrs, disable_history=False, overwrite=False):
        nid = attrs.get("id")
        node_attrs = self.G.nodes[nid]
        if node_attrs is None:
            print("Node couldnt be updated...")
            return

        # todo serilize @ save
        #attrs = check_serialize_dict(attrs, [k for k in attrs.keys()])

        # Add keys
        self._extend_key_map(attrs)
        if overwrite is False:
            self.G.nodes[nid].update(attrs)
        elif overwrite is True:
            self.G.nodes[nid] = attrs
        if self.enable_data_store is True and disable_history is False:
            # Add history entry
            self.h_entry(
                attrs["id"],
                {k: v for k, v in attrs.items() if k != "id"},
                graph_item="node"
            )

        # DB sync (edit): merge new attrs with the existing row and upsert,
        # so partial updates do not erase previously persisted columns.
        self._db_edit_node(attrs)

    def update_edge(self, src, trgt, attrs, rels: str or list = None, temporal=False):
        # rel = attrs.get("rel", "").lower().replace(" ", "_")
        """
        src_layer = attrs.get("src_layer").upper()
        trgt_layer = attrs.get("trgt_layer").upper()
        table_name = f"{src_layer}_{rel}_{trgt_layer}
        """

        # serialize attrs
        # todo @ save chek serilize otherwise ray actors get serialized fuck in
        # attrs = check_serialize_dict(attrs, [k for k in attrs.keys()])

        # Add keys
        self._extend_key_map(attrs)

        # Update nx
        if isinstance(self.G, (nx.MultiGraph, nx.MultiDiGraph)):
            for key, edge in self.G.get_edge_data(src, trgt).items():
                erel = edge.get("rel")
                if rels is None or erel in rels:
                    if self.enable_data_store is True:
                        edge_id = f"{src}_{erel}_{trgt}"
                        self.h_entry(
                            edge_id,
                            {k: v for k, v in attrs.items() if k != "id"},
                            graph_item="edge"
                        )
                    self.G.edges[src, trgt, key].update(attrs)
        else:
            if self.enable_data_store is True:
                edge_id = self.G.edges[src, trgt]["id"]
                self.h_entry(
                    edge_id,
                    {k: v for k, v in attrs.items() if k != "id"},
                    graph_item="edge"
                )
            self.G.edges[src, trgt].update(attrs)

        # todo handle async rt spanner || fbrtdb

    ####################################
    # HELPER
    ####################################

    def get_nx_graph(self, G):
        if self.g_from_path is not None:
            if os.path.exists(self.g_from_path):
                self.load_graph()
        if G is not None:
            self.G = G
        elif self.G is None:
            self.G = nx.MultiGraph()
        #print("Local Graph loaded")

    def save_graph(self, dest_file, ds=False):
        print("Save Gs")

        if ds is True:
            G=self.datastore
        else:
            G=self.G
        self._link_safe(
            G,
            dest_file
        )
        print(f"G admin_data written to :{dest_file}")


    def _link_safe(self, G, dest_name):
        G = self.check_serilize(G)
        data = nx.node_link_data(G)

        with open(f"{dest_name}", "w") as f:
            json.dump(data, f)

    def check_serilize(self, G):
        for nid, attrs in G.nodes(data=True):
            G.nodes[nid].update(
                check_serialize_dict(
                    attrs,
                    [k for k in attrs.keys()],
                )
            )
            if "embedding" in attrs:
                attrs["embedding"] = None
            if "embed" in attrs:
                attrs["embed"]= None

        if isinstance(G, (nx.MultiGraph, nx.MultiDiGraph)):
            for u, v, k, d in G.edges(keys=True, data=True):
                G.edges[u, v, k].update(check_serialize_dict(d, list(d.keys())))
        else:
            for src, trgt, attrs in G.edges(data=True):
                G.edges[src, trgt].update(check_serialize_dict(attrs, list(attrs.keys())))
        return G


    def load_graph(self, local_g_path=None):
        if local_g_path is None:
            local_g_path = self.g_from_path
        """Loads the networkx graph from a JSON file."""
        print(f"📂 Loading graph from {local_g_path}...")
        with open(local_g_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)  # Use json.load() for files, not json.loads()

        self.G = nx.node_link_graph(graph_data, multigraph=graph_data.get("multigraph", True))

        # return env
        for k, v in self.G.nodes(data=True):
            type = v.get("type")
            if type == "ENV":
                return k, v
        print(f"✅ Graph loaded! {len(self.G.nodes)} nodes, {len(self.G.edges)} edges.")

    def print_status_G(self):
        print("STATUS:", self.G)
        everything = {}
        for k, v in self.G.nodes(data=True):
            ntype = v.get("type")
            if ntype not in everything:
                everything[ntype] = []
            everything[ntype].append(k)
        for k, v in everything.items():
            print(f"{k}: {len(v)} nodes:")

    def local_batch_loader(self, args):
        table_name = args.get("type")
        row_id = args.get("id", args.get("id"))
        if table_name:
            if table_name not in self.schemas:
                self.schemas[table_name] = {
                    "schema": {},
                    "rows": [],
                    "id_map": set(),
                }
                #print(f"Added {table_name} to schema")

            if row_id not in [item for item in self.schemas[table_name]["id_map"]]:
                # #print(f"Insert {row_id} into {table_name}")
                self.schemas[table_name]["rows"].append(args)
                self.schemas[table_name]["id_map"].add(row_id)
            # else:
            # #print(f"{row_id} already in schema")
        # #print("Added args")

    def get_single_neighbor_nx(self, node, target_type:str):
        #print("Node", node)
        try:
            if isinstance(node, tuple):
                node = node[0]
            for neighbor in self.G.neighbors(node):
                if self.G.nodes[neighbor].get('type') == target_type:
                    return neighbor, self.G.nodes[neighbor]
            return None, None  # No neighbor of that type found
        except Exception as e:
            print(f"Couldnt fetch content: {e}")

    def get_node_list(self, trgt_types, just_id=False):
        interest = {
            nid: attrs
            for nid, attrs in self.G.nodes(data=True)
            if attrs.get("type") in trgt_types
        }
        if just_id is True:
            interest = list(interest.keys())
        return interest


    def get_edge_ids(self, src, neighbor_ids):
        eids = []
        for nnid in neighbor_ids:
            eattrs = self.G.get_edge_data(src, nnid)
            if "id" in eattrs:
                eid = eattrs["id"]
            else:
                rel = eattrs.get("rel")
                eid = f"{src}_{rel}_{nnid}"
            eids.append(eid)
        #print(f"Edge Ids extracted: {eids}")
        return eids



    def get_neighbor_list(
            self,
            node,
            target_type: str or list or None = None,
            just_ids=False
    ) -> List[str] or Dict[str, Dict]:
        neighbors = {}

        # Filter Input
        if isinstance(target_type, str):
            target_type = [target_type]

        if target_type is None:
            if self.G.has_node(node):
                return {nnid: self.G.nodes[nnid] for nnid in self.G.neighbors(node)}
            else:
                print(f"node {node} not in G")

        upper_trgt_types = [t.upper() for t in target_type]

        if just_ids is True:
            nids = list(self.G.neighbors(node))
            #print(f"Node Ids extracted: {nids}")
            return nids

        for neighbor in self.G.neighbors(node):
            # Get neighbor from type
            nattrs = self.G.nodes[neighbor]
            if target_type is not None:
                try:
                    ntype = nattrs.get('type').upper()
                    if ntype in upper_trgt_types:
                        if neighbor not in neighbors:
                            neighbors[neighbor] = {}
                        neighbors[neighbor] = nattrs
                except Exception as e:
                    print("Err neighbors", e, nattrs, neighbor)

        print(f"Neighbors extracted: {neighbors.keys()}")
        return neighbors


    def get_neighbor_list_rel(
        self,
        node:str,
        trgt_rel: str or list or None = None,
        as_dict=False,
        just_ids=False,
    ) -> list[tuple] or dict:
        neighbors = {}
        edges = {}

        if isinstance(trgt_rel, str):
            trgt_rel = [trgt_rel]

        # Get neighbor from rel
        for nnid in self.G.neighbors(node):
            edge_data = self.G.get_edge_data(node, nnid)

            try:
                if isinstance(self.G, (nx.MultiGraph, nx.MultiDiGraph)):
                    for key, edge_attrs in edge_data.items():
                        ntype = edge_attrs.get('type')

                        if edge_attrs.get("rel") in trgt_rel:
                            if ntype not in neighbors:
                                neighbors[nnid] = {}
                            edges[nnid] = edge_attrs
                            neighbors[nnid] = self.G.nodes[nnid]
                else:
                    # check if rel matches
                    if edge_data.get("rel").lower() in [rel.lower() for rel in trgt_rel]:
                        # get nodes from extracted edges
                        attrs = self.G.nodes[nnid]
                        neighbors[nnid] = {
                            "id": nnid,
                            **{
                                k: v
                                for k, v in attrs.copy().items()
                                if k != "id"
                            }
                        }

            except Exception as e:
                print(f"Err get_neighbor_list_rel for ({edge_data}):", e)

        if just_ids is True:
            return list(neighbors.keys())

        if as_dict is True:
            return neighbors

        return [
            (nid, attrs)
            for nid, attrs in neighbors.items()
        ]

    def remove_node(self, node_id, ntype):
        for row in self.schemas[ntype]["rows"]:
            if row["id"] == node_id:
                self.schemas[ntype]["rows"].remove(row)
                break
        self.G.remove_node(node_id)


    def cleanup_self_schema(self):
        # #print("Cleanup schema")
        for k, v in self.schemas.items():
            v["rows"] = []


    def build_G_from_data(
            self,
            initial_data,
            env_id=None,
            save_demo=False,
    ):
        # --- Graph aufbauen ---
        env = None
        data_keys = [k for k in initial_data.keys()]
        print(f"INITIAL DATA KEYS: {data_keys}")

        for node_type, node_id_data in initial_data.items():
            # Just get valid
            nupper = node_type.upper()
            valid_types = []
            nupper_valid_t = nupper in valid_types

            print(f"{nupper} valid: {nupper_valid_t}")

            if nupper_valid_t:
                if isinstance(node_id_data, dict):  # Sicherstellen, dass es ein Dictionary ist
                    for nid, attrs in node_id_data.items():
                        # print(f">>>NID, {nid}")
                        if node_type.lower() == "EDGES":
                            parts = nid.split(f"_{attrs.get('rel')}_")
                            # print("parts", parts)
                            # check 2 ids in id and
                            if len(parts) >= 2:
                                self.add_edge(
                                    parts[0],
                                    parts[1],
                                    attrs=attrs
                                )
                            else:
                                print("something else!!!")

                        elif node_type == "ENV":
                            print("Env recognized")
                            env = attrs
                            env_id = nid
                            self.add_node(
                                attrs=attrs,
                            )
                            # Speichern Sie die env_id, falls benötigt
                        else:
                            self.add_node(
                                attrs=attrs,
                            )
                else:
                    print(f"DATA NOT A DICT:{node_type}:{node_id_data}")
                    # pprint.pp(node_id_data)
                # time.sleep(10)

            else:
                print(f"TYPE NOT VALID:{node_type}")

        print(f"Graph successfully build: {self.G}")

        if save_demo is True and getattr(self, "demo_G_save_path", None) is not None:
            self.save_graph(dest_file=self.demo_G_save_path)
        return env, env_id

    def delete_node(self, delid):
        if delid and self.get_node(key="id", value=delid):
            self.G.remove_node(delid)
            self._db_delete_node(delid)
        else:
            print(f"Couldnt delete since {delid} doesnt exists")
    
    
    def get_node_pos(self, G=None):
        if G==None:
            G = self.G
        serializable_node_copy = []
        valid_types = []
        for nid, attrs in G.nodes(data=True):
            ntype = attrs.get("type")
            if ntype in valid_types:
                # todo single subs
                serializable_node_copy.append(
                    {
                        "id": nid,
                        "pos": attrs.get("pos")
                    }
                )
        return serializable_node_copy


    def get_nodes(
            self,
            filter_key=None,
            filter_value:str or list=None,
            just_id=False,
    ) -> list[int] or list[tuple]:
        #print("G:", self.G)
        nodes = self.G.nodes(data=True)

        #print(f"len nodes: {len(nodes)}")

        if filter_key is not None and filter_value is not None:
            new_nodes = []
            if not isinstance(filter_value, list):
                filter_value = [filter_value]

            for nid, attrs in nodes:
                if attrs.get(filter_key) in filter_value:
                    if just_id is True:
                        new_nodes.append(
                            nid
                        )
                    else:
                        new_nodes.append(
                            (nid, attrs)
                        )
            nodes = new_nodes
        print("get_nodes... done")
        return nodes

    
    def get_edges_src_trgt_pos(self, G=None, get_pos=False) -> list[dict]:
        if G == None:
            G = self.G
        edges=[]
        valid_types = []
        for src, trgt, attrs in G.edges(data=True):
            src_attrs = G.nodes[src]
            trgt_attrs = G.nodes[trgt]

            src_type = src_attrs["type"]
            trgt_type = trgt_attrs["type"]

            if src_type in valid_types and trgt_type in valid_types:
                if get_pos is True:
                    src_pos = src_attrs["pos"]
                    trgt_pos = trgt_attrs["pos"]

                    # todo calc weight based on
                    edges.append(
                        dict(
                            src=src_pos,
                            trgt=trgt_pos
                        )
                    )
                else:
                    edges.append(
                        dict(
                            src=src,
                            trgt=trgt
                        )
                    )
        #print(f"edge src trgt pos set: {edges}")
        return edges

    def create_html(self):
        save_path = os.path.join(
            self.file_store.name,
            "graph.html",
        )
        html = create_g_visual(self.datastore, dest_path=None)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML Graph was written to: {save_path}")





    def categorize_nodes_in_types(self, valid_ntypes) -> dict[list]:
        categorized = {}
        for nid, attrs in self.G.nodes(data=True):
            ntype = attrs.get("type")
            if ntype:
                ntype=ntype.upper()
            if ntype in [n.upper() for n in valid_ntypes]:
                if ntype not in categorized:
                    categorized[ntype] = []
                categorized[ntype].append(
                    (nid, attrs)
                )
        print("Nodes in types categorized")
        return categorized

    def categorize_nodes_in_qfns(self) -> dict[list[tuple]]:
        categorized = {}
        points = [(nid, attrs) for nid, attrs in self.G.nodes(data=True) if attrs.get("type") == "PIXEL"]

        for qfn in points:
            qfn_id = qfn[0]
            categorized[qfn_id] = self.get_neighbor_list_rel(qfn_id, trgt_rel="has_field")

        print("Nodes in PIXELs categorized")
        return categorized


    ###################
    # GETTER
    ###################

    def get_demo_G_save_path(self):
        return self.demo_G_save_path

    def get_env(self):
        """env:tuple = [(nid, attrs) for nid, attrs in self.G.nodes(admin_data=True) if attrs.get("type") == "ENV"][0]
        return {"id": env[0], **{k:v for k,v in env[1].items() if k != "id"}}"""
        for nid, attrs in self.G.nodes(data=True):
            if attrs.get("type") == "ENV":
                print("ENV entry found")
                return {
                    "id": nid,
                    **{k: v for k, v in attrs.items() if k != "id"}}

