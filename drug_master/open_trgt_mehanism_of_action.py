import asyncio
import os
from pathlib import Path
from file.parquet import ParquetMaster


def open_trgt_moa(
        trgt_ids: list[str], # ensG id frm GENE_ID-node
        drug_ids: list[list[str]],
        batch_size: int = 100_000_000_000,
):
    """
    PARSE DRUG MOA AND PASTE IT TO DRUG
    TODO REFERENCE FOR OPTIMIZED SPEED
    """

    print("Parsing drug_mechanism_of_action (Open Targets 26.06)...")

    data = {
        "targetId": [],  # Aufgelöste Ensembl-Gen-ID (ENSG###)
        "drugId": [],  # Aufgelöste Drug-ID (CHEMBL###)
        "actionType": [],  # z.B. INHIBITOR, ACTIVATOR
        "mechanismOfAction": [],  # Pharmakologische Beschreibung
        "targetName": [],  # Name des biologischen Objekts
        "targetType": [],  # Typ (z.B. protein complex)
    }
    filtered_drug_ids = []
    local_dir = Path(
        os.path.abspath(
            "platform/mechanismOfAction"
        )
    )

    local_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if len(list(local_dir.glob("*.parquet"))) == 0:
        asyncio.run(
            ParquetMaster.receive_all(
                ftp_url=(
                    "https://ftp.ebi.ac.uk/"
                    "pub/databases/opentargets/"
                    "platform/26.06/output/"
                    "drug_mechanism_of_action/"
                ),
                output_dir=str(local_dir),
            )
        )

    #
    parquet_files = sorted(
        local_dir.glob("*.parquet")
    )

    for file_idx, parquet_file in enumerate(
            parquet_files,
            start=1,
    ):
        print(
            f"[{file_idx}/{len(parquet_files)}] "
            f"{parquet_file.name}"
        )

        pm = ParquetMaster(
            str(parquet_file)
        )

        for batch in pm.iter_batches(
            batch_size=batch_size,
            columns=[
                "actionType",
                "mechanismOfAction",
                "chemblIds",
                "targetName",
                "targetType",
                "targets",
            ],
        ):
            rows = batch.to_pylist()
            print("rows_identifeid:", len(rows), rows[0])
            # rows_identifeid: 3112 {'actionType': 'ACTIVATOR', 'mechanismOfAction': 'Acetylcholinesterase activator', 'chemblIds': ['CHEMBL748', 'CHEMBL1420'], 'targetName': 'Acetylcholinesterase', 'targetType': 'single protein', 'targets': ['ENSG00000087085']}
            # map combined trgt and its drug ids from pharmacogenoimics ds
            for trgt, drug_id_batch in (trgt_ids, drug_ids):
                # FILL SKEELTON TO FILL DRUGS MECHANISMS INTO
                drug_skeleton = [None for _ in range(len(drug_id_batch))]

                # loop all rows
                for i, row in enumerate(rows):
                    row_target = row.get("targetName")
                    if row_target != trgt:
                        print("row_target != trgt", row_target, trgt)
                        continue
                    #
                    row_drugs = row.get("chemblIds")

                    # ANY ITEM MATCH MECHANISM?
                    for item in drug_id_batch:
                        if item in row_drugs:
                            if drug_skeleton[i] is None:
                                print("set mech for ", item, ":", row["mechanismOfAction"])
                                drug_skeleton[i] = row["mechanismOfAction"]
                data.append(drug_skeleton)
    print("Open trgt moa dropped")
    return data


if __name__ == "__main__":
    open_trgt_moa([],[],)