import asyncio
import os
from pathlib import Path

from file.parquet import ParquetMaster


def add_target_metadata(
        gene_ids,
        batch_size: int = 100_000_000_000,
):
    print("add_target_metadata (Open Targets 26.06)...")

    idx_mapping = {}

    data = {
        k: []
        for k in [
            "approvedSymbol",
            "approvedName",
            "biotype",
        ]
    }

    local_dir = Path(
        os.path.abspath(
            "platform/target"
        )
    )

    local_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 3. Download anstoßen, falls noch keine Parquet-Dateien vorhanden sind
    if len(list(local_dir.glob("*.parquet"))) == 0:
        asyncio.run(
            ParquetMaster.receive_all(
                ftp_url=(
                    "https://ftp.ebi.ac.uk/"
                    "pub/databases/opentargets/"
                    "platform/26.06/output/"
                    "target/"
                ),
                output_dir=str(local_dir),
            )
        )

    matched_rows = 0

    parquet_files = sorted(
        local_dir.glob("*.parquet")
    )

    # 4. Parquet-Dateien iterieren und Zielspalten extrahieren
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
                    "id",
                ],
        ):
            rows = batch.to_pylist()
            for gid in gene_ids:
                for i, row in enumerate(rows):
                    target_id = row.get("id")
                    
                    if gid == target_id:
                        idx_mapping[target_id] = i

                if gid not in idx_mapping:
                    print(f"variant {gid} not found in phenotypes")
                    idx_mapping[gid] = None
        for batch in pm.iter_batches(
                batch_size=batch_size,
                columns=list(data.keys()),
        ):
            rows = batch.to_pylist()

            for i, row in enumerate(rows):

                if int(i) in [int(i) for i in list(idx_mapping.values())]:
                    for k, v in row.items():
                        data[k].append(v)

        return data

    print(f"✓ Fertig. {matched_rows} Targets erfolgreich mit Metadaten aktualisiert.")