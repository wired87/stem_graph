from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class DrugActivity:

    activity_id: int

    molecule_chembl_id: str
    parent_molecule_chembl_id: str

    target_chembl_id: str
    target_name: str
    target_organism: str
    target_tax_id: int

    assay_chembl_id: str
    assay_type: str
    assay_description: str

    activity_type: str          # IC50, EC50, Ki, Kd ...
    relation: str              # =, >, <, >= ...

    value: Optional[float]
    units: Optional[str]

    standard_type: Optional[str]
    standard_relation: Optional[str]
    standard_value: Optional[float]
    standard_units: Optional[str]

    pchembl_value: Optional[float]

    document_chembl_id: str
    document_journal: Optional[str]
    document_year: Optional[int]

    standard_flag: bool

    canonical_smiles: Optional[str]