def read_idat_string(f, offset):
    """
    Hilfsfunktion, die das variable Längen-Byte (Base-128) von Illumina liest
    und den anschließenden ASCII-String extrahiert.
    """
    if not offset:
        return "Unknown"
    try:
        f.seek(offset)

        # Illumina Variable-Length Integer Decoding (Base-128 Variant)
        shift = 0
        result = 0
        while True:
            byte = struct.unpack('<B', f.read(1))[0]
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7

        string_length = result
        if string_length == 0 or string_length > 255:  # Schutz vor Binärmüll
            return "Unknown"

        raw_bytes = f.read(string_length)
        decoded = raw_bytes.decode('ascii', errors='ignore').strip()

        # Falls Müll-Zeichen enthalten sind, verwerfen
        if any(ord(c) < 32 or ord(c) > 126 for c in decoded):
            return "Unknown"
        return decoded
    except Exception:
        return "Unknown"


def determine_array_reliably(num_snps, barcode, layout_string):
    """
    Kaskaden-Weiche: Bestimmt den echten Array-Namen anhand der Sondenanzahl,
    des Layouts und des Barcode-Präfixes.
    """
    barcode_str = str(barcode)
    layout_upper = str(layout_string).upper()

    # 1. Haupt-Weiche über die Sondenanzahl (Offizielle Illumina-Manifest-Größen)

    # Global Diversity Array (GDA) - Deine Variante mit Exom/Klinik-Content
    if 1580000 <= num_snps <= 1620000:
        return "GSAMD-24v3-0"  # Matcht 1,600,107 Loci

    elif 1900000 <= num_snps <= 2050000:
        return "GDA-8v1-0"

    # Global Screening Array (GSA v3)
    elif 730000 <= num_snps <= 765000:
        return "GSAMD-24v3-0"

        # Global Screening Array (GSA v2)
    elif 711000 <= num_snps <= 725000:
        return "GSA-24v2-0"

    elif 695000 <= num_snps <= 710999:
        if barcode_str.startswith(("206", "200")):
            return "GSA-24v1-0"
        return "OmniExpress-24v1-3"

    # PsychArray
    elif 580000 <= num_snps <= 598000:
        return "PsychArray-24v1-1"

    # Omni 2.5
    elif 2400000 <= num_snps <= 2500000:
        return "Omni2.5-8v1-3"

    else:
        raise ValueError("Pixel range out of bounds...")


