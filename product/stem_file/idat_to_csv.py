
import struct
import re
import csv
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

CHIP_TYPE_TO_ARRAY_NAME = {
    "Multi-EthnicGlobal-8_v1-0": "GSA-24v1-0",
    "GlobalScreeningArray_v1-0": "GSA-24v1-0",
    "GSAMD-24v1-0": "GSAMD-24v1-0",
    "GSAMD-24v2-0": "GSAMD-24v2-0",
    "GSAMD-24v3-0": "GSAMD-24v3-0",
    "GSA-24v3-0": "GSA-24v3-0",
    "InfiniumOmniExpress-24v1-2": "OmniExpress-24v1-2",
    "InfiniumOmniExpress-24v1-3": "OmniExpress-24v1-3",
    "Omni25-8v1-3": "Omni2.5-8v1-3",
    "Omni5-4v1-2": "Omni5-4v1-2",
    "InfiniumPsychArray-24v1-1": "PsychArray-24v1-1",
    "InfiniumPsychExome-24v1-2": "PsychExome-24v1-2",
    "OncoArray-500K": "OncoArray-500K",
    "MethylationEPIC": "EPIC-8v1-0",
    "MethylationEPIC_v2": "EPIC-8v2-0"
}


def parse_idat(file_path):
    """Parst IDAT v3 vollständig und extrahiert Metadaten + Intensitäten."""
    try:
        with open(file_path, 'rb') as f:
            magic = f.read(4)
            if magic != b'IDAT':
                raise ValueError("Keine valide Illumina IDAT-Datei (Magic Number fehlt).")

            version = struct.unpack('<Q', f.read(8))[0]
            num_fields = struct.unpack('<I', f.read(4))[0]

            fields = {}
            for _ in range(num_fields):
                field_id = struct.unpack('<H', f.read(2))[0]
                field_offset = struct.unpack('<Q', f.read(8))[0]
                fields[field_id] = field_offset

            metadata = {
                "file_path": str(file_path),
                "file_format": "IDAT",
                "format_version": version,
                "total_fields_in_header": num_fields
            }

            # Feld 1000: Exakter Chip-Typ aus dem Header extrahieren
            if fields.get(1000):
                f.seek(fields[1000])
                str_len = struct.unpack('<B', f.read(1))[0]
                metadata["chip_type"] = f.read(str_len).decode('ascii', errors='ignore')
                metadata["derived_array_name"] = CHIP_TYPE_TO_ARRAY_NAME.get(metadata["chip_type"],
                                                                             metadata["chip_type"])
            else:
                metadata["chip_type"] = "Unknown"
                metadata["derived_array_name"] = "Unknown"

            # Feld 402: Chip Barcode (Sentrix ID)
            if fields.get(402):
                f.seek(fields[402])
                str_len = struct.unpack('<B', f.read(1))[0]
                metadata["chip_barcode"] = f.read(str_len).decode('ascii', errors='ignore')
            else:
                metadata["chip_barcode"] = "Unknown"

            # Feld 403: Chip Position (Sentrix Position, z.B. R11C02)
            if fields.get(403):
                f.seek(fields[403])
                str_len = struct.unpack('<B', f.read(1))[0]
                metadata["chip_position"] = f.read(str_len).decode('ascii', errors='ignore')
            else:
                metadata["chip_position"] = "Unknown"

            # Feld 406: Scan-Zeitstempel
            if fields.get(406):
                f.seek(fields[406])
                str_len = struct.unpack('<B', f.read(1))[0]
                metadata["scan_date"] = f.read(str_len).decode('ascii', errors='ignore')
            else:
                metadata["scan_date"] = "Unknown"

            # Feld 102: Anzahl der Loci/Sonden
            num_snps = 0
            if fields.get(102):
                f.seek(fields[102])
                num_snps = struct.unpack('<I', f.read(4))[0]
                metadata["num_loci_measured"] = num_snps
            else:
                metadata["num_loci_measured"] = 0

            # Farbkanal-Konvention abfragen
            file_name_upper = Path(file_path).name.upper()
            metadata["color_channel"] = "Green" if "GRN" in file_name_upper else (
                "Red" if "RED" in file_name_upper else "Unknown")

            # Fallback per Regex, falls 400er-Felder blockieren
            if metadata["chip_barcode"] == "Unknown" or metadata["chip_position"] == "Unknown":
                f.seek(0)
                buffer = f.read(4096)
                if metadata["chip_position"] == "Unknown":
                    pos_match = re.search(b'R\d{2}C\d{2}', buffer)
                    if pos_match: metadata["chip_position"] = pos_match.group(0).decode('ascii')
                if metadata["chip_barcode"] == "Unknown":
                    name_match = re.search(b'\d{12}', buffer)
                    if name_match: metadata["chip_barcode"] = name_match.group(0).decode('ascii')

            # --- Sonden-Messwerte laden ---
            probe_ids, mean_intensities, std_devs, bead_counts = [], [], [], []

            if num_snps > 0:
                if fields.get(104):  # Sonden-IDs (Feld 104)
                    f.seek(fields[104])
                    probe_ids = [struct.unpack('<I', f.read(4))[0] for _ in range(num_snps)]
                else:
                    probe_ids = list(range(num_snps))

                if fields.get(107):  # Mittlere Intensität (Feld 107)
                    f.seek(fields[107])
                    mean_intensities = [struct.unpack('<H', f.read(2))[0] for _ in range(num_snps)]
                else:
                    mean_intensities = [0] * num_snps

                if fields.get(108):  # Standardabweichung (Feld 108)
                    f.seek(fields[108])
                    std_devs = [struct.unpack('<H', f.read(2))[0] for _ in range(num_snps)]
                else:
                    std_devs = [0] * num_snps

                if fields.get(109):  # Bead Count (Feld 109)
                    f.seek(fields[109])
                    bead_counts = [struct.unpack('<B', f.read(1))[0] for _ in range(num_snps)]
                else:
                    bead_counts = [0] * num_snps

            probe_data = []
            for i in range(num_snps):
                probe_data.append({
                    "Illumina_ID": probe_ids[i] if i < len(probe_ids) else "N/A",
                    "Mean_Intensity": mean_intensities[i] if i < len(mean_intensities) else 0,
                    "StdDev": std_devs[i] if i < len(std_devs) else 0,
                    "BeadCount": bead_counts[i] if i < len(bead_counts) else 0
                })

            return metadata, probe_data
    except Exception as e:
        raise Exception(f"Parser-Fehler: {str(e)}")


