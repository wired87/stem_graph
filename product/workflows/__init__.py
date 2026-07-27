"""Composable workflow steps used by :class:`product.run_local.StemGraph`."""

from .annotation import annotate_result
from .calling import build_calls, find_call
from .inputs import collect_files, prepare_inputs
from .function_filter import run_function_filter
from .pipeline import run_pipeline

__all__ = [
    "annotate_result",
    "build_calls",
    "collect_files",
    "find_call",
    "prepare_inputs",
    "run_function_filter",
    "run_pipeline",
]
