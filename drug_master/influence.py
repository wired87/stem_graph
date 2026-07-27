"""Shared signed pathway influence rules."""


def get_edge_multiplier(edge_attrs: dict) -> float:
    if edge_attrs.get("consensus_stimulation"):
        return 1.0
    if edge_attrs.get("consensus_inhibition"):
        return -1.0
    if edge_attrs.get("consensus_direction"):
        return 0.5
    if edge_attrs.get("omnipath_stimulation"):
        return 0.75
    if edge_attrs.get("omnipath_inhibition"):
        return -0.75
    return 0.0
