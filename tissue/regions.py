"""
Static UBERON major-region map — no embedder import (safe for DRF startup).

Prompt: create server drf app; organs list for gui tissue selector.
"""


def get_major_uberon_regions() -> dict[str, str]:
    """Primary high-level UBERON body regions and major organs (English)."""
    return {
        "UBERON:0001017": "Central nervous system",
        "UBERON:0000955": "Brain",
        "UBERON:0000033": "Head",
        "UBERON:0001690": "Ear",
        "UBERON:0000970": "Eye",
        "UBERON:0002101": "Limbs",
        "UBERON:0002387": "Foot",
        "UBERON:0002389": "Hand",
        "UBERON:0000978": "Leg",
        "UBERON:0002102": "Arm",
        "UBERON:0000948": "Heart",
        "UBERON:0002048": "Lung",
        "UBERON:0002107": "Liver",
        "UBERON:0002113": "Kidney",
        "UBERON:0000945": "Stomach",
        "UBERON:0001242": "Intestine",
        "UBERON:0000974": "Thorax",
        "UBERON:0000916": "Abdomen",
        "UBERON:0001272": "Pelvis",
        "UBERON:0001009": "Circulatory system",
        "UBERON:0001007": "Digestive system",
        "UBERON:0002405": "Immune system",
        "UBERON:0001013": "Adipose tissue",
        "UBERON:0002193": "Skin",
    }

def get_major_brain_uberon_regions() -> dict[str, str]:
    return {
        "UBERON:0000955": "Brain",
        "UBERON:0001017": "Central nervous system",

        # Major divisions
        "UBERON:0001890": "Forebrain",
        "UBERON:0001891": "Midbrain",
        "UBERON:0001896": "Hindbrain",

        # Cerebral cortex
        "UBERON:0000956": "Cerebral cortex",
        "UBERON:0001870": "Telencephalon",

        # Limbic system
        "UBERON:0002421": "Hippocampus",
        "UBERON:0001872": "Amygdala",
        "UBERON:0001898": "Hypothalamus",

        # Deep brain structures
        "UBERON:0001897": "Thalamus",
        "UBERON:0002435": "Basal ganglion",
        "UBERON:0001882": "Striatum",

        # Brainstem
        "UBERON:0002298": "Brainstem",
        "UBERON:0000988": "Pons",
        "UBERON:0002726": "Medulla oblongata",

        # Cerebellum
        "UBERON:0002037": "Cerebellum",

        # Ventricular system
        "UBERON:0002084": "Lateral ventricle",
        "UBERON:0002285": "Third ventricle",
        "UBERON:0002286": "Fourth ventricle",

        # Sensory systems
        "UBERON:0001950": "Olfactory bulb",
        "UBERON:0002430": "Retina",

        # White matter
        "UBERON:0002420": "Corpus callosum",

        # Functional cortex regions
        "UBERON:0002771": "Frontal lobe",
        "UBERON:0002428": "Parietal lobe",
        "UBERON:0002429": "Temporal lobe",
        "UBERON:0002431": "Occipital lobe",
        "UBERON:0002870": "Insula",
    }