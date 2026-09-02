FROM condaforge/miniforge3:25.3.1-0

ARG STEMCNV_COMMIT=e050dcf0737e1c260135d0f41832f3151f7b117e

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STEMCNV_CACHE=/cache \
    STEMCNV_LOCAL_CORES=4

RUN mamba install -y -n base -c conda-forge -c bioconda \
        python=3.12 \
        apptainer \
        fuse-overlayfs \
        squashfuse \
        git \
        snakemake=8.28 \
        pip \
    && python -m pip install --no-cache-dir \
        "git+https://github.com/bihealth/StemCNV-check.git@${STEMCNV_COMMIT}" \
    && mamba clean --all --yes

# StemCNV-check 1.0.0 passes str workdirs to the Snakemake 8.28 Python API,
# whose WorkdirHandler requires pathlib.Path. The module already imports Path.
RUN sed -i 's/workdir=args.directory/workdir=Path(args.directory)/g' \
        /opt/conda/lib/python3.12/site-packages/stemcnv_check/app/make_staticdata.py \
    && sed -i 's/cores=args.local_cores/cores=int(args.local_cores)/g; s/local_cores=args.local_cores/local_cores=int(args.local_cores)/g; s/'"'"'mem_mb'"'"': args.memory_mb/'"'"'mem_mb'"'"': int(args.memory_mb)/g' \
        /opt/conda/lib/python3.12/site-packages/stemcnv_check/app/make_staticdata.py \
    && sed -i 's/hgdownload\.cse\.ucsc\.edu/hgdownload.soe.ucsc.edu/g' \
        /opt/conda/lib/python3.12/site-packages/stemcnv_check/rules/static_creation_global_files.smk

COPY entrypoint.sh /usr/local/bin/stemcnv-entrypoint
RUN chmod 0755 /usr/local/bin/stemcnv-entrypoint \
    && mkdir -p /work /cache \
    && touch /etc/localtime

WORKDIR /work
VOLUME ["/work", "/cache"]

ENTRYPOINT ["/usr/local/bin/stemcnv-entrypoint"]
CMD ["run"]
