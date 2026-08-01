from django.test import Client, TestCase


class StateApiTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost")

    def test_registry_and_anonymous_session_are_exposed(self):
        registry_response = self.client.get("/api/state/registry/")
        self.assertEqual(registry_response.status_code, 200)
        keys = {item["key"] for item in registry_response.json()["components"]}
        self.assertEqual(keys, {"protein.prediction", "drug.precision", "product.stem_graph"})
        self.assertIn("X-State-ID", registry_response)

        session_response = self.client.get("/api/state/session/")
        self.assertEqual(session_response.status_code, 200)
        self.assertEqual(session_response.json()["id"], registry_response["X-State-ID"])

    def test_component_state_resolves_downstream_requirements(self):
        update = self.client.put(
            "/api/state/components/protein.prediction/",
            data={"data": {"protein.candidates": ["Q15822"]}, "expected_revision": 0},
            content_type="application/json",
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["workspace_revision"], 1)
        self.assertEqual(update.json()["dependents"], ["drug.precision"])

        requirements = self.client.get("/api/state/components/drug.precision/requirements/")
        self.assertEqual(requirements.status_code, 200)
        self.assertEqual(requirements.json()["data"], {"protein.candidates": ["Q15822"]})
        self.assertEqual(requirements.json()["missing"], [])