def read_idat_metadata(file_path):
    """
    Parst den binären Header einer Illumina .idat-Datei und extrahiert
    alle technischen Mess- und Probenmetadaten (Optimiert für IDAT v3).
    """
    path_obj = Path(file_path)
    print(f"\n==================================================")
    print(f" STARTE IDAT-PARSING FÜR:\n {path_obj.name}")
    print(f"==================================================")

    try:
        with open(file_path, 'rb') as f:
            # 1. Magic Number Validierung
            magic = f.read(4)
            if magic != b'IDAT':
                raise ValueError("Keine valide Illumina IDAT-Datei.")

            # 2. Version und Anzahl der Felder lesen
            version = struct.unpack('<Q', f.read(8))[0]
            num_fields = struct.unpack('<I', f.read(4))[0]

            # 3. Die Feld-Tabelle (Index-Verzeichnis) einlesen
            fields = {}
            for _ in range(num_fields):
                field_id = struct.unpack('<H', f.read(2))[0]
                field_offset = struct.unpack('<Q', f.read(8))[0]
                fields[field_id] = field_offset

            # 4. Sonden-Anzahl sicher auslesen (Feld 102)
            num_snps = 0
            if fields.get(102):
                f.seek(fields[102])
                chunk = f.read(4)
                if len(chunk) == 4:
                    num_snps = struct.unpack('<I', chunk)[0]

            # 5. Strings über Hilfsfunktion auslesen
            raw_chip_type = read_idat_string(f, fields.get(1000))
            chip_name_header = read_idat_string(f, fields.get(402))
            chip_layout_header = read_idat_string(f, fields.get(403))
            run_date = read_idat_string(f, fields.get(406))
            scanner_id = read_idat_string(f, fields.get(401))

            # 6. Dateinamen-Parsing für Barcode und Position (Höchste Priorität bei Fehlern)
            file_name = path_obj.stem
            parts = file_name.split('_')
            chip_name_file = parts[0] if len(parts) > 0 else "Unknown"
            chip_pos_file = parts[1] if len(parts) > 1 else "Unknown"

            # Bereinigung: Wenn Header-Werte fehlen, nimm die sicheren Werte aus dem Dateinamen
            chip_name = chip_name_file if chip_name_file != "Unknown" else chip_name_header
            chip_pos = chip_pos_file if chip_pos_file != "Unknown" else chip_layout_header

            # 7. AUTOMATISCHE ABLEITUNG DES CODES FÜR STEMCNV
            array_name = determine_array_reliably(num_snps, chip_name, chip_layout_header)

            # Farbkanal ableiten
            file_name_upper = path_obj.name.upper()
            color_channel = "Green" if "GRN" in file_name_upper else ("Red" if "RED" in file_name_upper else "Unknown")

            # 8. MENSCHENLESBARE AUSGABE IM TERMINAL
            print("\n📋 GEFUNDENE IDENTIFIZIERTE METADATEN:")
            print(f"--------------------------------------------------")
            print(f" 📂 Datei-Format      : {magic.decode('ascii')} (Version {version})")
            print(f" 🚀 ABGELEITETER NAME : {array_name}  <-- [BERECHNET FÜR STEMCNV!]")
            print(f" 🏷️  Chip-Barcode (ID) : {chip_name}, {raw_chip_type}")
            print(f" 📍 Chip-Position     : {chip_pos}")
            print(f" 📐 Physisches Layout : {chip_layout_header}")
            print(f" 📊 Gemessene Sonden  : {num_snps:,} Loci")
            print(f" 🎨 Farbkanal         : {color_channel}")
            print(f" 📅 Scan-Datum        : {run_date}")
            print(f" 🖥️  Scanner-Kennung   : {scanner_id}")
            print(f"--------------------------------------------------\n")

    except Exception as e:
        print(f"❌ Fehler beim tiefen Parsen der IDAT: {e}")
        import traceback
        traceback.print_exc()
        return None

    metadata = {
        "file_format": "IDAT",
        "format_version": version,
        "array_name": array_name,  # Jetzt dynamisch berechnet!
        "chip_name": chip_name,
        "chip_pos": chip_pos,
        "num_loci_measured": num_snps,
        "color_channel": color_channel,
        "scan_date": run_date,
        "scanner_serial_number": scanner_id,
        "is_compressed": False,
        "intensity_data_type": "UInt16"
    }

    print(f"=== Parsing abgeschlossen. Resultat-Keys: {list(metadata.values())} ===\n")
    return metadata

import struct
from pathlib import Path


def read_idat_string(f, offset):
    """
    Hilfsfunktion, die das variable Längen-Byte (Base-128) von Illumina liest
    und den anschließenden ASCII-String extrahiert.
    """
    if not offset:
        return "Unknown"
    try:
        f.seek(offset)

        # Illumina Variable-Length Integer Decoding (Base-128 Variant)
        shift = 0
        result = 0
        while True:
            byte = struct.unpack('<B', f.read(1))[0]
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7

        string_length = result
        if string_length == 0 or string_length > 255:  # Schutz vor Binärmüll
            return "Unknown"

        raw_bytes = f.read(string_length)
        decoded = raw_bytes.decode('ascii', errors='ignore').strip()

        # Falls Müll-Zeichen enthalten sind, verwerfen
        if any(ord(c) < 32 or ord(c) > 126 for c in decoded):
            return "Unknown"
        return decoded
    except Exception:
        return "Unknown"


