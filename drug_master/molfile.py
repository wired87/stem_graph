import base64
from rdkit import Chem
from rdkit.Chem import Draw
from rdkit.Chem import Descriptors
from rdkit.Chem import rdMolDescriptors



def generate_biochem_molecular_profile(molfile_string: str) -> dict:
    """
    Parses a raw MOLFILE block, generates a high-quality 2D visualization
    optimized for biochemical engineering inspection, and compiles structural
    validation fingerprints.

    Args:
        molfile_string (str): The raw structural MDL Molfile text block.

    Returns:
        dict: A single dictionary containing the base64 encoded visualization
              and useful molecular engineering metadata.
    """
    # 1. Parse the Molfile into a robust RDKit Molecule object
    # sanitize=True enforces chemical valence checks, aromaticity, and hybridization rules
    mol = Chem.MolFromMolBlock(molfile_string, sanitize=True)

    if mol is None:
        return {
            "success": False,
            "error": "Failed to parse Molfile. The structure may violate chemical valence rules."
        }

    # 2. Leverage Best Practices for Biochemical Visualizations
    # We configure the drawing options to explicitly show properties critical for
    # drug-target binding: stereochemical wrappers, atom numbering, and clear lone pairs/charges.
    drawer_options = Draw.rdMolDraw2D.MolDrawOptions()
    drawer_options.addAtomIndices = False  # Keep clean for pure structural overview
    drawer_options.addStereoAnnotation = True  # CRITICAL: Highlights R/S and E/Z configurations for docking
    drawer_options.includeRadicals = True  # Shows reactivity risks
    drawer_options.continuousHighlight = True

    # Generate 2D coordinates if they are missing or flat in the molfile
    Chem.rdDepictor.Compute2DCoords(mol)

    # Draw to an SVG canvas (scalable, crisp vector format for UIs or data pipelines)
    # 600x400 provides ideal spacing to avoid crowded atomic labels
    drawer = Draw.rdMolDraw2D.MolDraw2DSVG(600, 400)
    drawer.SetDrawOptions(drawer_options)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()

    svg_text = drawer.GetDrawingText()

    # Convert the SVG string to a Base64 URI string for seamless frontend injection or graph storage
    b64_image_uri = f"data:image/svg+xml;base64,{base64.b64encode(svg_text.encode('utf-8')).decode('utf-8')}"

    # 3. Compile Useful Engineering & Validation Practices
    # These properties act as the "validation passport" when verifying drug-target paths
    profile = {
        "success": True,
        "visualization_svg_b64": b64_image_uri,

        # Exact structural anchors to resolve duplicates in your Knowledge Graph
        "identity_anchors": {
            "canonical_smiles": Chem.MolToSmiles(mol, canonical=True),
            "inchi_key": Chem.MolToInchiKey(mol),
            "formula": rdMolDescriptors.CalcMolFormula(mol)
        },

        # Physico-chemical vectors used by weighting/scoring engines to predict behavior
        "physicochemical_properties": {
            "molecular_weight": Descriptors.MolWt(mol),
            "exact_mass": Descriptors.ExactMolWt(mol),
            "clogp": Descriptors.MolLogP(mol),  # Lipophilicity index
            "tpsa": rdMolDescriptors.CalcTPSA(mol),
            # Topological Polar Surface Area (crucial for Blood-Brain Barrier estimation)
            "heavy_atom_count": mol.GetNumHeavyAtoms()
        },

        # Binding/Docking structural readiness flags
        "pharmacophore_descriptors": {
            "h_bond_donors": rdMolDescriptors.CalcNumHBD(mol),  # Hydrogen Bond Donors
            "h_bond_acceptors": rdMolDescriptors.CalcNumHBA(mol),  # Hydrogen Bond Acceptors
            "rotatable_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol),  # Molecular flexibility metric
            "aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol)
        }
    }

    return profile


# --------------------------------------------------------------------------
# Execution Example (Using the Prazosin Molfile snippet from earlier)
# --------------------------------------------------------------------------
if __name__ == "__main__":
    sample_molfile = """
     RDKit          2D

 28 31  0  0  0  0  0  0  0  0999 V2000
    0.9375   -1.9792    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.9292   -2.6917    0.0000 N   0  0  0  0  0  0  0  0  0  0  0  0
   -0.3208   -2.6750    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.2875   -3.0417    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.3042   -1.6167    0.0000 N   0  0  0  0  0  0  0  0  0  0  0  0
   -0.3208   -1.9625    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.3917   -0.5917    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5542   -1.6417    0.0000 N   0  0  0  0  0  0  0  0  0  0  0  0
    2.7792   -0.9542    0.0000 N   0  0  0  0  0  0  0  0  0  0  0  0
   -0.9500   -3.0167    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    4.0125   -0.9292    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   -0.9250   -1.5917    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   -1.5833   -2.6542    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   -1.5708   -1.9417    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    4.2417   -1.5917    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    1.5417   -0.9500    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.1667   -2.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.1667   -0.5792    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.7792   -1.6375    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.4042    0.0875    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    4.5792   -0.5125    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    4.9417   -1.5917    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    5.1542   -0.9292    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.2667   -3.7542    0.0000 N   0  0  0  0  0  0  0  0  0  0  0  0
   -2.2000   -2.9917    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
   -2.1833   -1.5792    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
   -2.7958   -1.9125    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   -2.7958   -2.6542    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  2  1  2  0
  3  6  1  0
  4  2  1  0
  5  1  1  0
  6  5  2  0
  7  9  1  0
  8  1  1  0
  9 19  1  0
 10  3  1  0
 11  7  1  0
 12  6  1  0
 13 14  1  0
 14 12  2  0
 15 11  1  0
 16  8  1  0
 17  8  1  0
 18 16  1  0
 19 17  1  0
 20  7  2  0
 21 11  2  0
 22 15  1  0
 23 21  1  0
 24  4  1  0
 25 13  1  0
 26 14  1  0
 27 26  1  0
 28 25  1  0
  3  4  2  0
  9 18  1  0
 10 13  2  0
 22 23  2  0
M  END"""

    result = generate_biochem_molecular_profile(sample_molfile)
    if result["success"]:
        print(f"InChI Key derived: {result['identity_anchors']['inchi_key']}")
        print(f"Calculated TPSA: {result['physicochemical_properties']['tpsa']} Å²")
        print(f"Image string starts with: {result['visualization_svg_b64'][:45]}...")