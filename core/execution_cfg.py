"""
Hardcoded execution configuration for all workflow categories.

EXECUTION_CFG maps each category slug to a specs dict containing
API endpoints, routing keywords, retrieval defaults, scoring params,
and output artifact naming — everything the master pipeline needs
to resolve a category at runtime without scattered constants.
"""
from __future__ import annotations

# ── AMINO ACID (UniProt) ────────────────────────────────────────────
# Mirrors the current master_workflow.py implementation.
# UniProt REST is fully open — no API key required.
# Rate-limit of 5 req/s matches their fair-use policy.
_AMINO_ACID_SPECS: dict = {
    "display_name": "Amino Acid",
    "api": {
        "provider": "uniprot",
        "base_url": "https://rest.uniprot.org",
        "search_url": "https://rest.uniprot.org/uniprotkb/search",
        "fields_url": "https://rest.uniprot.org/configure/uniprotkb/result-fields",
        "format": "json",
        "auth_header": None,
    },
    "routing": {
        "workflow_hint": "acid",
        "keywords": {
            "amino", "acid", "acids", "residue", "residues", "motif",
            "composition",
        },
        "router_description": (
            "amino-acid structure, amino-acid composition, "
            "residue frequencies, or residue-level design"
        ),
    },
    "retrieval": {
        "organism_filter": "organism_id:9606",
        "field_prefix": "ft_",
        "max_per_category": 25,
        "rate_limit_per_second": 5,
        "timeout_seconds": 30,
        # CORE FIELDS always requested alongside scored feature fields
        "core_field_labels": [
            "Entry", "Entry Name", "Gene Names", "Protein names",
            "Sequence", "Function [CC]", "Catalytic activity",
            "Subcellular location [CC]",
        ],
    },
    "scoring": {
        "selection_threshold": 0.7,
        "fallback_top_n": 5,
        "model_weight": 0.5,
        "embedding_weight": 0.5,
        "embedding_dimension": 26,
    },
    "output": {
        "artifact_prefix": "acid_sequence",
        "fasta_header_template": (
            ">{accession} | {name} | category={category} | "
            "harmony={harmony:.3f} | fragments={fragments}"
        ),
        "composite_header": "TRANSFORMED_ACID_STRUCTURE",
        "sidecar_extra_keys": [
            "amino_acid_frequency", "structure_plan", "assembly_notes",
        ],
    },
}


# ── PROTEIN STRUCTURE (RCSB PDB) ───────────────────────────────────
# RCSB PDB search uses a JSON POST body (not query-string params).
# Data endpoints return per-entry or per-entity JSON.
# No auth required; fair-use rate limit ~5 req/s.
_PROTEIN_STRUCTURE_SPECS: dict = {
    "display_name": "Protein Structure",
    "api": {
        "provider": "rcsb_pdb",
        "base_url": "https://data.rcsb.org",
        "search_url": "https://search.rcsb.org/rcsbsearch/v2/query",
        # {pdb_id} placeholder resolved at runtime
        "entry_url": "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}",
        "polymer_entity_url": (
            "https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/1"
        ),
        "format": "json",
        "auth_header": None,
        # RCSB search expects HTTP POST with a JSON body
        "search_method": "POST",
    },
    "routing": {
        "workflow_hint": "protein_structure",
        "keywords": {
            "protein", "structure", "pdb", "fold", "domain", "3d",
            "crystal", "cryo", "conformation", "tertiary",
        },
        "router_description": (
            "protein 3D structure, PDB entries, folds, domains, "
            "or crystallographic / cryo-EM conformations"
        ),
    },
    "retrieval": {
        "organism_filter": "Homo sapiens",
        # RCSB search body template — text_value injected at runtime
        "search_body_template": {
            "query": {
                "type": "terminal",
                "service": "full_text",
                "parameters": {"value": "{text_value}"},
            },
            "return_type": "entry",
            "request_options": {
                "results_content_type": ["experimental"],
                "paginate": {"start": 0, "rows": 25},
            },
        },
        "max_per_category": 25,
        "rate_limit_per_second": 5,
        "timeout_seconds": 30,
    },
    "scoring": {
        "selection_threshold": 0.7,
        "fallback_top_n": 5,
        "model_weight": 0.5,
        "embedding_weight": 0.5,
        "embedding_dimension": 26,
    },
    "output": {
        "artifact_prefix": "protein_structure",
        "fasta_header_template": (
            ">{pdb_id} | {name} | method={method} | "
            "resolution={resolution} | chains={chain_count}"
        ),
        "composite_header": "STRUCTURAL_COMPOSITE",
        "sidecar_extra_keys": [
            "resolution", "experimental_method", "chain_sequences",
        ],
    },
}


