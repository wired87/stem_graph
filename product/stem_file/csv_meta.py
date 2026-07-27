
import csv
from pathlib import Path

def extract_manifest_metadata(csv_path: str | Path) -> dict:
    """
    Parst NUR die Metadaten des Manifests. Arbeitet komplett autark.
    """
    metadata = {
        "descriptor_file_name": "Unknown",
        "assay_format": "Unknown",
        "date_manufactured": "Unknown",
        "loci_count": 0,
        "genome_version": "Unknown",
        "array_name": "Unknown"
    }

    with open(csv_path, mode='r', encoding='utf-8', errors='ignore') as f:
        # 1. Header bis zum [Assay]-Block einlesen
        for line in f:
            line_clean = line.strip()
            if line_clean.startswith("[Assay]"):
                break
            if not line_clean or line_clean.startswith("[Heading]"):
                continue

            parts = [p.strip() for p in line_clean.split(',') if p.strip()]
            if len(parts) >= 2:
                key = parts[0].lower()
                value = parts[1]

                if "descriptor file name" in key:
                    metadata["descriptor_file_name"] = value
                elif "assay format" in key:
                    metadata["assay_format"] = value
                elif "date manufactured" in key:
                    metadata["date_manufactured"] = value
                elif "loci count" in key:
                    try:
                        metadata["loci_count"] = int(value)
                    except ValueError:
                        pass

        reader = csv.reader(f)
        headers = next(reader, None)  # Spaltenköpfe des Assay-Blocks
        if headers:
            headers_lower = [h.lower() for h in headers]
            if "genomebuild" in headers_lower:
                genome_idx = headers_lower.index("genomebuild")
                first_data_row = next(reader, None)
                if first_data_row and len(first_data_row) > genome_idx:
                    build_val = first_data_row[genome_idx].strip()
                    metadata["genome_version"] = f"GRCh{build_val}" if build_val in ["37", "38"] else build_val

    loci = metadata["loci_count"]
    if 1580000 <= loci <= 1620000 or 1900000 <= loci <= 2050000:
        metadata["array_name"] = "GDA-8v1-0"
    elif 730000 <= loci <= 765000:
        metadata["array_name"] = "GSAMD-24v3-0"
    elif 711000 <= loci <= 725000:
        metadata["array_name"] = "GSA-24v2-0"
    elif 695000 <= loci <= 710999:
        if "gsa" in metadata["descriptor_file_name"].lower():
            metadata["array_name"] = "GSA-24v1-0"
        else:
            metadata["array_name"] = "OmniExpress-24v1-3"
    elif 580000 <= loci <= 598000:
        metadata["array_name"] = "PsychArray-24v1-1"
    elif 2400000 <= loci <= 2500000:
        metadata["array_name"] = "Omni2.5-8v1-3"
    else:
        metadata["array_name"] = "GSAMD-24v3-0"
    #
    return metadata


def extract_manifest_assay_data(csv_path: str | Path) -> list[dict]:
    """
    Parst NUR die Tabellendaten des Assay-Blocks. Arbeitet komplett autark.
    Skippt den Metadaten-Header dynamisch.
    """
    records = []

    with open(csv_path, mode='r', encoding='utf-8', errors='ignore') as f:
        # Spule die Datei vor, bis der [Assay]-Block erreicht ist
        for line in f:
            if line.strip().startswith("[Assay]"):
                print("Found [Assay] block... skip")
                break

        # Ab hier liest der CSV-Reader autark weiter
        reader = csv.reader(f)
        headers = next(reader, None)  # Liest die Tabellen-Header

        if not headers:
            print("Noe header foud in csv...")
            return records

        for row in reader:
            if not row or len(row) < len(headers):
                print("Invalid row found in csv...")
                continue
            # Erstellt das flache Key-Value Dict für die Zeile
            records.append(dict(zip(headers, row)))
    print("records", records[0])
    #records {'IlmnID': '1:103380393-0_B_R_2346041316', 'Name': '1:103380393', 'IlmnStrand': 'BOT', 'SNP': '[T/C]', 'AddressA_ID': '0009663149', 'AlleleA_ProbeSeq': 'AATAAACTTTTATGCAAAACTTGTAAGATAACTCTTCTTTCCTTCTTCTT', 'AddressB_ID': '', 'AlleleB_ProbeSeq': '', 'GenomeBuild': '37', 'Chr': '1', 'MapInfo': '103380393', 'Ploidy': 'diploid', 'Species': 'Homo sapiens', 'Source': '1000genomes', 'SourceVersion': '0', 'SourceStrand': 'TOP', 'SourceSeq': 'GCTTCCCCTTTCTCTCCTCTTTCTCCTTTGGGACCCTAAACAATGTTAAAAAAAAAAAAA[A/G]AAGAAGAAGGAAAGAAGAGTTATCTTACAAGTTTTGCATAAAAGTTTATTAACCTTGGCA', 'TopGenomicSeq': 'GCTTCCCCTTTCTCTCCTCTTTCTCCTTTGGGACCCTAAACAATGTTAAAAAAAAAAAAA[A/G]AAGAAGAAGGAAAGAAGAGTTATCTTACAAGTTTTGCATAAAAGTTTATTAACCTTGGCA', 'BeadSetID': '1895', 'Exp_Clusters': '3', 'RefStrand': '-'}
    return records



if __name__ == "__main__":
    # Pfad zu deiner extrahierten Manifest-CSV eintragen
    csv_test_path = r"C:\Users\Bernhard\PycharmProjects\CNVMaster\product\executable\example_data\static-data\ExampleArray\GSAMD-24v3-0-EA_20034606_A1.csv"
    extract_manifest_assay_data(csv_path=csv_test_path)



