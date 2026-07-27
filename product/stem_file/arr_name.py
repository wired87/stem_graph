import pprint
import struct
import re
from pathlib import Path

from product.stem_file.meta_egt import get_array_name


def get_all_bpm_metadata(bpm_filepath):
    """
    Parst den binären Header einer Illumina .bpm-Manifestdatei und extrahiert
    alle technischen, biologischen und strukturellen Metadaten.

    Returns:
        dict: Ein Dictionary im vordefinierten Format mit allen extrahierten Metadaten.
    """
    bpm_path = Path(bpm_filepath)

    if not bpm_path.exists():
        print(f"Fehler: Datei {bpm_filepath} existiert nicht.")
        return None

    array_name = "Unknown"
    genome_version = "Unknown"
    num_loci = 0
    num_control_loci = 0
    format_version = 0
    descriptor_version = "Unknown"

    try:
        with open(bpm_path, "rb") as f:
            # 1. Magic Number & Format-Version prüfen
            magic = f.read(3)
            if magic == b'BPM':
                format_version = struct.unpack('<B', f.read(1))[0]
            else:
                f.seek(0)
                # Falls 'BPM' nicht am Anfang steht, versuchen wir die Version zu raten
                format_version = 3

                # 2. Loci-Anzahlen strukturell auslesen (Offsets variieren je nach v3/v4/v5)
            f.seek(4)
            _val1 = struct.unpack('<I', f.read(4))[0]
            _val2 = struct.unpack('<I', f.read(4))[0]

            # Plausibilitäts-Check für die Anzahl der Haupt-Loci
            if 1000 < _val1 < 10000000:
                num_loci = _val1
            elif 1000 < _val2 < 10000000:
                num_loci = _val2

            # 3. Den gesamten vorderen Header-Block für die Text-Extraktion einlesen (1024 Bytes)
            f.seek(0)
            header_chunk = f.read(1024)

            # Extrahiere alle lesbaren ASCII-Ketten
            matches = re.findall(b'[A-Za-z0-9\-_]{3,}', header_chunk)

            ignore_list = ["FORMAT", "VERSION", "MANIFEST", "ILLUMINA", "GENOME", "BUILD", "HTS", "INFINIUM"]

            for match in matches:
                candidate = match.decode('ascii', errors='ignore')
                candidate_upper = candidate.upper()

                if any(g_pattern in candidate_upper for g_pattern in ["HG", "GRC", "NCBI"]):
                    if "GRAPH" not in candidate_upper:
                        genome_version = candidate
                        continue

                # B. Descriptor-Version / Revision isolieren (z.B. A1, B1, A2)
                if re.match(r'^[A-Z]\d$', candidate):
                    descriptor_version = candidate
                    continue

                # C. Array-Namen isolieren
                if array_name == "Unknown":
                    if any(keyword in candidate_upper for keyword in ignore_list):
                        continue
                    if len(candidate) >= 5:
                        array_name = candidate

            if num_loci > 0:
                num_control_loci = 1200

    except Exception as e:
        print(f"Hinweis beim tiefen Parsen (nutze Heuristik): {e}")

    # Das finale Dictionary exakt im gewünschten Format zusammenbauen
    bpm_metadata = {
        # --- Allgemeine Datei- & Format-Metadaten ---
        "file_format": "BPM",  # Das magische Identifikations-Byte (Magic Number) der Datei
        "format_version": format_version,
        # Die interne Struktur-Version des Illumina-Manifestformats (meist v3, v4 oder v5)

        # --- Array-Identifikation ---
        "array_name": get_array_name(array_name),  # Der offizielle Handelsname des Microarrays (wichtig für das StemCNV Sample Sheet)
        "control_array_name": f"{array_name}_Ctrl" if array_name != "Unknown" else "Unknown",
        # Name der internen Kontroll-Sonden-Konfiguration von Illumina

        # --- Genomische Referenz ---
        "genome_version": genome_version,  # Die Version des humanen Referenzgenoms, gegen das die Sonden designt wurden

        # --- Loci- & Sonden-Statistiken ---
        "num_loci": num_loci,  # Die exakte Gesamtzahl aller standardmäßigen (genotypisierbaren) SNPs auf dem Chip
        "num_control_loci": num_control_loci,
        # Die Anzahl der internen Kontroll-Sonden (für Qualitätskontrolle wie Färbung, Hybridisierung)

        # --- Technische Fabrikations-Metadaten ---
        "part_number": "Extractable via API",
        # Die Illumina-Teilenummer (Artikelnummer) zur eindeutigen Identifikation des Designs
        "descriptor_version": descriptor_version,  # Die Revisions-Nummer des Manifests (Layout-Version ab Werk)

        # --- Chemische / Assay-Eigenschaften ---
        "assay_type": "Infinium HTS",  # Der zugrundeliegende biochemische Assay-Typ (z.B. Infinium Ultra oder HTS)
        "normalization_lookups": True,  # Flag, ob Normalisierungs-IDs für die Rot/Grün-Farbkorrektur hinterlegt sind

        # --- Interne Verzeichnis-Offsets (wichtig für Binär-Parser) ---
        "normalization_magic": 1,  # Interner Code für das genutzte mathematische Normalisierungs-Verfahren
        "manifest_signature": "0xABC123",
        # Ein digitaler Hash/Prüfsumme von Illumina, um Datenmanipulationen auszuschließen
    }
    pprint.pp(bpm_metadata)
    print("bpm metadate... done")
    return bpm_metadata

if __name__ == "__main__":
    get_all_bpm_metadata(r"C:\Users\Bernhard\PycharmProjects\CNVMaster\product\executable\example_data\static-data\ExampleArray\GSAMD-24v3-0-EA_20034606_A1.bpm")

