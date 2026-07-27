"""

TPSA (Topological Polar Surface Area): Zeigt, wie groß die polare Oberfläche des Moleküls ist. Ein extrem wichtiger Grenzwert: Liegt der Wert unter $140\text{ \AA}^2$, kann das Molekül Zellmembranen gut durchdringen. Liegt er unter $90\text{ \AA}^2$, kann es sogar die Blut-Hirn-Schranke passieren – essenziell, wenn du Ionenkanäle im zentralen Nervensystem manipulieren willst.H-Donoren & H-Akzeptoren: Die Anzahl der Wasserstoffbrückenbindungen. Sie sind zusammen mit dem Molekulargewicht und LogP die Eckpfeiler der Lipinski's Rule of 5, die voraussagt, ob eine Chemikalie überhaupt als Medikament im Körper überleben kann.Rotatable Bonds (Drehbare Bindungen): Je flexibler ein Molekül ist (viele drehbare Bindungen), desto schwerer hat es eine feste Bindung, da es sich in viele Konformationen "verbiegen" kann. Weniger als 10 ist hier der pharmakologische Richtwert.QED (Quantitative Estimate of Drug-likeness): Ein von RDKit berechneter Index zwischen 0 und 1. Er fasst alle physikochemischen Eigenschaften zusammen und gibt an, wie "medikamentenähnlich" die Struktur ist (je näher an 1, desto besser).

"""

from rdkit import Chem
from rdkit.Chem import Descriptors, QED


def process_smiles(smiles_string: str = "COc1cc2nc(N3CCN(C(=O)c4ccco4)CC3)nc(N)c2cc1OC") -> dict:
    """Analyseiert einen SMILES-String mit RDKit auf alle für die EDEn-Pipeline

    relevanten pharmakochemischen Eigenschaften (Drug-Likeness).

    :param smiles_string: Der chemische Struktur-String (Standard ist Prazosin)
    :return: Dictionary mit den berechneten Deskriptoren oder leeres Dict bei Fehler
    """
    # 1. Sicherheits-Check: Kann RDKit das Molekül parsen?
    mol = Chem.MolFromSmiles(smiles_string)
    if mol is None:
        print(f"❌ Fehler: Ungültiger SMILES-String übergeben: {smiles_string}")
        return {}

    # 2. Berechnung der erweiterten Key-Performance-Indikatoren (KPIs)
    analysis_results = {
        "smiles": smiles_string,

        # Basis-Eigenschaften
        "molecular_weight": float(Descriptors.MolWt(mol)),
        "log_p": float(Descriptors.MolLogP(mol)),  # Oktanol-Wasser-Partitionskoeffizient

        # Membran- und Barriere-Gängigkeit
        "tpsa": float(Descriptors.TPSA(mol)),  # Polare Oberfläche in Angström²

        # Lipinski-Regel Komponenten
        "h_bond_donors": int(Descriptors.NumHDonors(mol)),  # Wasserstoffbrücken-Donoren
        "h_bond_acceptors": int(Descriptors.NumHAcceptors(mol)),  # Wasserstoffbrücken-Akzeptoren

        # Flexibilität und Bindungsdynamik
        "rotatable_bonds": int(Descriptors.NumRotatableBonds(mol)),  # Drehbare Bindungen
        "aromatic_rings": int(Descriptors.NumAromaticRings(mol)),  # Anzahl aromatischer Ringstrukturen

        # Gesamtbewertung
        "qed_score": float(QED.qed(mol))  # Drug-likeness Index (0.0 bis 1.0)
    }

    # 3. Quick-Check für die Logik-Konsole ausgeben
    print(f"--- Analyse für {smiles_string[:15]}... abgeschlossen ---")
    print(f"Gewicht: {analysis_results['molecular_weight']:.2f} g/mol")
    print(f"LogP (Fettlöslichkeit): {analysis_results['log_p']:.2f}")
    print(f"TPSA (Zellgängigkeit): {analysis_results['tpsa']:.2f} Å²")
    print(f"QED-Score (Wirkstoff-Qualität): {analysis_results['qed_score']:.4f}")

    return analysis_results


if __name__ == "__main__":
    # Testlauf mit dem Standard-SMILES (Prazosin - ein Alphablocker, der auch Ionenkanäle moduliert)
    drug_properties = process_smiles()