def save_to_csv(metadata, probe_data, output_path):
    """Exportiert Metadaten als Kommentar-Header und Tabellendaten in die CSV."""
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["# === ILLUMINA IDAT METADATA HEADERS ==="])
        for key, val in metadata.items():
            writer.writerow([f"# {key}", val])
        writer.writerow(["# ======================================"])
        writer.writerow([])

        writer.writerow(["Illumina_ID", "Mean_Intensity", "StdDev", "BeadCount"])
        for row in probe_data:
            writer.writerow([row["Illumina_ID"], row["Mean_Intensity"], row["StdDev"], row["BeadCount"]])


class IdatViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Illumina IDAT Viewer & Converter")
        self.root.geometry("750x550")

        style = ttk.Style()
        style.theme_use('clam')

        # UI Top
        top = ttk.Frame(root, padding=15)
        top.pack(fill=tk.X)
        ttk.Label(top, text="IDAT-Datei:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        self.file_entry = ttk.Entry(top, width=50)
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(top, text="Datei öffnen", command=self.browse_file).pack(side=tk.RIGHT)

        # UI Mid
        mid = ttk.LabelFrame(root, text=" Extrahierte Daten-Vorschau (Inkl. Feld 1000) ", padding=15)
        mid.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        self.txt_metadata = tk.Text(mid, font=("Consolas", 10), bg="#ffffff", fg="#333333", bd=1, relief=tk.SOLID)
        scroll = ttk.Scrollbar(mid, command=self.txt_metadata.yview)
        self.txt_metadata.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_metadata.pack(fill=tk.BOTH, expand=True)
        self.txt_metadata.insert(tk.END, "Wähle eine .idat-Datei aus.")
        self.txt_metadata.config(state=tk.DISABLED)

        # UI Bot
        bot = ttk.Frame(root, padding=15)
        bot.pack(fill=tk.X)
        self.lbl_status = ttk.Label(bot, text="Bereit.", font=("Segoe UI", 9, "italic"))
        self.lbl_status.pack(side=tk.LEFT)
        self.btn_export = ttk.Button(bot, text="CSV lokal speichern", command=self.export_csv, state=tk.DISABLED)
        self.btn_export.pack(side=tk.RIGHT)

    def browse_file(self):
        fp = filedialog.askopenfilename(filetypes=[("Illumina IDAT Files", "*.idat")])
        if fp:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, fp)
            try:
                self.metadata, self.probe_data = parse_idat(fp)
                self.txt_metadata.config(state=tk.NORMAL)
                self.txt_metadata.delete('1.0', tk.END)

                view_text = "=== EXTRAHIERTE METADATEN ===\n"
                for k, v in self.metadata.items():
                    view_text += f"{k.upper()}: {v}\n"
                view_text += f"\n=== INTENSITÄTEN-PREVIEW (Erste 5 Zeilen) ===\n"
                view_text += f"{'Illumina_ID':<12} | {'Mean_Intensity':<15} | {'StdDev':<8} | {'BeadCount':<8}\n" + "-" * 55 + "\n"
                for row in self.probe_data[:5]:
                    view_text += f"{row['Illumina_ID']:<12} | {row['Mean_Intensity']:<15} | {row['StdDev']:<8} | {row['BeadCount']:<8}\n"

                self.txt_metadata.insert(tk.END, view_text)
                self.txt_metadata.config(state=tk.DISABLED)
                self.btn_export.config(state=tk.NORMAL)
                self.lbl_status.config(text=f"Parsing abgeschlossen! Sonden: {len(self.probe_data)}")
            except Exception as e:
                messagebox.showerror("Fehler", str(e))

    def export_csv(self):
        suggested_name = f"IDAT_Export_{self.metadata.get('chip_barcode', 'Data')}_{self.metadata.get('chip_position', '')}.csv"
        out = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV-Datei", "*.csv")],
                                           initialfile=suggested_name)
        if out:
            try:
                save_to_csv(self.metadata, self.probe_data, out)
                messagebox.showinfo("Erfolg", f"Datei erfolgreich lokal gespeichert unter:\n{out}")
            except Exception as e:
                messagebox.showerror("Fehler beim Export", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = IdatViewerApp(root)
    root.mainloop()