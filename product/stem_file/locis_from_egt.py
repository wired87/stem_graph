from __future__ import annotations

from pathlib import Path

from BeadArrayFiles.module import ClusterFile


def load_egt(path: str) -> dict:
    """
    Load an Illumina EGT (cluster) file into a Python dictionary.

    Parameters
    ----------
    path
        Path to the .egt file.

    Returns
    -------
    dict
    """

    egt = ClusterFile(Path(path))

    return {
        "version": egt.version,

        "num_loci": egt.num_loci,

        "manifest_name": getattr(egt, "manifest_name", None),

        "cluster_version": getattr(egt, "cluster_version", None),

        "normalization_version": getattr(
            egt,
            "normalization_version",
            None,
        ),

        "loci": [
            {
                "name": locus.name,

                "aa_cluster": locus.aa_cluster_stats,

                "ab_cluster": locus.ab_cluster_stats,

                "bb_cluster": locus.bb_cluster_stats,

                "gen_train_score": getattr(
                    locus,
                    "gen_train_score",
                    None,
                ),

                "normalization": getattr(
                    locus,
                    "normalization_transform",
                    None,
                ),
            }
            for locus in egt.loci
        ],
    }

if __name__ == "__main__":
    egt_path = r"C:\Users\Bernhard\PycharmProjects\CNVMaster\product\executable\example_data\static-data\ExampleArray\GSAMD-24v3-0-EA_20034606_A1.egt"
    loci_list = extract_loci_from_egt(egt_path)
    print(loci_list)