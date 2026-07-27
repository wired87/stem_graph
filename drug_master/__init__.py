"""Canonical drug discovery and research scoring package."""

__all__ = ["build_precision_drug_graph"]


def __getattr__(name):
    if name == "build_precision_drug_graph":
        from drug_master.precision_workflow import build_precision_drug_graph
        return build_precision_drug_graph
    raise AttributeError(name)
