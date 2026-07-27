import struct
from pathlib import Path


def get_sex_from_ida(file_path: str | Path, y_threshold: float = 1000.0) -> str:
    """
    Ultraschnelle Variante: Lädt die IDAT-Datenblöcke am Stück in den Speicher
    und parst sie dort nativ. Reduziert I/O-Overhead gegen Null.
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Die IDAT-Datei wurde nicht gefunden: {path_obj}")

    with open(path_obj, 'rb') as f:
        # 1. Header validieren
        magic = f.read(4)
        if magic != b'IDAT':
            raise ValueError("Keine valide Illumina IDAT-Datei.")

        f.seek(12)
        num_fields = struct.unpack('<I', f.read(4))[0]

        # 2. Feld-Verzeichnis einlesen
        fields = {}
        for _ in range(num_fields):
            field_id = struct.unpack('<H', f.read(2))[0]
            field_offset = struct.unpack('<Q', f.read(8))[0]
            fields[field_id] = field_offset

        # 3. Anzahl der Loci holen (Feld 102)
        if 102 not in fields or 103 not in fields or 104 not in fields:
            raise KeyError("Erforderliche IDAT-Felder (102, 103, 104) fehlen.")

        f.seek(fields[102])
        num_snps = struct.unpack('<I', f.read(4))[0]

        # =================================================================
        # DER TURBO: Ganze Blöcke auf einmal in den RAM laden
        # =================================================================
        # Feld 103: Alle IDs am Stück lesen (4 Bytes pro ID)
        f.seek(fields[103])
        ids_block = f.read(num_snps * 4)

        # Feld 104: Alle Intensitäten am Stück lesen (2 Bytes pro Intensität)
        f.seek(fields[104])
        intensities_block = f.read(num_snps * 2)

    # 4. Auswertung im RAM (via schnellem Iterator statt f.seek)
    y_intensity_sum = 0.0
    y_probe_count = 0

    # iter_unpack liest den gesamten Bytestream in C-Geschwindigkeit durch
    ids_iterator = struct.iter_unpack('<I', ids_block)
    intensities_iterator = struct.iter_unpack('<H', intensities_block)

    # Reiner Speicher-Loop (Kein I/O!)
    for (probe_id,), (intensity,) in zip(ids_iterator, intensities_iterator):

        # Deine Y-Chromosom Kriterien (Integer-basiert)
        if 9000000 <= probe_id <= 9999999:  # <-- Hier deine echten Y-IDs anpassen
            y_intensity_sum += intensity
            y_probe_count += 1

    # 5. Berechnung
    avg_y_intensity = (y_intensity_sum / y_probe_count) if y_probe_count > 0 else 0

    return "male" if avg_y_intensity >= y_threshold else "female"