import os

from file.find_file_by_extension import find_file_by_extension
from create_config import get_config


def make_cfg(
    detected_array_name,
    detected_genome_version,
):
    print("making cfg...")
    input_dir = os.path.abspath(os.path.join("executable/data", "input"))
    config_args: dict = {}
    config_args["STEMCNV_ARRAY_NAME"] = detected_array_name
    config_args["STEMCNV_GENOME_VERSION"] = detected_genome_version
    config_args["STEMCNV_BPM_MANIFEST"] = find_file_by_extension(input_dir, ".bpm")
    config_args["STEMCNV_EGT_CLUSTER"] = find_file_by_extension(input_dir, ".egt")
    config_args["STEMCNV_CSV_MANIFEST"] = find_file_by_extension(input_dir, ".csv")
    config_args["STEMCNV_RAW_DATA_FOLDER"] = os.path.abspath(os.path.join("executable/data", "raw"))
    config_args["LOGS_OUT"] = os.path.abspath(os.path.join("executable/data", "logs"))
    config_args["OUTPUT_DIR"] = os.path.abspath(os.path.join("executable/data", "output"))
    save_config_path = os.path.abspath(os.path.join("executable/data", "input", "config.yaml"))
    get_config(save_config_path, values=config_args)
    print("cfg made... done")
    return save_config_path
