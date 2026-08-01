from django.test import SimpleTestCase

from state_manager.registry import ComponentContract, ComponentRegistry, DependencyCycleError


class RegistryTests(SimpleTestCase):
    def test_dependency_order_and_dependents(self):
        components = ComponentRegistry()
        components.register(ComponentContract(key="source", provides=frozenset({"value"})))
        components.register(ComponentContract(key="consumer", requires=frozenset({"value"})))
        self.assertEqual(components.topological_order(), ("source", "consumer"))
        self.assertEqual(components.dependents("source"), frozenset({"consumer"}))

    def test_failed_cycle_registration_is_rolled_back(self):
        components = ComponentRegistry()
        components.register(ComponentContract(
            key="a", provides=frozenset({"a"}), requires=frozenset({"b"})
        ))
        with self.assertRaises(DependencyCycleError):
            components.register(ComponentContract(
                key="b", provides=frozenset({"b"}), requires=frozenset({"a"})
            ))
        self.assertEqual(tuple(item.key for item in components.all()), ("a",))
