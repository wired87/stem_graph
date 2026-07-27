import math


def calculate_electroceutical_synergy_score(drug_params: dict, protein_params: dict) -> float:
    """
    Calculates a heuristic synergy score [0.0 - 1.0] between a drug molecule
    and a target protein based on pharmacochemical and bioelectric constraints.

    Data Structures:
    ----------------
    drug_params = {
        "smiles": str,              # Chemical SMILES string
        "tpsa": float,              # Topological Polar Surface Area (from RDKit)
        "qed_score": float,         # Quantitative Estimate of Drug-likeness [0.0 - 1.0]
        "target_affinity_nm": float,# Measured IC50/Ki/Kd value against the target channel in nM
        "lowest_off_target_nm": float # Lowest measured affinity against ANY OTHER channel in nM
    }

    protein_params = {
        "uniprot_id": str,          # UniProt Accession Number
        "is_human": bool,           # Strict organism filter flag
        "gating_type": str          # "voltage-gated", "ligand-gated", etc.
    }
    """

    # --- 1. CRITICAL BIOLOGICAL FILTERS ---
    # In a human-targeted EDEn pipeline, non-human assays get penalized
    # unless no human data is available.
    organism_multiplier = 1.0 if protein_params.get("is_human", True) else 0.5

    # --- 2. AFFINITY COEFFICIENT (C_affinity) ---
    # We use an exponential decay function. An IC50 of 1nM -> ~1.0 score.
    # An IC50 of 10.000nM (10µM) -> near 0.0 score.
    target_affinity = drug_params.get("target_affinity_nm", 10000.0)
    # Avoid division by zero and cap extreme values
    target_affinity = max(0.1, target_affinity)
    c_affinity = math.exp(-target_affinity / 2000.0)

    # --- 3. SELECTIVITY COEFFICIENT (C_selectivity) ---
    # Selectivity Ratio = Off-Target-Affinity / Target-Affinity
    # Example: Target = 10nM, Off-Target = 1000nM -> Ratio = 100 (Highly Selective!)
    # Example: Target = 10nM, Off-Target = 5nM -> Ratio = 0.5 (Dangerous Off-Target!)
    lowest_off_target = drug_params.get("lowest_off_target_nm", 100000.0)

    if target_affinity >= lowest_off_target:
        # Drug binds stronger or equally to an unwanted target -> high side-effect risk
        c_selectivity = 0.1
    else:
        ratio = lowest_off_target / target_affinity
        # Logarithmic scaling to reward high selectivity ratios smoothly up to 1.0
        c_selectivity = min(1.0, math.log10(ratio) / 3.0)
        c_selectivity = max(0.1, c_selectivity)

    # --- 4. MEMBRANE PERMEABILITY COEFFICIENT (C_membrane) ---
    # Standard pharmaceutical rule: TPSA > 140 Å² cannot cross cell membranes easily.
    tpsa = drug_params.get("tpsa", 0.0)
    if tpsa <= 0.0:
        c_membrane = 0.1
    elif tpsa <= 140.0:
        c_membrane = 1.0  # Perfect window for general tissue membranes
    else:
        # Linear degradation for heavy polar surface areas
        c_membrane = max(0.0, 1.0 - ((tpsa - 140.0) / 100.0))

    # --- 5. MOLECULE-LIKENESS COEFFICIENT (C_drugness) ---
    # Direct use of RDKit's QED descriptor
    c_drugness = drug_params.get("qed_score", 0.5)

    # --- 6. FINAL MATHEMATICAL EQUATION ---
    final_score = c_affinity * c_selectivity * c_membrane * c_drugness * organism_multiplier

    # Ensure bounds constraint
    return min(1.0, max(0.0, float(final_score)))


# --- EXMPLE PIPELINE USAGE ---
if __name__ == "__main__":
    # Example A: Highly potent, highly selective, membrane-permeable drug (Prazosin-like profile)
    perfect_drug = {
        "smiles": "COc1cc2nc(N3CCN(C(=O)c4ccco4)CC3)nc(N)c2cc1OC",
        "tpsa": 105.5,
        "qed_score": 0.85,
        "target_affinity_nm": 1.9,  # Strong binding (1.9 nM)
        "lowest_off_target_nm": 5000.0  # Safe off-target distance
    }

    # Example B: "Dirty" drug with high side-effect risks and poor absorption
    poor_drug = {
        "smiles": "CC(=O)O...",
        "tpsa": 165.0,  # Too high, won't pass membrane easily
        "qed_score": 0.30,
        "target_affinity_nm": 1200.0,  # Weak binding
        "lowest_off_target_nm": 80.0  # Dangerous: Binds 15x stronger to an unwanted target!
    }

    target_ion_channel = {
        "uniprot_id": "P15823",
        "is_human": True,
        "gating_type": "voltage-gated"
    }

    score_a = calculate_electroceutical_synergy_score(perfect_drug, target_ion_channel)
    score_b = calculate_electroceutical_synergy_score(poor_drug, target_ion_channel)

    print(f"Synergy Score Drug A: {score_a:.4f}")  # Will be high (~0.6 - 0.8)
    print(f"Synergy Score Drug B: {score_b:.4f}")  # Will collapse near 0.0



