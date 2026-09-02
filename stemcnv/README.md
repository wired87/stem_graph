# StemCNV runtime image

This image contains the canonical `bihealth/StemCNV-check` 1.0.0 workflow,
pinned to commit `e050dcf0737e1c260135d0f41832f3151f7b117e`.
The Dockerfile includes narrow `Path` and integer resource conversions required
by the upstream Snakemake 8.28 Python API calls. It also selects UCSC's
certificate-valid `hgdownload.soe.ucsc.edu` alias; scientific logic is unchanged.

The analysis directory is mounted at `/work`; the reusable Snakemake,
Conda, Apptainer, and reference cache is mounted at `/cache`.

```bash
docker build -t stemcnv-check:1.0.0 stemcnv
docker run --rm --privileged \
  -v /absolute/project:/work \
  -v stemcnv-cache:/cache \
  stemcnv-check:1.0.0 run
```

`STEMCNV_CONFIG`, `STEMCNV_SAMPLE_TABLE`, and `STEMCNV_LOCAL_CORES` override
the defaults. The entrypoint also exposes `validate`, `setup`, and
`make-staticdata` actions.
