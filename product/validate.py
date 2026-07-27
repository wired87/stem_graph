import csv
from pathlib import Path


def extract_array_name_from_tsv(sample_table_path: str | Path) -> str:
    """
    Liest den eindeutigen Array_Name aus der übergebenen TSV-Datei aus.

    Verhält sich strikt: Erwartet die Spalte 'Array_Name', ignoriert Kommentare,
    und wirft einen ValueError bei Formatfehlern oder Konflikten.
    """
    #
    path_obj = Path(sample_table_path)
    if not path_obj.exists():
        raise ValueError("Sample-Tabelle (.tsv) wurde auf dem Dateisystem nicht gefunden.")
    try:
        with open(path_obj, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')

            # 1. Header-Validierung
            if not reader.fieldnames or 'Array_Name' not in reader.fieldnames:
                raise ValueError(
                    "Ungültiges Dateiformat: Die Pflichtspalte 'Array_Name' fehlt im Header der TSV-Datei.")

            unique_array_names = set()
            for row in reader:
                name_val = row.get('Array_Name')
                # Ignoriere leere Felder, leere Zeilen oder Zeilen, die als Kommentar starten
                if name_val and name_val.strip() and not name_val.strip().startswith('#'):
                    unique_array_names.add(name_val.strip())

            # 2. Inhalts-Validierung
            if not unique_array_names:
                raise ValueError(
                    "Die Sample-Tabelle enthält keine gültigen Datenzeilen oder die Spalte 'Array_Name' ist überall leer.")


            # Wenn alles valide ist, den exakten Typ zurückgeben
            return list(unique_array_names)

    except ValueError:
        # Re-raise bekannte Validierungsfehler direkt
        raise
    except Exception as e:
        # Verpacke unerwartete I/O- oder Parsing-Fehler
        raise ValueError(f"Die Sample-Tabelle konnte nicht gelesen werden: {str(e)}")


def extract_genome_version(input_dir: str | Path) -> str:
    """
    Scannt das Eingabeverzeichnis nach Illumina-Manifestdateien (.bpm oder .csv)
    und ermittelt anhand standardisierter Namenskonventionen die Genomversion.

    Gibt 'hg19' oder 'hg38' zurück. Erreicht keine Erkennung, wird 'hg19' als Fallback genutzt.
    """
    path_obj = Path(input_dir)
    if not path_obj.exists():
        raise ValueError(f"Verzeichnis {input_dir} existiert nicht.")

    # 1. Alle potenziellen Manifest-Dateien auflisten
    manifest_files = [
        f.name.lower() for f in path_obj.iterdir()
        if f.is_file() and (f.name.endswith('.bpm') or f.name.endswith('.csv') or '.csv' in f.name)
    ]

    if not manifest_files:
        print("Meldung: Keine Manifestdatei (.bpm/.csv) zur Genom-Erkennung gefunden. Nutze Fallback 'hg19'.")
        return "hg19"

    # 2. Untersuchung der Dateinamen auf hg38-Muster
    # Illumina hg38 Manifeste enden üblicherweise auf 'A2' (z.B. ..._A2.bpm)
    for filename in manifest_files:
        # Bereinige die Dateiendung für die Überprüfung der Endung des Basisnamens
        base_name = filename.split('.')[0]

        if "hg38" in filename or "grch38" in filename or base_name.endswith("a2"):
            return "hg38"

    # 3. Untersuchung auf hg19-Muster (Endung auf 'A1', 'hg19' oder 'grch37')
    for filename in manifest_files:
        base_name = filename.split('.')[0]
        if "hg19" in filename or "grch37" in filename or base_name.endswith("a1"):
            return "hg19"

    # Fallback, falls ein valides Manifest da ist, aber kein klares Muster erkannt wurde
    print("Meldung: Genomversion nicht eindeutig aus Manifestnamen lesbar. Nutze Standard 'hg19'.")
    return "hg19"



