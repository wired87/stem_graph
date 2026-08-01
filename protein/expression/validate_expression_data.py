def validate_download_expression():

    from pathlib import Path
    import os
    import requests
    import zipfile
    import io

    def validate_tissue_expression(url) -> None:
        local_path = (
                Path(__file__).resolve().parent.parent.parent
                / "protein"
                / "expression"
                / f"{url.split('/')[-1].split('.')[0]}.tsv"
        )

        if not os.path.isfile(local_path):
            print(local_path, "not found. Downloading...")

            response = requests.get(url)
            response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                # Assume the ZIP contains a single TSV file
                tsv_name = next(
                    name for name in zf.namelist()
                    if name.endswith(".tsv")
                )

                with zf.open(tsv_name) as src, open(local_path, "wb") as dst:
                    dst.write(src.read())

    print("extract tissue...")

    protein_expression_urls = [
        # todo add more ntries
        "https://www.proteinatlas.org/download/tsv/rna_brain_region_hpa.tsv.zip",
        #f"https://www.proteinatlas.org/download/tsv/rna_brain_hpa.tsv.zip",
    ]

    for item in protein_expression_urls:
        validate_tissue_expression(item)

    print("download expression... done")
