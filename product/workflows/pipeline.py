"""Top-level composition of the independent StemGraph workflow groups."""

from .annotation import annotate_result
from .calling import build_calls
from .disease_treatment import (
    build_disease_treatment_nodes,
    disease_treatment_enabled,
)
from .function_filter import function_filter_enabled, run_function_filter
from .inputs import prepare_inputs


def run_input_workflow(graph, files):
    return prepare_inputs(graph, files)


def run_calling_workflow(graph, idat_pairs):
    return build_calls(graph, idat_pairs)


def run_annotation_workflow(graph, result_ids, **annotation_options):
    return {
        result_id: annotate_result(graph, result_id, **annotation_options)
        for result_id in result_ids
    }


def run_function_filter_workflow(graph, cfg, **filter_options):
    return run_function_filter(graph, cfg, **filter_options)


def run_pipeline(
    graph,
    files,
    annotate_variants=True,
    cfg=None,
    function_filter_options=None,
    **annotation_options,
):
    pairs = run_input_workflow(graph, files)
    results = run_calling_workflow(graph, pairs)
    annotations = (
        run_annotation_workflow(graph, results, **annotation_options)
        if annotate_variants
        else {}
    )
    function_filter = (
        run_function_filter_workflow(
            graph,
            cfg,
            **(function_filter_options or {}),
        )
        if function_filter_enabled(cfg)
        else None
    )
    disease_treatment = (
        build_disease_treatment_nodes(graph, cfg)
        if disease_treatment_enabled(cfg)
        else None
    )
    return {
        "idat_pairs": pairs,
        "result_ids": results,
        "annotations": annotations,
        "function_filter": function_filter,
        "disease_treatment": disease_treatment,
    }
