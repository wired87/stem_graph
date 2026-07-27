"""Signal scoring and genotype calling for paired Illumina IDAT channels."""

from __future__ import annotations

import math
from typing import Any


def calculate_channel_score(mean_intensity, std_dev, gamma: float = 0.0005) -> float:
    """Return a bounded signal-quality score for one color channel."""
    mean_intensity = float(mean_intensity or 0)
    std_dev = float(std_dev or 0)
    epsilon = 1e-5
    intensity_factor = 1.0 - math.exp(-gamma * mean_intensity)
    snr_factor = (mean_intensity**2) / (
        mean_intensity**2 + std_dev**2 + epsilon
    )
    return intensity_factor * snr_factor


def get_genotype(score_red, score_green, aa, ab, bb) -> tuple[int, str]:
    """Return the closest EGT cluster and its AA/AB/BB label."""
    if score_red == 0 and score_green == 0:
        return -1, "NC"

    theta = math.atan2(score_green, score_red) / (math.pi / 2)
    cluster_centers = [float(aa), float(ab), float(bb)]
    labels = ["AA", "AB", "BB"]
    distances = [abs(theta - center) for center in cluster_centers]
    index = distances.index(min(distances))
    return index, labels[index]


def calc_score_single(item: dict) -> float:
    """Calculate one channel score from a normalized intensity row."""
    mean_intensity = item.get("mean_intensity", item.get("mean_intensities", 0))
    std_dev = item.get("std_dev", item.get("std_devs", 0))
    return calculate_channel_score(mean_intensity, std_dev)


def _cluster_theta(cluster_stats: Any) -> float:
    for attr in ("theta_mean", "mean_theta", "theta", "mean"):
        if hasattr(cluster_stats, attr):
            return float(getattr(cluster_stats, attr))
    if isinstance(cluster_stats, (int, float)):
        return float(cluster_stats)
    raise TypeError(
        f"No theta center available on {type(cluster_stats).__name__}"
    )


def _get_idat_item(batch: dict | list[dict], index: int) -> dict | None:
    """Return one row from column- or row-oriented IDAT data."""
    if index < 0:
        return None
    if isinstance(batch, dict):
        means = batch.get("mean_intensities", batch.get("mean_intensity", []))
        stds = batch.get("std_devs", batch.get("std_dev", []))
        if index >= len(means):
            return None
        return {
            "mean_intensity": means[index],
            "std_dev": stds[index] if index < len(stds) else 0,
        }
    if index >= len(batch):
        return None
    return batch[index]


def _get_probe_score(batch: dict | list[dict], index: int) -> float:
    item = _get_idat_item(batch, index)
    return calc_score_single(item) if item is not None else 0.0


def filter_strongest_signal(
    gbatch: dict | list[dict],
    rbatch: dict | list[dict],
    egt_content: list,
    aligned: list[tuple[int, int, int]],
    manifest,
) -> list[dict]:
    """
    Call one genotype per aligned manifest locus.

    ``aligned`` contains ``(red_index, green_index, egt_index)`` in manifest
    order. Returned rows retain ``manifest_idx`` so every graph node can be
    traced back to its original input columns.
    """
    results: list[dict] = []
    manifest_names = list(manifest.names)
    manifest_snps = list(manifest.snps)
    manifest_chroms = list(manifest.chroms)
    manifest_map_infos = list(manifest.map_infos)
    genome_builds = getattr(
        manifest, "genome_builds", [None] * len(manifest_names)
    )

    for manifest_idx, (red_idx, green_idx, egt_idx) in enumerate(aligned):
        if egt_idx < 0:
            continue

        red_score = _get_probe_score(rbatch, red_idx)
        green_score = _get_probe_score(gbatch, green_idx)
        egt_entry = egt_content[egt_idx]
        genotype_idx, genotype_label = get_genotype(
            score_red=red_score,
            score_green=green_score,
            aa=_cluster_theta(egt_entry.aa_cluster_stats),
            ab=_cluster_theta(egt_entry.ab_cluster_stats),
            bb=_cluster_theta(egt_entry.bb_cluster_stats),
        )
        if genotype_idx < 0:
            continue

        snp = str(manifest_snps[manifest_idx]).strip()
        alleles = snp.strip("[]").split("/")
        if len(alleles) != 2:
            continue
        allele_a, allele_b = alleles
        converted_genotype = {
            "AA": f"{allele_a}/{allele_a}",
            "AB": f"{allele_a}/{allele_b}",
            "BB": f"{allele_b}/{allele_b}",
        }[genotype_label]

        results.append(
            {
                "A": allele_a,
                "B": allele_b,
                "genotype": converted_genotype,
                "genotype_class": genotype_label,
                "score": math.hypot(red_score, green_score),
                "red_score": red_score,
                "green_score": green_score,
                "chr": str(manifest_chroms[manifest_idx]),
                "MapInfo": str(manifest_map_infos[manifest_idx]),
                "GenomeBuild": genome_builds[manifest_idx],
                "egt_idx": egt_idx,
                "red_idx": red_idx,
                "green_idx": green_idx,
                "manifest_idx": manifest_idx,
                "name": str(manifest_names[manifest_idx]),
            }
        )
    return results
