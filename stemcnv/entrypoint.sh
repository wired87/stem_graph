#!/bin/sh
set -eu

action="${1:-run}"
if [ "$#" -gt 0 ]; then
    shift
fi

config="${STEMCNV_CONFIG:-config.yaml}"
sample_table="${STEMCNV_SAMPLE_TABLE:-sample_table.tsv}"
cores="${STEMCNV_LOCAL_CORES:-3}"
memory_mb="${STEMCNV_MEMORY_MB:-6500}"
snake_options="${STEMCNV_SNAKEMAKE_OPTIONS:---set-resources run_CBS:mem_mb=6500 combined_PennCNV_output:mem_mb=6500}"
cache="${STEMCNV_CACHE:-/cache}"

common_args="--directory /work --config $config --sample-table $sample_table --local-cores $cores --memory-mb $memory_mb --cache-path $cache"

case "$action" in
    validate)
        stemcnv-check --version
        stemcnv-check run --help >/dev/null
        ;;
    setup)
        cd /work
        exec stemcnv-check setup-files "$@"
        ;;
    make-staticdata)
        # shellcheck disable=SC2086
        exec stemcnv-check make-staticdata $common_args "$@"
        ;;
    run)
        # shellcheck disable=SC2086
        exec stemcnv-check run $common_args "$@" -- $snake_options
        ;;
    *)
        echo "Unknown action: $action (expected validate, setup, make-staticdata, or run)" >&2
        exit 64
        ;;
esac
