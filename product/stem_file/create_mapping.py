from __future__ import annotations
import csv


def load_address_to_rsid(manifest_csv: str) -> dict[int, str]:
    """
    Load Address ID -> rsID mapping from an Illumina manifest CSV.

    Supports columns like:
        IlmnID
        Name
        AddressA_ID
        AddressB_ID

    Returns
    -------
    dict[int, str]
        {
            31730401: "rs429358",
            31730402: "rs7412",
        }
    """

    mapping: dict[int, str] = {}

    with open(manifest_csv, newline="", encoding="utf-8-sig") as f:

        # Skip manifest header until column names
        while True:
            pos = f.tell()
            line = f.readline()

            if line.startswith("IlmnID,") or line.startswith("Name,"):
                f.seek(pos)
                break

        reader = csv.DictReader(f)

        for row in reader:
            print("row", row)
            rsid = row.get("Name", "")
            if rsid is None:
                continue
            rsid = rsid.strip()

            if not rsid.startswith("rs"):
                continue

            for col in ("AddressA_ID", "AddressB_ID"):

                value = row.get(col, "").strip()

                if not value:
                    continue

                try:
                    mapping[int(value)] = rsid
                except ValueError:
                    pass
    print("result", list(mapping.items())[:10])
    return mapping

if __name__ == "__main__":
    load_address_to_rsid(r"C:\Users\Bernhard\PycharmProjects\CNVMaster\product\executable\example_data\static-data\ExampleArray\GSAMD-24v3-0-EA_20034606_A1.csv")