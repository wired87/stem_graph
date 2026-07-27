import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path


class FakeFetcher:
    def __init__(self, responses):
        self.responses = list(responses)
        self.queries = []

    async def search(self, query, size=500):
        self.queries.append(query)
        return self.responses.pop(0)


class FakeGraph:
    def __init__(self, nodes):
        self._nodes = {node_id: dict(attrs) for node_id, attrs in nodes}
        self.edges = []
        self.G = self

    def nodes(self, data=False):
        return list(self._nodes.items()) if data else list(self._nodes)

    def has_node(self, node_id):
        return node_id in self._nodes

    def add_node(self, attrs):
        self._nodes[attrs["id"]] = dict(attrs)

    def add_edge(self, src, trgt, attrs):
        self.edges.append((src, trgt, dict(attrs)))

    def get_node(self, value=None, key=None):
        for node_id, attrs in self._nodes.items():
            if attrs.get(key) == value or node_id == value:
                return {"id": node_id, **attrs}
        return None


def load_module(fetcher):
    protein = types.ModuleType("protein")
    processors = types.ModuleType("protein.processors")
    single = types.ModuleType("protein.processors.get_single_protein")
    single._UNIPROT_FETCHER = fetcher
    sys.modules.update({
        "protein": protein,
        "protein.processors": processors,
        "protein.processors.get_single_protein": single,
    })
    path = Path(__file__).resolve().parents[1] / "protein/processors/protein_from_gene.py"
    spec = importlib.util.spec_from_file_location("protein_retrieval_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProteinRetrievalTests(unittest.TestCase):
    def test_strict_result_is_scored_and_linked(self):
        protein = {
            "primaryAccession": "P35498",
            "genes": [{"geneName": {"value": "SCN1A"}}],
            "keywords": [{"id": "KW-0407", "name": "Ion channel"}],
            "uniProtKBCrossReferences": [{"database": "GO", "id": "GO:0007268"}],
            "comments": [{"texts": [{"value": "Expressed in brain"}]}],
        }
        fetcher = FakeFetcher([{"results": [protein]}])
        module = load_module(fetcher)
        graph = FakeGraph([
            ("ENSG1", {"type": "GENE", "symbol": "SCN1A"}),
            ("KW-0407", {"type": "KEYWORD", "sub_type": "META"}),
            ("Brain", {"type": "TISSUE", "sub_type": "UNIPROT"}),
            ("GO:0007268", {"type": "GO_TERM"}),
        ])

        result = asyncio.run(module.fetch_uniprot_protein(graph))

        self.assertEqual(result["protein_count"], 1)
        self.assertEqual(result["retrieval_strategy"], "strict")
        self.assertEqual(graph._nodes["P35498"]["protein_score"], 1.0)
        self.assertTrue(any(edge[2]["rel"] == "encodes" for edge in graph.edges))
        self.assertTrue(any(edge[2]["rel"] == "supports" for edge in graph.edges))

    def test_empty_strict_result_retries_with_relaxed_query(self):
        fetcher = FakeFetcher([
            {"results": []},
            {"results": [{"primaryAccession": "P1", "keywords": []}]},
        ])
        module = load_module(fetcher)
        graph = FakeGraph([
            ("ENSG1", {"type": "GENE", "Gene": "SCN1A"}),
            ("KW-0407", {"type": "KEYWORD", "sub_type": "META"}),
        ])

        result = asyncio.run(module.fetch_uniprot_protein(graph))

        self.assertEqual(result["retrieval_strategy"], "relaxed")
        self.assertEqual(result["protein_count"], 1)
        self.assertEqual(len(fetcher.queries), 2)
        self.assertIn(" OR ", fetcher.queries[1])

    def test_empty_response_is_a_valid_zero_result(self):
        fetcher = FakeFetcher([{}])
        module = load_module(fetcher)
        graph = FakeGraph([])

        result = asyncio.run(module.fetch_uniprot_protein(graph))

        self.assertEqual(result["protein_count"], 0)
        self.assertEqual(result["retrieval_strategy"], "strict")


if __name__ == "__main__":
    unittest.main()
