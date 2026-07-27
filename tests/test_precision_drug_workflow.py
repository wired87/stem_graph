import unittest

from drug_master.precision_workflow import (
    build_precision_drug_graph,
    classify_vep_variant,
)


class NodeView:
    def __init__(self, graph):
        self.graph = graph

    def get(self, node_id, default=None):
        return self.graph.node_data.get(node_id, default)

    def __call__(self, data=False):
        return (
            list(self.graph.node_data.items())
            if data else list(self.graph.node_data)
        )


class TinyGraph:
    def __init__(self):
        self.node_data = {}
        self.edge_data = {}
        self.nodes = NodeView(self)

    def has_node(self, node_id):
        return node_id in self.node_data

    def neighbors(self, node_id):
        out = []
        for source, target in self.edge_data:
            if source == node_id:
                out.append(target)
            elif target == node_id:
                out.append(source)
        return out

    def get_edge_data(self, source, target):
        return (
            self.edge_data.get((source, target))
            or self.edge_data.get((target, source))
        )


class TinyGUtils:
    def __init__(self):
        self.G = TinyGraph()

    def add_node(self, attrs):
        self.G.node_data.setdefault(attrs["id"], {}).update(attrs)

    def add_edge(self, source, target, attrs):
        self.G.edge_data[(source, target)] = dict(attrs)


class PrecisionDrugWorkflowTests(unittest.TestCase):
    def test_builds_index_stable_multi_target_research_plan(self):
        graph = TinyGUtils()
        result = build_precision_drug_graph(
            graph,
            ["P11111", "P22222"],
            target_records={
                "P11111": [{"target_chembl_id": "CHEMBL_T1"}],
                "P22222": [{"target_chembl_id": "CHEMBL_T2"}],
            },
            pathway_rows={
                "P11111": [{
                    "source": "P11111",
                    "target": "PX",
                    "consensus_stimulation": True,
                }, {
                    "source": "PX",
                    "target": "P22222",
                    "consensus_inhibition": True,
                }],
            },
            candidates_by_target={
                "CHEMBL_T1": [
                    {
                        "molecule_chembl_id": "DRUG_BAD_DIRECTION",
                        "activity_value": 1,
                        "activity_unit": "nM",
                        "mechanism": "agonist",
                        "confidence": 1,
                    },
                    {
                        "molecule_chembl_id": "DRUG_T1",
                        "activity_value": 10,
                        "activity_unit": "nM",
                        "mechanism": "inhibitor",
                        "confidence": 0.9,
                    },
                ],
                "CHEMBL_T2": [{
                    "molecule_chembl_id": "DRUG_T2",
                    "activity_value": 100,
                    "activity_unit": "nM",
                    "mechanism": "activator",
                    "confidence": 0.8,
                }],
            },
            vep_annotations=[{
                "id": "VAR1",
                "protein_id": "P11111",
                "impact": "HIGH",
                "clin_sig": ["pathogenic"],
                "disease": "Example disease",
                "variant_effect": "gain_of_function",
            }],
            sex="female",
        )

        self.assertEqual(result["target_ids"], ["CHEMBL_T1", "CHEMBL_T2"])
        self.assertEqual(result["harmful_variant_count"], 1)
        self.assertFalse(result["clinical_use"])
        self.assertFalse(result["sex_adjustment_applied"])
        self.assertEqual(len(graph.G.node_data["P11111"]["influence"]), 2)
        self.assertIn("DRUG_T1", result["drug_ids"])
        self.assertNotIn("DRUG_BAD_DIRECTION", result["drug_ids"])
        for target_id in result["target_ids"]:
            molecule_neighbors = [
                node for node in graph.G.neighbors(target_id)
                if graph.G.node_data[node].get("type") == "MOLECULE"
            ]
            self.assertLessEqual(len(molecule_neighbors), 1)
        for drug_id in result["drug_ids"]:
            self.assertTrue(graph.G.node_data[drug_id]["not_a_clinical_dose"])
            self.assertIsNone(graph.G.node_data[drug_id]["dose_unit"])

    def test_high_impact_without_disease_is_not_harmful(self):
        risk = classify_vep_variant({
            "id": "VAR2",
            "protein_id": "P11111",
            "impact": "HIGH",
            "consequence": "stop_gained",
        })
        self.assertFalse(risk.harmful)
        self.assertFalse(risk.disease_associated)


if __name__ == "__main__":
    unittest.main()
