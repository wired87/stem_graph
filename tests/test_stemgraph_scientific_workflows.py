import unittest

import networkx as nx
import numpy as np

from product.workflows.disease_treatment import build_disease_treatment_nodes
from product.workflows.function_filter import run_function_filter
from product.stem_graph_table import build_stem_graph_table


class Graph:
    def __init__(self):
        self.G = nx.Graph()

    def add_node(self, attrs):
        node_id = attrs["id"]
        self.G.add_node(node_id, **attrs)

    def add_edge(self, source, target, attrs):
        self.G.add_edge(source, target, **attrs)

    def update_node(self, attrs):
        self.G.nodes[attrs["id"]].update(attrs)

    def get_node(self, node_id):
        return self.G.nodes[node_id]


class ScientificWorkflowTests(unittest.TestCase):
    def test_go_indices_gene_order_and_unlabelled_terms(self):
        graph = Graph()
        graph.add_node({
            "id": "ENSG2", "type": "GENE",
            "xrefs": [{"primary_id": "GO:0000002", "description": "axon transport"}],
        })
        graph.add_node({
            "id": "ENSG1", "type": "GENE",
            "xrefs": [{"primary_id": "GO:0000001"}],
        })

        def embed(values):
            return np.asarray([
                [1.0, 0.0] if value in {"axon transport", "transport"} else [0.0, 1.0]
                for value in values
            ])

        mask = run_function_filter(
            graph,
            {"protein": {
                "functional_annotation": ["transport"],
                "function_similarity_threshold": 0.9,
                "fetch_go_xrefs": False,
            }},
            embed_batch_fn=embed,
        )
        self.assertEqual(graph.get_node("gene_to_goterm")["genes"], ["ENSG2", "ENSG1"])
        self.assertEqual(graph.get_node("goterm")["index_by_id"], {
            "GO:0000001": 0, "GO:0000002": 1,
        })
        self.assertEqual(mask, [0, None])
        self.assertEqual(
            graph.get_node("goterm_function_alignment")["unlabelled_goterm_indices"],
            [0],
        )

    def test_treatment_requires_pathogenicity_target_and_curated_semantics(self):
        graph = Graph()
        graph.add_node({
            "id": "VAR1", "type": "VARIANT",
            "annotation": {
                "clin_sig": ["pathogenic"], "disease": "D",
                "gene_id": "ENSG1",
            },
        })
        config = {"treatment": {
            "pharmacogenetic_entries": [{
                "variantId": "VAR1", "directionality": "INCREASE",
                "drugs": [{"drugId": "CHEMBL1"}],
            }],
            "mechanism_entries": [{
                "chemblIds": ["CHEMBL1"], "targets": ["ENSG1"],
                "actionType": "INHIBITOR",
            }],
        }}
        self.assertEqual(build_disease_treatment_nodes(graph, config), [[]])
        self.assertFalse(
            graph.G.nodes["VAR_TREATMENT_DRUG_IDS"]["inference_allowed"]
        )

        config["treatment"]["direction_semantics"] = "target_activity"
        self.assertEqual(build_disease_treatment_nodes(graph, config), [[0]])
        self.assertEqual(graph.G.nodes["variant_dir"]["data"], [0])
        self.assertEqual(graph.G.nodes["DRUGIDS"]["data"], ["CHEMBL1"])

    def test_conflicting_direction_is_unknown(self):
        graph = Graph()
        graph.add_node({
            "id": "VAR1", "type": "VARIANT",
            "annotation": {"clin_sig": ["pathogenic"], "disease": "D"},
        })
        build_disease_treatment_nodes(graph, {"treatment": {
            "direction_semantics": "target_activity",
            "pharmacogenetic_entries": [
                {"variantId": "VAR1", "directionality": "INCREASE"},
                {"variantId": "VAR1", "directionality": "DECREASE"},
            ],
        }})
        self.assertEqual(graph.G.nodes["variant_dir"]["data"], [None])

    def test_vep_colocated_clinvar_and_snake_case_mechanism(self):
        graph = Graph()
        graph.add_node({
            "id": "VAR1", "type": "VARIANT",
            "annotation": {
                "most_severe_consequence": "missense_variant",
                "colocated_variants": [{
                    "clin_sig": ["pathogenic"],
                    "phenotype_or_disease": 1,
                }],
                "gene_id": "ENSG1",
            },
        })
        accepted = build_disease_treatment_nodes(graph, {"treatment": {
            "direction_semantics": "target_activity",
            "pharmacogenetic_entries": [{
                "variantId": "VAR1",
                "directionality": "INCREASE",
                "drugs": [{"drugId": "CHEMBL1"}],
            }],
            "mechanism_entries": [{
                "molecule_chembl_id": "CHEMBL1",
                "targetId": "ENSG1",
                "action_type": "INHIBITOR",
            }],
        }})
        self.assertEqual(graph.G.nodes["harmful_variation"]["data"], [0])
        self.assertEqual(accepted, [[0]])

    def test_stem_graph_table_preserves_tdx_edges_and_case_legend(self):
        graph = Graph()
        graph.add_node({
            "id": "result:0",
            "type": "SCORE_RESULT",
            "data": [{"call_id": "call:0", "score": 0.91}],
        })
        graph.add_node({
            "id": "harmful_variation",
            "type": "HARMFUL_VARIATION",
            "data": [0, None],
            "semantics": "0=explicit disease-associated pathogenic evidence; None=not established",
        })
        graph.add_edge(
            "result:0",
            "harmful_variation",
            {"rel": "derived_batch", "src_layer": "SCORE_RESULT", "trgt_layer": "HARMFUL_VARIATION"},
        )

        table = build_stem_graph_table(graph.G)

        self.assertEqual(table["rows"][0]["tdx"], 0)
        self.assertEqual(table["rows"][0]["item_id"], "call:0")
        self.assertEqual(table["tdx_groups"][0]["items"]["result:0"]["score"], 0.91)
        self.assertEqual(table["tdx_groups"][0]["items"]["harmful_variation"], 0)
        self.assertEqual(
            table["legend"]["node_value_meanings"]["harmful_variation"]["values"]["0"],
            "explicit disease-associated pathogenic evidence",
        )
        self.assertEqual(
            table["rows"][1]["value_label"],
            "explicit disease-associated pathogenic evidence",
        )
        self.assertEqual(table["physical_edges"][0]["rel"], "derived_batch")


if __name__ == "__main__":
    unittest.main()