# ── ATOM (PubChem Elements) ─────────────────────────────────────────
# PubChem PUG REST exposes element data under /element/name/.
# Periodic-table properties come back as a flat JSON object.
# No auth required; generous rate limit (~5 req/s recommended).
_ATOM_SPECS: dict = {
    "display_name": "Atom",
    "api": {
        "provider": "pubchem",
        "base_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug",
        # {element_name} placeholder resolved at runtime
        "element_url": (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
            "element/name/{element_name}/JSON"
        ),
        "periodic_table_url": (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
            "periodictable/JSON"
        ),
        "format": "json",
        "auth_header": None,
    },
    "routing": {
        "workflow_hint": "atom",
        "keywords": {
            "atom", "element", "atomic", "electron", "proton", "neutron",
            "orbital", "isotope", "periodic", "valence",
        },
        "router_description": (
            "atomic elements, periodic table properties, "
            "electron configurations, or isotope data"
        ),
    },
    "retrieval": {
        "organism_filter": None,
        "max_per_category": 50,
        "rate_limit_per_second": 5,
        "timeout_seconds": 20,
        # PROPERTIES requested from PubChem element endpoint
        "default_properties": [
            "AtomicNumber", "Symbol", "Name", "AtomicMass",
            "ElectronConfiguration", "Electronegativity",
            "AtomicRadius", "IonizationEnergy", "GroupBlock",
        ],
    },
    "scoring": {
        "selection_threshold": 0.6,
        "fallback_top_n": 10,
        "model_weight": 0.4,
        "embedding_weight": 0.6,
        "embedding_dimension": 26,
    },
    "output": {
        "artifact_prefix": "atom_profile",
        "fasta_header_template": (
            ">{symbol} | {name} | Z={atomic_number} | "
            "mass={atomic_mass} | group={group_block}"
        ),
        "composite_header": "ATOM_COMPOSITE",
        "sidecar_extra_keys": [
            "electron_configuration", "electronegativity",
            "ionization_energy",
        ],
    },
}


# ── CHEMICAL (PubChem Compounds) ────────────────────────────────────
# PubChem PUG REST compound search by name returns CID(s);
# property endpoint fetches bulk physicochemical data.
# No auth; ~5 req/s recommended.
_CHEMICAL_SPECS: dict = {
    "display_name": "Chemical",
    "api": {
        "provider": "pubchem",
        "base_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug",
        # {compound_name} placeholder resolved at runtime
        "compound_search_url": (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
            "compound/name/{compound_name}/JSON"
        ),
        # {cid} placeholder resolved at runtime
        "compound_property_url": (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
            "compound/cid/{cid}/property/"
            "MolecularFormula,MolecularWeight,CanonicalSMILES,"
            "IsomericSMILES,InChI,InChIKey,IUPACName,XLogP,"
            "ExactMass,TPSA,HBondDonorCount,HBondAcceptorCount,"
            "RotatableBondCount/JSON"
        ),
        # Substructure / similarity search (optional advanced use)
        "compound_similarity_url": (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
            "compound/fastsimilarity_2d/smiles/{smiles}/cids/JSON"
        ),
        "format": "json",
        "auth_header": None,
    },
    "routing": {
        "workflow_hint": "chemical",
        "keywords": {
            "chemical", "compound", "molecule", "drug", "ligand",
            "smiles", "inchi", "formula", "reagent", "substance",
        },
        "router_description": (
            "chemical compounds, molecular properties, drug-like "
            "molecules, SMILES/InChI lookups, or physicochemical profiles"
        ),
    },
    "retrieval": {
        "organism_filter": None,
        "max_per_category": 25,
        "rate_limit_per_second": 5,
        "timeout_seconds": 30,
        # PROPERTIES pulled from the compound property endpoint
        "default_properties": [
            "MolecularFormula", "MolecularWeight", "CanonicalSMILES",
            "IsomericSMILES", "InChI", "InChIKey", "IUPACName",
            "XLogP", "ExactMass", "TPSA",
            "HBondDonorCount", "HBondAcceptorCount",
            "RotatableBondCount",
        ],
    },
    "scoring": {
        "selection_threshold": 0.7,
        "fallback_top_n": 5,
        "model_weight": 0.5,
        "embedding_weight": 0.5,
        "embedding_dimension": 26,
    },
    "output": {
        "artifact_prefix": "chemical_profile",
        "fasta_header_template": (
            ">{cid} | {iupac_name} | formula={formula} | "
            "mw={molecular_weight} | smiles={smiles}"
        ),
        "composite_header": "CHEMICAL_COMPOSITE",
        "sidecar_extra_keys": [
            "smiles", "inchi", "xlogp", "tpsa",
            "hbond_donors", "hbond_acceptors",
        ],
    },
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCAN PIPELINE — modality-indexed term lists (no inline tables in enrich modules)
# Phase 21: ranked anatomy query strings → OLS4 UBERON search (intensity tier → term).
SCAN_ANATOMY_TERM_TIERS_BY_MODALITY: dict[str, list[str]] = {
    "MRI": ["white matter", "gray matter", "cerebrospinal fluid"],
    "MRI_T1": ["white matter", "gray matter", "cerebrospinal fluid"],
    "MRI_T2": ["gray matter", "white matter", "cerebrospinal fluid"],
    "CT": ["soft tissue", "bone", "air"],
    "PET": ["metabolically active tissue", "soft tissue", "background"],
    "ULTRASOUND": ["soft tissue", "fluid", "bone"],
    "FMRI": ["cortex", "subcortical structure", "white matter"],
}

# Phase 22c: modality → HPO search term options (dominant feature dimension indexes into list).
SCAN_PATHOLOGY_HPO_TERMS_BY_MODALITY: dict[str, list[str]] = {
    "MRI": ["abnormal signal intensity", "brain lesion", "atrophy"],
    "MRI_T1": ["white matter abnormality", "brain atrophy", "hypointensity"],
    "MRI_T2": ["hyperintensity", "edema", "demyelination"],
    "CT": ["calcification", "hyperdensity", "mass lesion"],
    "PET": ["hypermetabolism", "hypometabolism", "abnormal uptake"],
    "ULTRASOUND": ["echogenic lesion", "cyst", "mass"],
    "FMRI": ["abnormal activation", "reduced connectivity", "cortical dysfunction"],
}
