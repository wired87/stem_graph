import asyncio
import os
from pathlib import Path
from firegraph.file.parquet import ParquetMaster

SCHEMA_TYPES = {
    "variantId": str,
    "chromosome": str,
    "position": int,
    "referenceAllele": str,
    "alternateAllele": str,

    "variantEffect": list[dict], # !!!

    "mostSevereConsequenceId": str,

    "transcriptConsequences": list[dict],

    "rsIds": list[str],

    "hgvsId": str,

    "alleleFrequencies": list[dict],

    "dbXrefs": list[dict],

    "variantDescription": str,
}

VARIANT_DS_KEYS: list[str] = [
    """
    variantFunctionalConsequenceIds	Beste Feld. Standardisierte funktionelle Konsequenzen (SO-IDs).
    mostSevereConsequenceId	Schlimmste Konsequenz laut VEP.
    impact	HIGH / MODERATE / LOW / MODIFIER.
    lofteePrediction	Hochwertige LoF-Klassifikation (HC, LC, OS).
    siftPrediction	deleterious / tolerated.
    polyphenPrediction	benign / possibly damaging / probably damaging.
    consequenceScore	Numerischer Schweregrad.
    aminoAcidChange	Welche AS verändert wurde.
    uniprotAccessions	Verknüpfung zum Protein.
    """
    "variantId",
    "chromosome",
    "position",
    "referenceAllele",
    "alternateAllele",
    "variantEffect",
    "method",
    "assessment",
    "score",
    "assessmentFlag",
    "targetId",
    "normalisedScore",
    "mostSevereConsequenceId",
    "transcriptConsequences",
    "variantFunctionalConsequenceIds",
    "aminoAcidChange",
    "uniprotAccessions",
    "isEnsemblCanonical",
    "codons",
    "distanceFromFootprint",
    "distanceFromTss",
    "appris",
    "maneSelect",
    "targetId",
    "impact",
    "lofteePrediction",
    "siftPrediction",
    "polyphenPrediction",
    "consequenceScore",
    "transcriptIndex",
    "approvedSymbol",
    "biotype",
    "transcriptId",
    "rsIds",
    "hgvsId",
    "alleleFrequencies",
    "populationName",
    "alleleFrequency",
    "dbXrefs",
    "id",
    "source",
    "variantDescription"
]

SCHEMA_DESCRIPTION = {
    "variantId":
        "Unique variant identifier: chromosome-position-ref-alt",

    "chromosome":
        "Chromosome containing the variant",

    "position":
        "Genomic position of the variant",

    "referenceAllele":
        "Reference allele",

    "alternateAllele":
        "Alternative allele",

    "variantEffect":
        {
            "method":
                "Prediction method",

            "assessment":
                "Textual effect assessment",

            "score":
                "Raw effect score",

            "assessmentFlag":
                "Pathogenicity flag",

            "targetId":
                "Affected Ensembl target",

            "normalisedScore":
                "Effect score normalized between -1 and 1",
        },

    "mostSevereConsequenceId":
        "Most severe Sequence Ontology consequence",

    "transcriptConsequences":
        {
            "variantFunctionalConsequenceIds":
                "Sequence ontology consequence identifiers",

            "aminoAcidChange":
                "Protein amino acid change",

            "uniprotAccessions":
                "Affected UniProt protein accessions",

            "isEnsemblCanonical":
                "Canonical transcript flag",

            "codons":
                "Affected codon(s)",

            "distanceFromFootprint":
                "Distance from transcript footprint",

            "distanceFromTss":
                "Distance from transcription start site",

            "appris":
                "APPRIS transcript annotation",

            "maneSelect":
                "MANE transcript annotation",

            "targetId":
                "Affected Ensembl gene",

            "impact":
                "VEP impact prediction (HIGH/MODERATE/LOW/etc)",

            "lofteePrediction":
                "LOFTEE loss-of-function prediction",

            "siftPrediction":
                "SIFT functional impact score",

            "polyphenPrediction":
                "PolyPhen functional impact score",

            "consequenceScore":
                "VEP consequence severity score",

            "transcriptIndex":
                "Transcript rank around gene",

            "approvedSymbol":
                "HGNC gene symbol",

            "biotype":
                "Transcript biotype",

            "transcriptId":
                "Ensembl transcript identifier",
        },

    "rsIds":
        "dbSNP rs identifiers",

    "hgvsId":
        "HGVS variant notation",

    "alleleFrequencies":
        {
            "populationName":
                "Population name",

            "alleleFrequency":
                "Alternative allele frequency",
        },

    "dbXrefs":
        {
            "id":
                "External database identifier",

            "source":
                "External database source",
        },

    "variantDescription":
        "Human-readable summary of variant effect",
}


