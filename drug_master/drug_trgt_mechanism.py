from dataclasses import dataclass, field
from typing import Optional, List


@dataclass(slots=True)
class MechanismReference:
    ref_id: str
    ref_type: str
    ref_url: str


@dataclass(slots=True)
class Mechanism:
    action_type: str

    binding_site_comment: Optional[str]
    direct_interaction: bool
    disease_efficacy: bool

    max_phase: int

    mec_id: int

    mechanism_comment: Optional[str]
    mechanism_of_action: str


    molecular_mechanism: bool

    molecule_chembl_id: str
    parent_molecule_chembl_id: str

    record_id: int

    selectivity_comment: Optional[str]

    site_id: Optional[int]

    target_chembl_id: str

    variant_sequence: Optional[str]


@dataclass(slots=True)
class MechanismResponse:
    mechanisms: List[Mechanism] = field(default_factory=list)