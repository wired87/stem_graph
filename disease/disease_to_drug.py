import os
import sys
from pathlib import Path

# CHAR: repo root on sys.path when this file is run as a script.
for _p in Path(__file__).resolve().parents:
    if (_p / "core").is_dir() and (_p / "embedder").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

from drug_master.drug import ChemblFetcher

from firegraph.file.parquet import ParquetMaster

_CHEMBL_FETCHER = ChemblFetcher()

DISEASE_DRUG_OT_ENDP = "http://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.03/output/clinical_indication/"

INDICATION_COLUMNS = {
    "id": str,
    "maxClinicalStage": str,
    "clinicalReportIds": list[str],
    "diseaseId": str,
    "drugId": str,
}


async def _ensure_indication_parquets(local_dir: Path) -> list[Path]:
    local_dir.mkdir(parents=True, exist_ok=True)
    for stale in local_dir.glob("*.parquet"):
        if not ParquetMaster.is_valid_parquet(stale):
            print(f"removing invalid parquet: {stale}")
            stale.unlink()
    valid = [p for p in sorted(local_dir.glob("*.parquet")) if ParquetMaster.is_valid_parquet(p)]
    if not valid:
        await ParquetMaster.receive_all(
            ftp_url=DISEASE_DRUG_OT_ENDP,
            output_dir=str(local_dir),
        )
        valid = [p for p in sorted(local_dir.glob("*.parquet")) if ParquetMaster.is_valid_parquet(p)]
    if not valid:
        raise FileNotFoundError(f"no valid clinical_indication parquet in {local_dir}")
    return valid


async def get_drug_for_disease(
    g,
):
    print("get_drug_for_disease...")

    local_dir = Path(os.path.abspath("disease/align"))
    parquet_files = await _ensure_indication_parquets(local_dir)

    for file_idx, parquet_file in enumerate(
            parquet_files,
            start=1,
    ):
        pm = ParquetMaster(
            str(parquet_file)
        )

        for batch in pm.iter_batches(
                batch_size=100000,
                columns=list(INDICATION_COLUMNS.keys()),
            ):

            rows = batch.to_pylist()

            for row in rows:

                disease_id = row["diseaseId"]
                if not g.G.has_node(disease_id):continue

                drug_id = row["drugId"]

                g.add_node(
                    dict(
                        type="MOLECULE",
                        id=drug_id
                    )
                )

                # DIS -> DRUG
                g.add_edge(
                    src=disease_id,
                    trgt=drug_id,
                    attrs=dict(
                        rel="associated_with",
                        src_layer="DISEASE",
                        trgt_layer="MOLECULE",
                        **{k:v for k,v in row.items() if k not in ["targetId", "diseaseId"]}
                    )
                )

    print("get_drug_for_disease... done")


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for get_drug_for_disease.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import asyncio
    from firegraph.graph.local_graph_utils import GUtils

    async def _check_get_drug_for_disease():
        # CHAR: pre-seed OT disease id present in clinical_indication parquet stream.
        g = GUtils()
        g.add_node(
            attrs=dict(
                id="EFO_000125",
                type="DISEASE",
                name="epilepsy",
                text="epilepsy",
            )
        )
        g.add_node(
            attrs=dict(
                id="EFO_000136",
                type="DISEASE",
                name="diabetes mellitus",
                text="diabetes mellitus",
            )
        )
        n0 = g.G.number_of_nodes()
        await get_drug_for_disease(g)
        molecules = [nid for nid, a in g.G.nodes(data=True) if a.get("type") == "MOLECULE"]
        dis_drug = [
            a for _, _, a in g.G.edges(data=True)
            if a.get("rel") == "associated_with" and a.get("src_layer") == "DISEASE"
        ]
        print(
            f"[__main__] get_drug_for_disease OK  "
            f"molecules={len(molecules)} dis_drug_edges={len(dis_drug)} nodes+={g.G.number_of_nodes()-n0}"
        )

    asyncio.run(_check_get_drug_for_disease())

