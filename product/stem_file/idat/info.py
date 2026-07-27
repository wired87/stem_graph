"""

AddressA_ID (oder AddressB_ID)
Intensität (Mean)
Standardabweichung (SD)
Anzahl der Beads (NBeads)

"""


from __future__ import annotations

import math


def compute_variant_features(
    green_intensity: float,
    red_intensity: float,
    green_stddev: float,
    red_stddev: float,
    green_bead_count: int,
    red_bead_count: int,
    eps: float = 1e-8,
    intensity_scale: float = 10000.0,
) -> dict[str, float]:
    """
    Computes normalized features from Illumina IDAT measurements for
    genotype (variant) inference.

    This function does NOT perform genotype calling itself (AA / AB / BB).
    Instead, it converts the raw fluorescence measurements into a compact,
    normalized feature vector suitable for downstream clustering or machine
    learning models.

    The implementation follows the same principles used by Illumina's
    GenCall algorithm:

        • allele balance
        • total signal intensity
        • fluorescence angle
        • measurement confidence
        • signal quality

    Parameters
    ----------
    green_intensity
        Mean fluorescence intensity of the green channel.

    red_intensity
        Mean fluorescence intensity of the red channel.

    green_stddev
        Standard deviation of the green intensity.

    red_stddev
        Standard deviation of the red intensity.

    green_bead_count
        Number of beads contributing to the green measurement.

    red_bead_count
        Number of beads contributing to the red measurement.

    eps
        Numerical stability constant.

    intensity_scale
        Saturation parameter used when computing confidence.

    Returns
    -------
    dict

        {
            "allele_balance",
            "total_intensity",
            "contrast",
            "theta",
            "quality",
            "confidence",
            "variant_score"
        }

    Feature description
    -------------------

    allele_balance
        Fraction of green signal.

            G / (G + R)

    total_intensity
        Total fluorescence.

            G + R

    contrast
        Difference between both alleles.

            |G-R| / (G+R)

    theta
        Fluorescence angle used by Illumina.

            2/pi * atan(R/G)

    quality
        Confidence estimated from bead count and measurement variance.

    confidence
        Signal confidence using total intensity.

    variant_score
        Continuous score useful for downstream clustering.
    """

    ###########################################################
    # Basic signal quantities
    ###########################################################

    total_intensity = green_intensity + red_intensity + eps

    allele_balance = green_intensity / total_intensity

    contrast = abs(green_intensity - red_intensity) / total_intensity

    theta = (2.0 / math.pi) * math.atan(
        red_intensity / (green_intensity + eps)
    )

    ###########################################################
    # Measurement quality
    ###########################################################

    quality = (
        math.sqrt(
            max(green_bead_count, 1)
            * max(red_bead_count, 1)
        )
        /
        (
            1.0
            + green_stddev
            + red_stddev
        )
    )

    confidence = (
        quality
        * total_intensity
        /
        (total_intensity + intensity_scale)
    )

    variant_score = confidence * theta

    return {
        "allele_balance": allele_balance,
        "total_intensity": total_intensity,
        "contrast": contrast,
        "theta": theta,
        "quality": quality,
        "confidence": confidence,
        "variant_score": variant_score,
    }