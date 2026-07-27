import asyncio
import os
from pathlib import Path
from firegraph.file.parquet import ParquetMaster

def add_gwas(
    g,
    batch_size: int = 100_000,
):
    print("add_studies...")

    gene_ids: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "GENE"]

    tissue_ids: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "TISSUE"
           and nid.startswith("UB")
    ]

    disease_ids: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "DISEASE"
    ]

    local_dir = Path(
        os.path.abspath(
            "genetics/study"
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
                    "study/"
                ),
                output_dir=str(local_dir),
            )
        )

    matched_rows = 0

    parquet_files = sorted(
        local_dir.glob("*.parquet")
    )

    for parquet_file in parquet_files:

        pm = ParquetMaster(
            str(parquet_file)
        )

        for batch in pm.iter_batches(
                batch_size=batch_size,
                columns=[
                    "studyId",
                    "geneId",
                    "studyType",
                    "traitFromSource",
                    "biosampleId",
                    "condition",
                    "diseaseIds",
                    "publicationTitle",
                    "pubmedId",
                    "nSamples",
                ],
        ):

            rows = batch.to_pylist()

            for row in rows:

                gene_id = row.get(
                    "geneId"
                )

                if gene_id not in gene_ids:
                    print(f"gene {gene_id} not relevant here")
                    continue

                biosample_id = row.get(
                    "biosampleId"
                )

                if biosample_id and biosample_id not in tissue_ids:
                    print(f"tissue {biosample_id} not relevant here")
                    continue

                row.get()
                matched_rows += 1

                study_id = row[
                    "studyId"
                ]

                if not g.G.has_node(
                        study_id
                ):
                    g.add_node(
                        dict(
                            id=study_id,
                            type="STUDY",

                            study_type=row.get(
                                "studyType"
                            ),

                            trait=row.get(
                                "traitFromSource"
                            ),

                            condition=row.get(
                                "condition"
                            ),

                            publication=row.get(
                                "publicationTitle"
                            ),

                            pubmed_id=row.get(
                                "pubmedId"
                            ),

                            sample_size=row.get(
                                "nSamples"
                            ),
                        )
                    )

                #
                # study -> gene
                #
                g.add_edge(
                    src=study_id,
                    trgt=gene_id,
                    attrs=dict(
                        rel="study_gene",
                        src_layer="STUDY",
                        trgt_layer="GENE",
                    )
                )



                g.add_edge(
                    src=study_id,
                    trgt=biosample_id,
                    attrs=dict(
                        rel="study_tissue",
                    )
                )

                #
                # study -> disease
                #
                for disease_id in (

                        or []
                ):

                    if not g.G.has_node(
                            disease_id
                    ):
                        continue

                    g.add_edge(
                        src=study_id,
                        trgt=disease_id,
                        attrs=dict(
                            rel="study_disease",
                        )
                    )

    print(
        f"matched_rows={matched_rows:,}"
    )

    print(
        "gwas graph build... done"
    )