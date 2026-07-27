import re


def create_sample_data(raw_string: str) -> dict:
    """
    Erstellt aus einem String wie 'chr7: 55.229.255:G>T' ein
    strukturiertes Dictionary für die Ensembl-Abfrage.
    """
    # Regulärer Ausdruck, um Chromosom, Position und den Basenwechsel zu isolieren
    # Erlaubt flexible Leerzeichen innerhalb der Koordinaten
    pattern = r"(chr[0-9XYM]+):\s*([0-9.]+):\s*([A-Z]+>[A-Z]+)"

    match = re.search(pattern, raw_string)

    if not match:
        raise ValueError(f"String-Format ungültig oder konnte nicht gelesen werden: '{raw_string}'")

    chrom = match.group(1)
    # Entfernt die Tausenderpunkte aus der Zahl (z.B. 55.229.255 -> 55229255)
    position = int(match.group(2).replace(".", ""))
    base_change = match.group(3)

    # Rückgabe des Objekts, das deine Ensembl-Methode erwartet
    return {
        "chromosome": chrom,
        "genomic_position": position,
        "base_change_genomic": base_change
    }
