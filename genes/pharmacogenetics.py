import asyncio
import os
from pathlib import Path
from firegraph.file.parquet import ParquetMaster

DATA_XTRACTOR=[
    "directionality",
    "evidenceLevel",
    "genotype",
    "genotypeAnnotationText",
    "pgxCategory",
    "phenotypeText",
    "variantAnnotation",
    "drugs",
    "targetFromSourceId",
    "isDirectTarget",
]

def add_variant_pharmacogenomics(
        g=None,
        variant_ids=None,
        batch_size: int = 100_000,
):
    print("add_variant_pharmacogenomics...")

    if variant_ids is None:
        variant_ids: list[str] = [
            nid
            for nid, attrs in g.G.nodes(data=True)
            if attrs.get("type") == "VARIANT"
        ]

    local_dir = Path(
        os.path.abspath(
            "genetics/pharmacogenomics"
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
                    "platform/26.03/output/"
                    "pharmacogenomics/"
                ),
                output_dir=str(local_dir),
            )
        )

    variant_set = set(
        variant_ids
    )

    matched_rows = 0

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
                    "variantId",
                    "directionality",
                    "evidenceLevel",
                    "genotype",
                    "genotypeAnnotationText",
                    "pgxCategory",
                    "phenotypeText",
                    "variantAnnotation",
                    "drugs",
                    "targetFromSourceId",
                    "isDirectTarget",
                ],
        ):

            rows = batch.to_pylist()
            print("rows_identifeid:", len(rows), rows[0])

            for row in rows:

                variant_id = row.get(
                    "variantId"
                )

                if (
                    not variant_id
                    or
                    variant_id not in variant_set
                ):
                    continue

                matched_rows += 1

                #
                # pgx node
                # Classification of the drug response type
                # (e.g. Toxicity)
                #
                pgx_id = (
                    f"PGX::{variant_id}::"
                    f"{matched_rows}"
                )

                g.add_node(
                    node_id=pgx_id,
                    node_type="PHARMACOGENOMIC_EFFECT",

                    directionality=row.get(
                        "directionality"
                    ),

                    evidence_level=row.get(
                        "evidenceLevel"
                    ),

                    genotype=row.get(
                        "genotype"
                    ),

                    genotype_annotation=row.get(
                        "genotypeAnnotationText"
                    ),

                    phenotype=row.get(
                        "phenotypeText"
                    ),

                    pgx_category=row.get(
                        "pgxCategory"
                    ),
                )

                #
                # variant -> pgx
                #
                g.add_edge(
                    src=variant_id,
                    trgt=pgx_id,
                    attrs=dict(
                        rel="var_pgx",
                        src_layer="VARIANT",
                        trgt_layer="PHARMACOGENOMIC_EFFECT",
                    )
                )

                #
                # drugs
                #
                for drug in (
                        row.get("drugs")
                        or []
                ):

                    drug_id = drug.get(
                        "drugId"
                    )

                    if not drug_id:
                        continue

                    if not g.G.has_node(
                            drug_id
                    ):
                        g.add_node(
                            node_id=drug_id,
                            node_type="DRUG",
                        )

                    g.add_edge(
                        src=pgx_id,
                        trgt=drug_id,
                        attrs=dict(
                            rel="pgx_drug",
                            is_direct_target=row.get(
                                "isDirectTarget"
                            ),
                            src_layer="PHARMACOGENOMIC_EFFECT",
                            trgt_layer="DRUG",
                        )
                    )

                #
                # variant annotations
                #
                for ann in (
                        row.get(
                            "variantAnnotation"
                        )
                        or []
                ):

                    ann_id = (
                        f"{pgx_id}::"
                        f"{ann.get('id')}"
                    )

                    g.add_node(
                        node_id=ann_id,
                        node_type="VARIANT_EFFECT",

                        effect=ann.get(
                            "effect"
                        ),

                        effect_type=ann.get(
                            "effectType"
                        ),

                        effect_description=ann.get(
                            "effectDescription"
                        ),

                        directionality=ann.get(
                            "directionality"
                        ),

                        entity=ann.get(
                            "entity"
                        ),
                    )

                    g.add_edge(
                        src=pgx_id,
                        trgt=ann_id,
                        attrs=dict(
                            rel="pgx_effect",
                            src_layer="PHARMACOGENOMIC_EFFECT",
                            trgt_layer="VARIANT_EFFECT",
                        )
                    )

    print(
        f"matched_rows={matched_rows:,}"
    )

    print(
        "pharmacogenomics build... done"
    )


def add_variant_pharmacogenomics_batch(
        variant_ids,
        batch_size: int = 100_000_000_000,
):
    """
    DB EINRCHTEN!!!
    PHARMACOGEN NODE SPEICHER NUR IDX MAP AUF DB.TABLE (no data copy = cheap & comfrotable)
    """
    print("add_variant_pharmacogenomics...")
    idx_mapping = {}
    local_dir = Path(
        os.path.abspath(
            "genetics/pharmacogenomics"
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
                    "platform/26.03/output/"
                    "pharmacogenomics/"
                ),
                output_dir=str(local_dir),
            )
        )

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
                    "variantId",
                    "directionality",
                    "evidenceLevel",
                    "genotype",
                    "genotypeAnnotationText",
                    "pgxCategory",
                    "phenotypeText",
                    "variantAnnotation",
                    "drugs",
                    "targetFromSourceId",
                    "isDirectTarget",
                ],
        ):
            rows = batch.to_pylist()
            print("rows_identifeid:", len(rows), rows[:10])

            for vid in variant_ids:
                for i, row in enumerate(rows):
                    #
                    variant_id = row.get(
                        "variantId",
                    )
                    #
                    if vid == variant_id:
                        idx_mapping[variant_id] = i

                if vid not in idx_mapping:
                    print(f"variant {vid} not found in phenotypes")
                    idx_mapping[vid] = None

        # FILL REAL DATA
        data = {
            k: []
            for k in DATA_XTRACTOR
        }
        for batch in pm.iter_batches(
                batch_size=batch_size,
                columns=[
                    #"variantId",
                    "directionality", # INCREASE DECREASE
                    "evidenceLevel",
                    "genotype",
                    "genotypeAnnotationText",
                    "pgxCategory",
                    "phenotypeText",
                    "variantAnnotation",
                    "drugs",
                    "targetFromSourceId",
                    "isDirectTarget",
                ],
        ):
            rows = batch.to_pylist()

            for i, row in enumerate(rows):

                if int(i) in [int(i) for i in list(idx_mapping.values())]:
                    for k, v in row.items():
                        # todo key validation for runtime processing
                        data[k].append(v)

        return data




if __name__ == "__main__":
    add_variant_pharmacogenomics_batch([],)