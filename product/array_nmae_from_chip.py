# Mapping von IDAT-Header ChipType zu offiziellem Array-Namen
CHIP_TYPE_TO_ARRAY_NAME = {
    # Global Screening Array (GSA) Familie
    "Multi-EthnicGlobal-8_v1-0": "GSA-24v1-0",
    "GlobalScreeningArray_v1-0": "GSA-24v1-0",
    "GSAMD-24v1-0": "GSAMD-24v1-0",
    "GSAMD-24v2-0": "GSAMD-24v2-0",
    "GSAMD-24v3-0": "GSAMD-24v3-0",
    "GSA-24v3-0": "GSA-24v3-0",

    # Omni / Whole Genome Familie
    "InfiniumOmniExpress-24v1-2": "OmniExpress-24v1-2",
    "InfiniumOmniExpress-24v1-3": "OmniExpress-24v1-3",
    "Omni25-8v1-3": "Omni2.5-8v1-3",
    "Omni5-4v1-2": "Omni5-4v1-2",

    # PsychArray / Exome / Onco
    "InfiniumPsychArray-24v1-1": "PsychArray-24v1-1",
    "InfiniumPsychExome-24v1-2": "PsychExome-24v1-2",
    "OncoArray-500K": "OncoArray-500K",

    # Methylierung (nur Vollständigkeitshalber, falls relevant)
    "MethylationEPIC": "EPIC-8v1-0",
    "MethylationEPIC_v2": "EPIC-8v2-0"
}


def get_array_name(chip_type_from_idat):
    """
    Sucht den passenden Array-Namen für die StemCNV-Config.
    Falls der exakte Typ nicht gefunden wird, wird der Originalwert zurückgegeben.
    """
    return CHIP_TYPE_TO_ARRAY_NAME.get(chip_type_from_idat, chip_type_from_idat)