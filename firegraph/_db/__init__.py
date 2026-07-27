"""
firegraph._db -- DuckDB persistence layer for the firegraph package.

User prompt (Cursor session):
    "allocate _db logic to firegraph and include a check add, save, edit
     process in each add_node, add_edge, and update_node-process.
     (The db layer includes just two tables (nodes and edges) where specific
     rows include the same fields as in the G-instance."

Original note preserved:
    MIT RAY UND ANDERN TOOLS KANN ICH KOMPLETT GCP NACHABUEN UND FAHRE SO VIEL GUENSTIGER
    pip install duckdb
    - seamless integration with bigquery sql

Public surface:
  * ``DBManager`` / ``get_db_manager`` -- generic DuckDB connection + DDL/DML
  * ``GraphStore``                     -- two-table (nodes, edges) facade used
                                          by ``firegraph.graph.local_graph_utils.GUtils``
"""

from firegraph._db.manager import DBManager, get_db_manager, db_check, db_status
from firegraph._db.graph_store import GraphStore, NODES_TABLE, EDGES_TABLE

__all__ = [
    "DBManager",
    "get_db_manager",
    "db_check",
    "db_status",
    "GraphStore",
    "NODES_TABLE",
    "EDGES_TABLE",
]
