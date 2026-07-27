"""
firegraph._db.graph_store -- two-table DuckDB persistence facade.

User prompt (Cursor session):
    "allocate _db logic to firegraph and include a check add, save, edit
     process in each add_node, add_edge, and update_node-process.
     (The db layer includes just two tables (nodes and edges) where specific
     rows include the same fields as in the G-instance."

Schema (exactly two tables, both lazy-extended by ``DBManager.insert``):
    nodes(id PK, type, ... <all attrs of the in-memory G node as columns>)
    edges(id PK, src, trgt, type, rel, src_layer, trgt_layer, ... <attrs>)

Why two tables: matches the in-memory NetworkX model used by
``firegraph.graph.local_graph_utils.GUtils`` -- a node and an edge each carry
an attribute dict; here that same dict becomes a row whose columns mirror
the keys. Column set grows on the fly because the underlying
``DBManager.insert`` calls ``_duck_insert_col`` for every attr key it has
not seen before, and JSON-encodes complex values so round-trip is lossless.

This module is intentionally tiny -- it only declares
  * the two table names + their seed (PK + structural) columns
  * a thin ``GraphStore`` with the check / add / save / edit verbs that
    ``GUtils.add_node`` / ``add_edge`` / ``update_node`` / ``delete_node``
    expect (each verb is one-line forwarding into ``DBManager``).

All heavy lifting (SQL, type coercion, dynamic columns) stays in
``firegraph._db.manager.DBManager``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Optional, Set

from firegraph._db.manager import DBManager, get_db_manager


# canonical table names -- exposed so consumers can introspect / reset them
NODES_TABLE = "nodes"
EDGES_TABLE = "edges"

# seed schemas: only the structural columns; everything else is added on demand
# (DBManager.insert -> _duck_insert_col) so rows mirror the G-instance attrs.
_NODE_BASE_SCHEMA: Dict[str, str] = {
    "id": "VARCHAR PRIMARY KEY",
    "type": "VARCHAR",
}

_EDGE_BASE_SCHEMA: Dict[str, str] = {
    "id": "VARCHAR PRIMARY KEY",
    "src": "VARCHAR",
    "trgt": "VARCHAR",
    "type": "VARCHAR",
    "rel": "VARCHAR",
    "src_layer": "VARCHAR",
    "trgt_layer": "VARCHAR",
}


class GraphStore:
    """Two-table (nodes, edges) DuckDB facade used by ``GUtils``.

    Verbs (mapped 1:1 to the GUtils mutation methods):
      * ``has_node(id)`` / ``has_edge(id)``                 -> CHECK
      * ``upsert_node(attrs)`` / ``upsert_edge(attrs)``     -> ADD / SAVE
      * ``update_node(attrs)``                              -> EDIT (merge)
      * ``delete_node(id)`` / ``delete_edge(id)``           -> remove
    """

    def __init__(self, db: Optional[DBManager] = None) -> None:
        # accept an injected manager (test / shared connection); default to singleton
        self._db = db or get_db_manager()
        # idempotent: ensures the two tables exist before any verb runs
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Create the two canonical tables if missing (no-op when present)."""
        self._db.create_table(NODES_TABLE, _NODE_BASE_SCHEMA)
        self._db.create_table(EDGES_TABLE, _EDGE_BASE_SCHEMA)

    # ----------------------------------------------------------------------
    # CHECK
    # ----------------------------------------------------------------------
    def has_node(self, nid: str) -> bool:
        """Return True iff a row with id=nid exists in the nodes table."""
        return self._exists(NODES_TABLE, nid)

    def has_edge(self, eid: str) -> bool:
        """Return True iff a row with id=eid exists in the edges table."""
        return self._exists(EDGES_TABLE, eid)

    def _exists(self, table: str, rid: str) -> bool:
        # tiny SELECT 1 helper -- safer than the legacy duck_row_from_id
        # builder which assumes status / created_at columns we do not have
        try:
            rows = self._db.run_query(
                f"SELECT id FROM {table} WHERE id = ? LIMIT 1",
                params=[rid],
                conv_to_dict=False,
            )
            return bool(rows)
        except Exception as e:
            # missing table at startup race etc. -- log but stay non-fatal
            print(f"[GraphStore._exists] {table} probe failed for {rid}: {e}")
            return False


    def upsert_nid_batch(self, batch_ids) -> bool:
        """Insert or replace a node row. ``attrs`` must contain ``id``."""
        # DBManager.insert auto-adds new columns and json-encodes non-scalar values
        return self._db.insert(
            NODES_TABLE,
            rows=[dict(id=nid) for nid in batch_ids],
            upsert=True,
            conflict_columns=("id",),
        )

    def upsert_edge(self, attrs: Dict[str, Any]) -> bool:
        """Insert or replace an edge row. ``attrs`` must contain ``id``."""
        if not attrs.get("id"):
            return False
        return self._db.insert(
            EDGES_TABLE,
            rows=dict(attrs),
            upsert=True,
            conflict_columns=("id",),
        )

    # ----------------------------------------------------------------------
    # EDIT  (merge-then-upsert so we never lose previously stored fields)
    # ----------------------------------------------------------------------
    def update_node(self, attrs: Dict[str, Any]) -> bool:
        """Merge ``attrs`` with the existing row (if any) and upsert the result."""
        nid = attrs.get("id")
        if not nid:
            return False
        existing = self._fetch_row(NODES_TABLE, nid)
        merged = {**existing, **attrs} if existing else dict(attrs)
        return self.upsert_node(merged)

    def update_edge(self, attrs: Dict[str, Any]) -> bool:
        """Merge ``attrs`` with the existing edge row (if any) and upsert."""
        eid = attrs.get("id")
        if not eid:
            return False
        existing = self._fetch_row(EDGES_TABLE, eid)
        merged = {**existing, **attrs} if existing else dict(attrs)
        return self.upsert_edge(merged)

    def _fetch_row(self, table: str, rid: str) -> Dict[str, Any]:
        # direct SELECT * by id; returns {} when missing
        try:
            rows = self._db.run_query(
                f"SELECT * FROM {table} WHERE id = ? LIMIT 1",
                params=[rid],
                conv_to_dict=True,
            )
            return dict(rows[0]) if rows else {}
        except Exception as e:
            print(f"[GraphStore._fetch_row] {table} read failed for {rid}: {e}")
            return {}

    # ----------------------------------------------------------------------
    # DELETE
    # ----------------------------------------------------------------------
    def delete_node(self, nid: str) -> None:
        try:
            self._db.delete(NODES_TABLE, "id = ?", [nid])
        except Exception as e:
            print(f"[GraphStore.delete_node] {nid}: {e}")

    def delete_edge(self, eid: str) -> None:
        try:
            self._db.delete(EDGES_TABLE, "id = ?", [eid])
        except Exception as e:
            print(f"[GraphStore.delete_edge] {eid}: {e}")

    # ----------------------------------------------------------------------
    # HYDRATE  (cache layer used before any web fetch)
    # ----------------------------------------------------------------------
    def hydrate(self, g, ids: Iterable[str]) -> Set[str]:
        """Inject cached nodes (+ all touching edges) for ``ids`` into ``g.G``.

        Returns the set of ids that were found in the cache. Pre-fetch sites
        can ``ids = [i for i in ids if i not in cached]`` (or update their
        own ``_SEEN`` dedup set) and skip the matching HTTP requests.

        Edges are pulled when ``src`` OR ``trgt`` matches a cached id so the
        full neighborhood of each cache hit is restored in one round-trip.
        """
        # normalize input -- dedupe + drop empties
        ids_list = list({str(i) for i in ids if i})
        if not ids_list:
            return set()

        # CHECK: which of the requested ids exist as cached node rows
        nodes_ph = ",".join(["?"] * len(ids_list))
        try:
            node_rows = self._db.run_query(
                f"SELECT * FROM {NODES_TABLE} WHERE id IN ({nodes_ph})",
                params=ids_list,
                conv_to_dict=True,
            )
        except Exception as e:
            print(f"[GraphStore.hydrate] nodes probe failed: {e}")
            return set()

        if not node_rows:
            return set()

        cached: Set[str] = {r["id"] for r in node_rows if r.get("id")}

        # related edges in one query (src OR trgt in cached set)
        cached_list = list(cached)
        edges_ph = ",".join(["?"] * len(cached_list))
        try:
            edge_rows = self._db.run_query(
                f"SELECT * FROM {EDGES_TABLE} "
                f"WHERE src IN ({edges_ph}) OR trgt IN ({edges_ph})",
                params=cached_list + cached_list,
                conv_to_dict=True,
            )
        except Exception as e:
            print(f"[GraphStore.hydrate] edges probe failed: {e}")
            edge_rows = []

        # ADD into G with DB sync temporarily off so we do not write what we
        # just read (cheap pause; original flag is restored in ``finally``)
        prev_flag = getattr(g, "enable_db_store", False)
        g.enable_db_store = False
        try:
            for row in node_rows:
                try:
                    attrs = _decode_row(row)
                    # Mark every hydrated node so downstream fetchers can skip
                    # data-source requests for entries that came from the cache.
                    attrs["cached"] = True
                    g.add_node(attrs)
                except Exception as e:
                    print(f"[GraphStore.hydrate] add_node({row.get('id')}) failed: {e}")
            for row in edge_rows:
                attrs = _decode_row(row)
                try:
                    g.add_edge(
                        src=attrs.get("src"),
                        trgt=attrs.get("trgt"),
                        attrs=attrs,
                    )
                except Exception as e:
                    print(f"[GraphStore.hydrate] add_edge({row.get('id')}) failed: {e}")
        finally:
            g.enable_db_store = prev_flag

        print(
            f"[GraphStore.hydrate] {len(cached)} nodes + {len(edge_rows)} edges restored from cache"
        )
        return cached


def _decode_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Reverse ``DBManager.insert``'s json.dumps: strings that parse as JSON
    become their original value, everything else is returned as-is."""
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if v is None:
            continue
        if isinstance(v, str):
            # try-decode so numbers / lists / dicts come back as themselves
            try:
                v = json.loads(v)
            except (json.JSONDecodeError, ValueError):
                pass
        out[k] = v
    return out
