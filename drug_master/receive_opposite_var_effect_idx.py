def variant_directionality_drug_mechanism_of_action_opposite(
        variant_effect: str,
        chembl_mechanisms: list[str]) -> list[int]:
    """
    Findet die Indizes von ChEMBL-Mechanismen (MoA), die der Richtung eines
    Open Targets Variant Effects entgegengesetzt (opposite) wirken.
    """
    effect = variant_effect.lower()

    opposing_map = {
        "gain_of_function": ["antagonist", "inhibitor", "suppressor", "blocker", "downregulator"],
        "increased_functionality": ["antagonist", "inhibitor", "suppressor", "blocker", "downregulator"],

        "loss_of_function": ["agonist", "activator", "inducer", "stimulator", "upregulator"],
        "decreased_functionality": ["agonist", "activator", "inducer", "stimulator", "upregulator"]
    }

    if effect not in opposing_map:
        print("invalid effect:", effect)
        return []

    target_opposites = opposing_map[effect]

    # Indizes der ChEMBL-Mechanismen finden, die ein gegensätzliches Keyword enthalten
    opposing_indices = [
        idx for idx, mech in enumerate(chembl_mechanisms)
        if any(opposite in mech.lower() for opposite in target_opposites)
    ]

    return opposing_indices