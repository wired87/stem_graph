# The official StemCNV workflow UI — a family-friendly guide

This website is a simple front door for the official **StemCNV-check 1.0.0**
workflow. It runs the real StemCNV engine. It is not a homemade replacement
for the scientific analysis.

## What is it for?

Imagine a DNA chip as a large sheet of tiny measurements. StemCNV reads those
measurements and looks for places where a chromosome section may appear too
few or too many times. The website helps you give the files to StemCNV and
collect the reports when the engine is finished.

The result is for research and quality checking. It is **not a diagnosis**.
A doctor, clinical laboratory, or genetic counsellor must explain health
questions and decide whether a result needs clinical confirmation.

## How a parent or first-time user runs it

1. Open the website.
2. Drag the complete DNA-chip folder into the large box. You can also click
   the box and choose files. If you add nothing, the official example is used.
3. Keep “Computer workers” at 3.
4. Choose a simple name for the ZIP download.
5. Press **Start the official StemCNV check** once.
6. Wait. Some real StemCNV steps take many minutes. The button stays locked so
   the same job is not started twice.
7. When every step succeeds, press the green download button. The ZIP contains
   the generated reports and result files.

Refreshing the page is safe: job state and generated results are saved in the
database. Only the Docker worker runs the scientific engine.

### Files needed for researcher data

- `config.yaml`
- `sample_table.tsv` or `sample_table.xlsx`
- matching `*_Grn.idat` and `*_Red.idat` files for every sample
- every array/reference file named by `config.yaml` (normally BPM, EGT, CSV
  manifest, PennCNV PFB and GC model, density BED, and gaps BED)

The server checks this bundle before it starts Docker. It rejects duplicate
filenames, missing IDAT color pairs, missing config references, and paths that
try to leave the job directory.

## For the person running the server

Copy `.env.example` to `.env`, adjust the PostgreSQL password, and run:

```bash
docker compose up --build
```

Open `http://SERVER_ADDRESS:8000/`. Runtime paths are relative by default and
can be moved to VM disks with `STEMCNV_RUN_ROOT_HOST` and
`STEMCNV_EXAMPLE_DATA_HOST`. Do not put a developer home-directory path into
the Docker image.

Codex referral rewards require a personal invite URL shown by an eligible
in-product promotion. Put that URL in `CODEX_REFERRAL_URL`. A normal Codex URL
cannot assign referral credit.