def determine_array_reliably(num_snps, barcode, layout_string):
    """
    Kaskaden-Weiche: Bestimmt den echten Array-Namen anhand der Sondenanzahl,
    des Layouts und des Barcode-Präfixes.
    """
    barcode_str = str(barcode)
    layout_upper = str(layout_string).upper()

    # 1. Haupt-Weiche über die Sondenanzahl (Offizielle Illumina-Manifest-Größen)

    # Global Diversity Array (GDA) - Deine Variante mit Exom/Klinik-Content
    if 1580000 <= num_snps <= 1620000:
        return "GSAMD-24v3-0"  # Matcht 1,600,107 Loci

    elif 1900000 <= num_snps <= 2050000:
        return "GDA-8v1-0"

    # Global Screening Array (GSA v3)
    elif 730000 <= num_snps <= 765000:
        return "GSAMD-24v3-0"

        # Global Screening Array (GSA v2)
    elif 711000 <= num_snps <= 725000:
        return "GSA-24v2-0"

    elif 695000 <= num_snps <= 710999:
        if barcode_str.startswith(("206", "200")):
            return "GSA-24v1-0"
        return "OmniExpress-24v1-3"

    # PsychArray
    elif 580000 <= num_snps <= 598000:
        return "PsychArray-24v1-1"

    # Omni 2.5
    elif 2400000 <= num_snps <= 2500000:
        return "Omni2.5-8v1-3"

    else:
        raise ValueError("Pixel range out of bounds...")


def read_idat_data(file_path):
    """
    Parst den binären Header einer Illumina .idat-Datei und extrahiert
    alle technischen Mess- und Probenmetadaten (Optimiert für IDAT v3).
    """
    path_obj = Path(file_path)
    print(f"\n==================================================")
    print(f" STARTE IDAT-PARSING FÜR:\n {path_obj.name}")
    print(f"==================================================")

    try:
        with open(file_path, 'rb') as f:
            # 1. Magic Number Validierung
            magic = f.read(4)
            if magic != b'IDAT':
                raise ValueError("Keine valide Illumina IDAT-Datei.")

            # 2. Version und Anzahl der Felder lesen
            version = struct.unpack('<Q', f.read(8))[0]
            num_fields = struct.unpack('<I', f.read(4))[0]

            # 3. Die Feld-Tabelle (Index-Verzeichnis) einlesen
            fields = {}
            for _ in range(num_fields):
                field_id = struct.unpack('<H', f.read(2))[0]
                field_offset = struct.unpack('<Q', f.read(8))[0]
                fields[field_id] = field_offset

            # 4. Sonden-Anzahl sicher auslesen (Feld 102)
            num_snps = 0
            if fields.get(102):
                f.seek(fields[102])
                chunk = f.read(4)
                if len(chunk) == 4:
                    num_snps = struct.unpack('<I', chunk)[0]

             # READ ROW DATA
            data = {}
            if num_snps > 0:
                if fields.get(103):
                    f.seek(fields[103])
                    raw_ids = f.read(num_snps * 4)
                    data["illumina_ids"] = list(struct.unpack(f'<{num_snps}I', raw_ids))

                # B. Intensitäten auslesen (Feld 104 -> 2 Bytes pro Wert, Unsigned Short)
                if fields.get(104):
                    f.seek(fields[104])
                    raw_intensities = f.read(num_snps * 2)
                    data["mean_intensities"] = list(struct.unpack(f'<{num_snps}H', raw_intensities))

                # C. Standardabweichungen auslesen (Feld 105 -> 2 Bytes pro Wert, Unsigned Short)
                if fields.get(105):
                    f.seek(fields[105])
                    raw_stddevs = f.read(num_snps * 2)
                    data["std_devs"] = list(struct.unpack(f'<{num_snps}H', raw_stddevs))

    except Exception as e:
        print(f"❌ Fehler beim tiefen Parsen der IDAT: {e}")
    print("idat keys found:", list(data.keys()), [len(i) for i in list(data.values())])
    return data

if __name__ == "__main__":
    read_idat_data()
