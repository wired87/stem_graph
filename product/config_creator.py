# StemCNV-check config template; {{KEY}} placeholders filled from payload values
import os
import re

# Minimal config template for StemCNV-check runs
CONFIG_CONTENT = """\
array_definition:
  {{STEMCNV_ARRAY_NAME}}:
    genome_version: {{STEMCNV_GENOME_VERSION}}
    bpm_manifest_file: {{STEMCNV_BPM_MANIFEST}}
    egt_cluster_file: {{STEMCNV_EGT_CLUSTER}}
    csv_manifest_file: {{STEMCNV_CSV_MANIFEST}}
    penncnv_pfb_file: __cache-default__
    penncnv_GCmodel_file: __cache-default__
    array_density_file: __cache-default__
    array_gaps_file: __cache-default__

raw_data_folder: {{STEMCNV_RAW_DATA_FOLDER}}
data_path: out
log_path: logs

reports:
  StemCNV-check-report:
    file_type: html
"""

# Placeholders that must be non-empty when building config via API
REQUIRED_CONFIG_KEYS = (
    'STEMCNV_ARRAY_NAME',
    'STEMCNV_GENOME_VERSION',
    'STEMCNV_BPM_MANIFEST',
    'STEMCNV_EGT_CLUSTER',
    'STEMCNV_RAW_DATA_FOLDER',
)


def get_config(values: dict | None = None, local_paths: dict | None = None) -> str:
    """Replace {{KEY}} tokens: explicit values first, then local_paths, then env."""
    values = values or {}
    local_paths = local_paths or {}
    config = CONFIG_CONTENT
    for key in re.findall(r'\{\{(\w+)\}\}', CONFIG_CONTENT):
        value = values.get(key) or local_paths.get(key) or os.getenv(key, '')
        config = config.replace(f'{{{{{key}}}}}', str(value))
    return config


def validate_config_values(values: dict) -> list[str]:
    """Return missing required keys for a config payload."""
    return [key for key in REQUIRED_CONFIG_KEYS if not str(values.get(key, '')).strip()]