def add_variant_nodes(
    g,
    batch_size: int = 100_000,
):
    print("add_variant_nodes...")

    uniprot_ids: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"]

    local_dir = Path(
        os.path.abspath(
            "genes/variant"
        )
    )

    local_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # FETCH DS IF NOT EXISTS
    if len(list(local_dir.glob("*.parquet"))) == 0:
        asyncio.run(
            ParquetMaster.receive_all(
                ftp_url=(
                    "https://ftp.ebi.ac.uk/"
                    "pub/databases/opentargets/"
                    "platform/26.03/output/"
                    "variant/"
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

        # todo first fetch idx (just with varintId key) -> access more data trgted
        for batch in pm.iter_batches(
                batch_size=batch_size,
                columns=VARIANT_DS_KEYS
        ):

            rows = batch.to_pylist()

            for row in rows:

                variant_id = row["variantId"]

                transcript_consequences = row.get("transcriptConsequences", [])

                for tc in transcript_consequences:
                    matched_transcripts = []
                    tc_uniprots = set(
                        tc.get(
                            "uniprotAccessions",
                            []
                        )
                    )

                    for item in tc_uniprots:
                        if item in uniprot_ids:
                            matched_transcripts.append(item)

                    if not matched_transcripts:
                        continue

                    if not g.G.has_node(
                            variant_id
                    ):
                        g.add_node(
                            id=variant_id,
                            node_type="VARIANT",

                            variant_description=row.get(
                                "variantDescription"
                            ),

                            most_severe_consequence=row.get(
                                "mostSevereConsequenceId"
                            ),
                        )

                    #
                    # VARIANT -> PROTEIN
                    # VARIANT -> GENE
                    #
                    for item in matched_transcripts:
                        g.add_edge(
                            src=variant_id,
                            trgt=item,
                            attrs=dict(
                                rel="var_prt",

                                impact=tc.get(
                                    "impact"
                                ),

                                loftee_prediction=tc.get(
                                    "lofteePrediction"
                                ),

                                sift_prediction=tc.get(
                                    "siftPrediction"
                                ),

                                polyphen_prediction=tc.get(
                                    "polyphenPrediction"
                                ),

                                consequence_score=tc.get(
                                    "consequenceScore"
                                ),

                                amino_acid_change=tc.get(
                                    "aminoAcidChange"
                                ),

                                src_layer="VARIANT",
                                trgt_layer="PROTEIN",
                            )
                        )

                        neighbor_gene = g.get_neighbor_list(
                            node=item,
                            target_type="GENE",
                            just_ids=True,
                        )
                        if neighbor_gene:
                            gene_id = neighbor_gene[0]

                            g.add_edge(
                                src=variant_id,
                                trgt=gene_id,
                                attrs=dict(
                                    rel="var_gene",

                                    impact=tc.get(
                                        "impact"
                                    ),

                                    loftee_prediction=tc.get(
                                        "lofteePrediction"
                                    ),

                                    consequence_score=tc.get(
                                        "consequenceScore"
                                    ),

                                    src_layer="VARIANT",
                                    trgt_layer="GENE",
                                )
                            )

    print(
        "variant graph build... done"
    )

# BUILD DB TODO

def get_variants_from_varids(
    valiant_ids:list[str],
    batch_size: int = 100_000,
):
    print("add_variant_nodes...")

    local_dir = Path(
        os.path.abspath(
            "genes/variant"
        )
    )

    local_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # FETCH DS IF NOT EXISTS
    if len(list(local_dir.glob("*.parquet"))) == 0:
        asyncio.run(
            ParquetMaster.receive_all(
                ftp_url=(
                    "https://ftp.ebi.ac.uk/"
                    "pub/databases/opentargets/"
                    "platform/26.03/output/"
                    "variant/"
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

        varints = []
        ref_ids = set()
        # todo first fetch idx (just with varintId key) -> access more data trgted
        for batch in pm.iter_batches(
                batch_size=batch_size,
                columns=VARIANT_DS_KEYS
        ):
            rows = batch.to_pylist()

            for row in rows:
                variant_id = row["variantId"]
                if variant_id in valiant_ids:
                    varints.append(row)
                    ref_ids.add(variant_id)

            missing = [vid for vid in valiant_ids if vid not in ref_ids]
            if missing:
                print(
                    f"missing {len(missing)}/{len(valiant_ids)} varints"
                )
            return varints, missing

    print(
        "variant graph build... done"
    )












