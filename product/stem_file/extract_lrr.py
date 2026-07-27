import os

import pandas as pd

from utils.run_subprocess import exec_cmd


def extract_lrr_baf(gtc_file: str, bpm_file: str, egt_file: str, output_dir: str) -> pd.DataFrame:
    """
    Nutzt bcftools (gtc2vcf), um aus der binären GTC-Datei die berechneten
    Werte für Log R Ratio (LRR) und B-Allele Frequency (BAF) auszulesen.
    """
    print("[SCHRITT 2] Extrahiere LRR und BAF Werte via bcftools gtc2vcf...")
    sample_name = os.path.basename(gtc_file).replace(".gtc", "")
    tsv_output_path = os.path.join(output_dir, f"{sample_name}_extracted_metrics.tsv")

    cmd_extract = f"bcftools plugin gtc2vcf --gtc {gtc_file} --bpm {bpm_file} --egt {egt_file} --export-lrr-baf {tsv_output_path}"
    exec_cmd(cmd_extract)

    df = pd.read_csv(tsv_output_path, sep="\t")
    df.set_index("Locus_Name", inplace=True)

    # Datenbereinigung
    df["LRR"] = pd.to_numeric(df["LRR"], errors='coerce')
    df["BAF"] = pd.to_numeric(df["BAF"], errors='coerce')

    print(f"-> Daten erfolgreich extrahiert. SNPs geladen: {len(df)}")
    return df[["Chr", "Pos", "LRR", "BAF"]]