# Put the official StemCNV example bundle here

For the “use example data” button fallback, this directory must contain the
official StemCNV example `config.yaml`, `sample_table.tsv` (or XLSX), `RAW/`,
and `static-data/` content. Large scientific fixtures are intentionally not
duplicated in this application repository.

On a VM you may instead set `STEMCNV_EXAMPLE_DATA_HOST` in `.env` to the
mounted directory containing that official bundle.
