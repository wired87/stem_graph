# StemGraph workflow modules

`StemGraph` is only the public graph facade. Domain behavior belongs to these
modules:

- `inputs.py`: collect files, parse metadata/reference content, validate files,
  and pair Green/Red IDAT channels.
- `calling.py`: align IDAT/BPM/EGT indices, call genotypes, create `SAMPLE`,
  `SCORE_RESULT`, and indexed `VARIANT_CALL` nodes.
- `annotation.py`: build Ensembl VEP requests and create `VARIANT`,
  `VARIANT_EFFECT`, `GENE`, and `PROTEIN` nodes.
- `function_filter.py`: optionally collect Ensembl GO xrefs, build stable GO
  indices, align GO terms to configured functions, and produce the gene mask.
- `pipeline.py`: compose the three workflow groups without implementing domain
  behavior.

Public use:

```python
from product.run_local import StemGraph, get_files

graph = StemGraph()
graph.main(get_files(dir="input"), annotate_variants=True)
call = graph.get_call(index=42)
```

Individual workflow groups can be executed explicitly:

```python
pairs = graph.input_workflow(files)
result_ids = graph.calling_workflow(pairs)
annotations = graph.annotation_workflow(result_ids[0])
```

Optional protein/function configuration:

```python
cfg = {
    "protein": {
        # Parameters compatible with protein.workflow.predict_proteins:
        "functional_annotation": ["synaptic transmission"],
        "tissue": "Thalamus",
        "protein_type": "Ion channel",

        # Function-filter parameters:
        "function_similarity_threshold": 0.75,
        "fetch_go_xrefs": True,
        "go_fetch_concurrency": 8,
        # Optional already-received Ensembl records keyed by gene id:
        "ensembl_entries": {},
    }
}

graph = StemGraph(cfg=cfg)
graph.main(files)
```

The filter creates four index-stable nodes:

- `goterm.data`: canonical GO rows with `idx`.
- `gene_to_goterm.data`: GO-index lists in `gene_to_goterm.genes` order.
- `goterm_function_alignment.data`: sorted GO indices above the threshold;
  `by_function` preserves the configured function order.
- `goterm_gene_alignment.data`: `0` for a matching gene, otherwise `None`, in
  the exact same gene order.
