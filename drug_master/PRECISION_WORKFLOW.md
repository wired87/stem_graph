# Precision drug graph workflow

## Purpose

Rank molecular interventions across several protein targets and pathway
variants. The output is a graph of evidence and **dimensionless research
exposure factors**. It is not a prescription, clinical dose, or treatment
recommendation.

## Canonical package

`drug_master` is the only drug package. Historical `drug.*` imports have been
migrated to `drug_master.*`.

## Evidence input contract

`build_precision_drug_graph` receives already-fetched, versioned evidence:

- `uniprot_accessions: list[str]`
- `target_records`: ChEMBL target rows grouped by UniProt accession
- `pathway_rows`: directed OmniPath-like interactions grouped by seed protein
- `candidates_by_target`: ChEMBL molecule/activity/mechanism rows
- `vep_annotations`: VEP consequence and phenotype/disease fields
- `sex`: optional analysis stratum; never converted directly into a dose

The API layer should record source release, assembly, fetch timestamp and raw
identifiers before calling the deterministic graph core.

## Graph contract

- `PROTEIN.influence`: fixed vector of length `len(target_ids)`
- `TARGET.target_index`: stable vector index
- `PROTEIN -> TARGET`: `target_component_of`, `dims=0`
- `PROTEIN -> PROTEIN`: `interacts_with`, `dims=1..10`
- `MOLECULE -> TARGET`: `target_of`, `dims=0`, signed activity `score`
- `PRECISION_DRUG_PLAN`: research result and safety warning

Each target has at most one selected `MOLECULE` neighbour. The same protein can
participate in several pathways; each target/drug influence remains isolated in
its stable vector slot.

## Stages

1. Normalize and de-duplicate UniProt accessions.
2. Add proteins and ChEMBL targets with stable indices.
3. Add directed pathway interactions and derive depth up to ten dimensions.
4. Interpret VEP conservatively:
   - a predicted consequence alone is not disease causality;
   - harmful status requires phenotype/disease evidence;
   - gain/loss direction is retained separately.
5. Score ChEMBL candidates using signed pActivity, confidence, selectivity and
   direction compatibility.
6. Keep no more than one selected molecule per target.
7. Propagate the direct target score through pathway edges with sign and decay.
8. Store every drug/target influence in the appropriate protein vector slot.
9. Rank variant-to-target paths by depth and write normalized stabilization
   weights to the corresponding edges.
10. Search dimensionless exposure factors that minimize aggregate harmful
    variant residuals.
11. Write the plan and all intermediate evidence back into the input graph.

## Clinical and research limits

- VEP predicts molecular consequences and can report phenotype associations;
  it does not prove that a variant causes the patient's disease.
- ChEMBL activity values come from heterogeneous assays and are not human dose
  equivalents.
- Pathway propagation is a model, not a PK/PD simulation.
- Sex is stored as a stratum only. A sex-specific factor requires
  drug-specific, indication-specific PK/PD evidence.
- Actual quantities require formulation, route, indication, age, body size,
  renal/hepatic function, comedication, therapeutic window and clinical review.
- DDI, contraindication and adverse-event checks remain mandatory before any
  translational use.

Official evidence interfaces:

- ChEMBL API: https://www.ebi.ac.uk/chembl/api/data/docs
- Ensembl VEP: https://www.ensembl.org/info/docs/tools/vep/
- UniProt REST API: https://www.uniprot.org/help/api_queries
- OmniPath: https://omnipathdb.org/
