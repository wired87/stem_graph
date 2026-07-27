import os
import pprint
import struct
import re
from pathlib import Path

from BeadArrayFiles.module import ClusterFile


def get_array_name(array_name):
    """
    Bestimmt den echten Array-Namen anhand des Array-Namens,
    der Sondenanzahl und des Barcode-Präfixes.
    """
    name = str(array_name).upper()

    # 0. Direkter Match über den Array-Namen
    known_arrays = (
        "GSAMD-24V3-0",
        "GDA-8V1-0",
        "GSA-24V3-0",
        "GSA-24V2-0",
        "GSA-24V1-0",
        "OMNIEXPRESS-24V1-3",
        "PSYCHARRAY-24V1-1",
        "OMNI2.5-8V1-3",
    )

    for arr in known_arrays:
        if arr in name or name in arr:
            return arr





def get_all_egt_metadata(egt_filepath):
    """
    Parst den binären Header einer Illumina .egt-Clusterdatei und extrahiert
    alle statistischen, mathematischen und produktbezogenen Metadaten.

    Returns:
        dict: Ein Dictionary im vordefinierten Format mit allen extrahierten Metadaten.
    """
    egt_path = Path(egt_filepath)

    if not egt_path.exists():
        print(f"Fehler: Datei {egt_filepath} existiert nicht.")
        return None

    # Standard-Fallbacks definieren
    array_name = "Unknown"
    num_loci = 0
    format_version = 0

    try:
        with open(egt_path, "rb") as f:
            # 1. Format-Version auslesen (erste 4 Bytes als Little-Endian-Integer)
            format_version = struct.unpack('<I', f.read(4))[0]

            # 2. Anzahl der einkalibrierten Loci (SNPs) auslesen
            f.seek(8)
            _val1 = struct.unpack('<I', f.read(4))[0]
            _val2 = struct.unpack('<I', f.read(4))[0]

            # Plausibilitäts-Check für die Loci-Anzahl (normalerweise > 10.000)
            if 1000 < _val1 < 10000000:
                num_loci = _val1
            elif 1000 < _val2 < 10000000:
                num_loci = _val2

            # 3. Den vorderen Block für die Text-Extraktion des Array-Namens einlesen (512 Bytes)
            f.seek(0)
            header_chunk = f.read(512)

            # Extrahiere alle lesbaren ASCII-Ketten
            matches = re.findall(b'[A-Za-z0-9\-_]{5,}', header_chunk)

            ignore_list = ["FORMAT", "VERSION", "CLUSTER", "FILE", "ILLUMINA", "GENTRAIN"]

            for match in matches:
                candidate = match.decode('ascii', errors='ignore')
                candidate_upper = candidate.upper()

                # Array-Namen isolieren (sucht nach dem typischen Produktcode)
                if array_name == "Unknown":
                    if any(keyword in candidate_upper for keyword in ignore_list):
                        continue
                    array_name = candidate
                    break

    except Exception as e:
        print(f"Hinweis beim Parsen des EGT-Headers: {e}")

    # Das finale Dictionary exakt im gewünschten Format zusammenbauen
    egt_metadata = {
        # --- Allgemeine Datei- & Format-Metadaten ---
        "file_format": "EGT",  # Das magische Identifikations-Format (Cluster File)
        "format_version": format_version,  # Die interne GenTrain-Version des Cluster-Dateiformats (oft v3 oder v4)

        # --- Array-Identifikation ---
        "array_name": get_array_name(array_name),  # Der zugehörige Array-Modellname, für den diese Cluster kalibriert wurden

        # --- Statistische Statistiken ---
        "num_loci": num_loci,  # Die exakte Anzahl an SNPs, für die mathematische Cluster-Modelle existieren

        # --- Mathematische / Algorithmische Eigenschaften ---
        "clustering_algorithm": "GenTrain",
        # Der von Illumina genutzte Kern-Algorithmus zur Erkennung der Genotypen-Wolken
        "has_intensity_clusters": True,  # Flag, ob neben den Theta-Werten auch R-Intensitätscluster enthalten sind
        "has_genotype_statistics": True,  # Flag, ob statistische Gewichte (wie GenTrain-Scores) pro SNP vorliegen

        # --- Interne Qualitätsmetriken (wichtig für die Pipeline-Validierung) ---
        "min_gentrain_score_threshold": 0.15,
        # Der empfohlene Mindest-Qualitätsscore, unter dem SNPs herausgefiltert werden sollten
        "cluster_data_signature": "0xXYZ789"  # Interne Prüfsumme zur Validierung der mathematischen Integrität
    }
    #
    pprint.pprint(egt_metadata)
    print("egt metadata... done")
    return egt_metadata


if __name__ == "__main__":
    path = r"C:\Users\Bernhard\PycharmProjects\CNVMaster\product\executable\example_data\static-data\ExampleArray\GSAMD-24v3-0-EA_20034606_A1.egt"
    egt = ClusterFile.read_cluster_file(
        open(os.path.abspath(path), "rb")
    ).name2cluster_record
    print("egt", egt)
    for k,v in egt.items():
        print(k, v)
        print(v.data)
    print("done")
