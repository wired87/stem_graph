import math
import sys
from pathlib import Path
from typing import Optional

# CHAR: repo root on sys.path when this file is run as a script.
for _p in Path(__file__).resolve().parents:
    if (_p / "core").is_dir() and (_p / "embedder").is_dir():
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
        break

def set_interaction_scroes_drug_trgt(g):
    #
    molecules: list[tuple] = [
        (nid, attrs)
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    #
    for mol in molecules:
        trgts = g.get_neighbor_list_rel(
            node=mol[0],
            trgt_rel="target_of",
            just_ids=True,
        )

        # SET SCORES ALL EDGES
        for trgt in trgts:
            edge = g.get_edge(
                src=mol[0],
                trgt=trgt
            )
            eattrs = edge.get("attrs", edge) if isinstance(edge, dict) else {}

            # CALC SCORE EDGE AND
            g.update_edge(
                src=mol[0],
                trgt=trgt,
                attrs=dict(
                    score=calculate_drug_effect_score(
                        eattrs.get("activity_value"),
                        eattrs.get("activity_unit"),
                        eattrs.get("mechanism"),
                        eattrs.get("confidence"),
                    )
                )
            )


# MVP SCHEMATIC -> IMPROVE
def calculate_drug_effect_score(
    activity_value: float,
    activity_unit: str,
    mechanism: str,
    confidence: Optional[float] = 1.0,
) -> float:
    """
    Calculate a normalized drug-target perturbation score.

    Parameters
    ----------
    activity_value : float
        Experimental activity value (Ki, IC50, EC50, Kd, etc.)

    activity_unit : str
        Activity unit:
        M, mM, uM, nM, pM

    mechanism : str
        Drug mechanism:
        agonist, antagonist, inhibitor, blocker, activator,
        positive modulator, negative modulator,
        partial agonist, inverse agonist

    confidence : float, optional
        Confidence score [0-1].
        Can originate from ChEMBL confidence scores,
        assay quality metrics, manual curation, etc.

    Returns
    -------
    float
        Signed perturbation score.
        Positive = activation
        Negative = inhibition
    """

    unit_scale = {
        "M": 1.0,
        "mM": 1e-3,
        "uM": 1e-6,
        "µM": 1e-6,
        "nM": 1e-9,
        "pM": 1e-12,
    }

    scale = unit_scale.get(activity_unit)

    if scale is None:
        raise ValueError(
            f"Unsupported activity unit: {activity_unit}"
        )

    activity_molar = activity_value * scale

    # ------------------------------
    # Experimental values must be > 0
    # ------------------------------
    if activity_molar <= 0:
        raise ValueError(
            f"Activity value must be > 0. Got {activity_value}"
        )

    # ------------------------------
    # Convert activity into
    # standard pActivity scale
    #
    # Example:
    # 1 nM  -> 9
    # 10 nM -> 8
    # 1 µM  -> 6
    # ------------------------------
    p_activity = -math.log10(activity_molar)

    # ------------------------------
    # Mechanism directionality
    # ------------------------------
    mechanism_signs = {
        "agonist": 1.0,
        "activator": 1.0,

        "positive modulator": 0.75,
        "positive allosteric modulator": 0.75,

        "partial agonist": 0.5,

        "neutral": 0.0,

        "negative modulator": -0.75,
        "negative allosteric modulator": -0.75,

        "antagonist": -1.0,
        "blocker": -1.0,
        "inhibitor": -1.0,

        "inverse agonist": -1.25,
    }

    mechanism_sign = mechanism_signs.get(
        mechanism.lower().strip(),
        0.0,
    )

    # ------------------------------
    # Clamp confidence to [0,1]
    # ------------------------------
    confidence = max(
        0.0,
        min(
            1.0,
            float(confidence),
        ),
    )

    # ------------------------------
    # Final perturbation score
    #
    # Positive:
    #   target activation
    #
    # Negative:
    #   target inhibition
    #
    # Magnitude:
    #   perturbation strength
    # ------------------------------
    score = (
        p_activity
        * mechanism_sign
        * confidence
    )

    return score


if __name__ == "__main__":
    # Prompt: standalone query_pipe check — hardcoded GUtils fixture for set_interaction_scroes_drug_trgt.
    import sys
    from pathlib import Path
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from firegraph.graph.local_graph_utils import GUtils

    # CHAR: MOLECULE→TARGET target_of edge with ChEMBL-like activity attrs on edge payload.
    g = GUtils()
    g.add_node(attrs=dict(id="CHEMBL25", type="MOLECULE", name="Aspirin"))
    g.add_node(attrs=dict(id="CHEMBL240", type="TARGET", pref_name="COX-1"))
    g.add_edge(
        "CHEMBL25",
        "CHEMBL240",
        attrs=dict(
            rel="target_of",
            src_layer="MOLECULE",
            trgt_layer="TARGET",
            activity_value=10.0,
            activity_unit="nM",
            mechanism="inhibitor",
            confidence=0.85,
        ),
    )
    # CHAR: pure scorer path — no graph required.
    raw = calculate_drug_effect_score(10.0, "nM", "inhibitor", confidence=0.85)
    assert raw < 0, "inhibitor mechanism should yield negative signed score"
    print(f"[__main__] calculate_drug_effect_score OK  score={raw:.4f}")
    set_interaction_scroes_drug_trgt(g)
    scored = [
        a.get("score")
        for _, _, a in g.G.edges(data=True)
        if a.get("rel") == "target_of"
    ]
    assert any(s is not None for s in scored), "expected score on target_of edge"
    print(f"[__main__] set_interaction_scroes_drug_trgt OK  edge_scores={scored}")
