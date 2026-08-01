from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Iterable


class RegistryError(RuntimeError):
    pass


class DependencyCycleError(RegistryError):
    pass


@dataclass(frozen=True, slots=True)
class ComponentContract:
    key: str
    form_class: type | None = None
    serializer_class: type | None = None
    view_class: type | None = None
    provides: frozenset[str] = frozenset()
    requires: frozenset[str] = frozenset()


class ComponentRegistry:
    def __init__(self):
        self._contracts: dict[str, ComponentContract] = {}
        self._lock = RLock()

    def register(self, contract: ComponentContract, *, replace: bool = False):
        with self._lock:
            current = self._contracts.get(contract.key)
            if current is not None and not replace:
                if current == contract:
                    return contract
                raise RegistryError(f"Component already registered: {contract.key}")
            self._contracts[contract.key] = contract
            try:
                self.validate()
            except Exception:
                if current is None:
                    self._contracts.pop(contract.key, None)
                else:
                    self._contracts[contract.key] = current
                raise
        return contract

    def unregister(self, key: str):
        with self._lock:
            return self._contracts.pop(key, None)

    def get(self, key: str):
        try:
            return self._contracts[key]
        except KeyError as exc:
            raise RegistryError(f"Unknown component: {key}") from exc

    def all(self):
        return tuple(self._contracts[key] for key in sorted(self._contracts))

    def provider_for(self, data_key: str):
        providers = [item for item in self.all() if data_key in item.provides]
        if len(providers) > 1:
            raise RegistryError(f"Multiple providers for {data_key}: {[item.key for item in providers]}")
        return providers[0] if providers else None

    def dependencies(self, component_key: str):
        contract = self.get(component_key)
        return frozenset(
            provider.key for key in contract.requires
            if (provider := self.provider_for(key)) is not None
        )

    def dependents(self, component_key: str, *, transitive: bool = True):
        found: set[str] = set()
        pending = [component_key]
        while pending:
            current = pending.pop()
            direct = {item.key for item in self.all() if current in self.dependencies(item.key)}
            new = direct - found
            found.update(new)
            if transitive:
                pending.extend(new)
        found.discard(component_key)
        return frozenset(found)

    def topological_order(self, keys: Iterable[str] | None = None):
        selected = set(keys or (item.key for item in self.all()))
        incoming = {key: set(self.dependencies(key)) & selected for key in selected}
        ready = sorted(key for key, dependencies in incoming.items() if not dependencies)
        ordered = []
        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for key in sorted(incoming):
                if current in incoming[key]:
                    incoming[key].remove(current)
                    if not incoming[key] and key not in ordered and key not in ready:
                        ready.append(key)
                        ready.sort()
        if len(ordered) != len(selected):
            raise DependencyCycleError(f"Component dependency cycle: {sorted(selected - set(ordered))}")
        return tuple(ordered)

    def validate(self):
        seen = {}
        for contract in self.all():
            for data_key in contract.provides:
                if data_key in seen:
                    raise RegistryError(f"Data key {data_key} is provided by both {seen[data_key]} and {contract.key}")
                seen[data_key] = contract.key
        self.topological_order()


registry = ComponentRegistry()


def register_component(key: str, *, form_class=None, serializer_class=None,
                       view_class=None, provides=(), requires=(), replace=False):
    return registry.register(ComponentContract(
        key=key,
        form_class=form_class,
        serializer_class=serializer_class,
        view_class=view_class,
        provides=frozenset(provides),
        requires=frozenset(requires),
    ), replace=replace)
