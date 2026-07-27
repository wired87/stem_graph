
import re

from file._yaml import write_yaml

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
data_path: {{OUTPUT_DIR}}
log_path: {{LOGS_OUT}}

reports:
  StemCNV-check-report:
    file_type: html
"""


def get_config(save_config_path, values:dict):
    """Replace {{KEY}} tokens: explicit values first, then local_paths, then env."""
    config = CONFIG_CONTENT
    for key in re.findall(r'\{\{(\w+)\}\}', CONFIG_CONTENT):
        value = values.get(key)
        config = config.replace(f'{{{{{key}}}}}', str(value))
    write_yaml(config, dest=save_config_path)



