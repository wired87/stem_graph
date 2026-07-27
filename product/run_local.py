"""Public StemGraph facade and workflow entry point."""

from __future__ import annotations

import tempfile
from pathlib import Path

from firegraph.graph import GUtils
from product.workflows.annotation import annotate_result
from product.workflows.calling import build_calls, find_call
from product.workflows.function_filter import run_function_filter
from product.workflows.inputs import collect_files, prepare_inputs
from product.workflows.pipeline import run_pipeline


DEFAULT_EXAMPLE_DIR = Path(__file__).resolve().parent / "executable" / "example_data"


def get_files(files=None, dir=None):
    """Backwards-compatible public input collector."""
    return collect_files(files=files, directory=dir)


def run_local(files, annotate_variants=True, cfg=None, **annotation_options):
    """Convenience API returning a fully built ``StemGraph`` instance."""
    return StemGraph().main(
        files,
        annotate_variants=annotate_variants,
        cfg=cfg,
        **annotation_options,
    )


class StemGraph(GUtils):
    """Thin graph facade delegating all domain logic to workflow modules."""

    def __init__(self, cfg=None):
        super().__init__()
        self.cfg = cfg
        self.tmp_store = tempfile.TemporaryDirectory()
        root = Path(self.tmp_store.name)
        self.dirs = {
            "input": str(root / "input"),
            "raw_input": str(root / "input" / "raw"),
            "output": str(root / "output"),
            "logs": str(root / "logs"),
            "time": str(root / "time"),
        }
        for directory in self.dirs.values():
            Path(directory).mkdir(parents=True, exist_ok=True)

    def close(self):
        self.tmp_store.cleanup()

    # Workflow group 1: input registration and validation.
    def input_workflow(self, files):
        return prepare_inputs(self, files)

    # Workflow group 2: channel alignment, calling and call graph creation.
    def calling_workflow(self, idat_pairs):
        return build_calls(self, idat_pairs)

    # Workflow group 3: remote variant/effect enrichment.
    def annotation_workflow(self, result_id, **options):
        return annotate_result(self, result_id, **options)

    # Workflow group 4: GO-term based functional gene filtering.
    def function_filter_workflow(self, cfg=None, **options):
        return run_function_filter(self, cfg or self.cfg, **options)

    # Read API delegated to the calling application.
    def get_call(self, index, sample_id=None):
        return find_call(self, index=index, sample_id=sample_id)

    def main(
        self,
        files,
        annotate_variants=True,
        cfg=None,
        function_filter_options=None,
        **annotation_options,
    ):
        self.workflow_result = run_pipeline(
            self,
            files,
            annotate_variants=annotate_variants,
            cfg=cfg or self.cfg,
            function_filter_options=function_filter_options,
            **annotation_options,
        )
        return self


if __name__ == "__main__":
    graph = StemGraph()
    try:
        graph.main(get_files(dir=DEFAULT_EXAMPLE_DIR))
        graph.print_status_G()
    finally:
        graph.close()
