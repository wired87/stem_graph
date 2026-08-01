from django.contrib.auth import get_user_model
from django.test import TestCase

from state_manager.models import WorkspaceState
from state_manager.registry import ComponentContract, registry
from state_manager.services import RevisionConflict, resolve_required_data, update_component_state


class StateServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="state@example.com", password="test")
        self.workspace = WorkspaceState.objects.create(owner=self.user)
        registry.unregister("test.source")
        registry.unregister("test.consumer")
        registry.register(ComponentContract(key="test.source", provides=frozenset({"test.value"})))
        registry.register(ComponentContract(key="test.consumer", requires=frozenset({"test.value"})))

    def tearDown(self):
        registry.unregister("test.consumer")
        registry.unregister("test.source")

    def test_revision_and_requirement_resolution(self):
        _, workspace = update_component_state(
            workspace=self.workspace, component_key="test.source",
            data={"test.value": "hello"}, expected_revision=0,
        )
        resolved, missing = resolve_required_data(workspace=workspace, component_key="test.consumer")
        self.assertEqual(workspace.revision, 1)
        self.assertEqual(resolved, {"test.value": "hello"})
        self.assertEqual(missing, ())

    def test_stale_revision_is_rejected(self):
        update_component_state(workspace=self.workspace, component_key="test.source", data={"test.value": "first"})
        with self.assertRaises(RevisionConflict):
            update_component_state(workspace=self.workspace, component_key="test.source",
                                   data={"test.value": "stale"}, expected_revision=0)
