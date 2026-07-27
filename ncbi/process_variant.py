from __future__ import annotations


def extract_variant_annotation(data: dict) -> dict:
    """
    Extract the most relevant annotation fields from an NCBI dbSNP Variant API response.
    """
    result = {
        # -------------------------
        # Variant
        # -------------------------
        "rsid": None,
        "created": None,
        "updated": None,

        # -------------------------
        # Genome
        # -------------------------
        "assembly": None,
        "chromosome": None,
        "position": None,
        "reference": None,
        "alternate": None,
        "variant_type": None,
        "hgvs_genomic": None,

        # -------------------------
        # Transcript
        # -------------------------
        "transcripts": [],

        # -------------------------
        # Protein
        # -------------------------
        "proteins": [],

        # -------------------------
        # Population frequencies
        # -------------------------
        "frequencies": [],

        # -------------------------
        # ClinVar
        # -------------------------
        "clinvar": [],

        # -------------------------
        # Metadata
        # -------------------------
        "citations": data.get("citations", []),
    }

    result["rsid"] = f'rs{data["refsnp_id"]}'
    result["created"] = data.get("create_date")
    result["updated"] = data.get("last_update_date")

    #########################################################
    # Placements
    #########################################################

    placements = (
        data.get("primary_snapshot_data", {})
        .get("placements_with_allele", [])
    )

    for placement in placements:

        if not placement.get("is_ptlp"):
            continue

        assembly = placement["placement_annot"]["seq_id_traits_by_assembly"][0]

        result["assembly"] = assembly["assembly_name"]

        seq = placement["seq_id"]

        if seq.startswith("NC_000"):
            result["chromosome"] = str(int(seq.split("_")[1].split(".")[0]))

        alleles = placement.get("alleles", [])

        if len(alleles) >= 2:

            ref = alleles[0]
            alt = alleles[1]

            ref_spdi = ref["allele"]["spdi"]
            alt_spdi = alt["allele"]["spdi"]

            result["position"] = ref_spdi["position"] + 1
            result["reference"] = ref_spdi["deleted_sequence"]
            result["alternate"] = alt_spdi["inserted_sequence"]

            result["hgvs_genomic"] = alt.get("hgvs")

            d = ref_spdi["deleted_sequence"]
            i = alt_spdi["inserted_sequence"]

            if len(d) == len(i) == 1:
                result["variant_type"] = "SNV"
            elif len(d) > len(i):
                result["variant_type"] = "Deletion"
            elif len(d) < len(i):
                result["variant_type"] = "Insertion"
            else:
                result["variant_type"] = "Indel"

        break

    #########################################################
    # Transcript / Protein HGVS
    #########################################################

    for placement in placements:

        seq = placement["seq_id"]

        if seq.startswith("NM_"):

            for allele in placement["alleles"]:

                hgvs = allele.get("hgvs")

                if hgvs and "=" not in hgvs:

                    result["transcripts"].append(
                        {
                            "transcript": seq,
                            "hgvs": hgvs,
                        }
                    )

        elif seq.startswith("NP_"):

            for allele in placement["alleles"]:

                hgvs = allele.get("hgvs")

                if hgvs and "=" not in hgvs:

                    result["proteins"].append(
                        {
                            "protein": seq,
                            "hgvs": hgvs,
                        }
                    )

    annotations = (
        data.get("primary_snapshot_data", {})
        .get("allele_annotations", [])
    )

    for ann in annotations:

        for freq in ann.get("frequency", []):

            total = freq.get("total_count", 0)
            allele = freq.get("allele_count", 0)

            result["frequencies"].append(
                {
                    "study": freq.get("study_name"),
                    "allele_count": allele,
                    "total_count": total,
                    "frequency": allele / total if total else None,
                }
            )

    #########################################################
    # ClinVar IDs
    #########################################################

    for obs in data.get("present_obs_movements", []):

        for comp in obs.get("component_ids", []):

            if comp["type"] == "clinvar":

                result["clinvar"].append(comp["value"])

    result["clinvar"] = sorted(set(result["clinvar"]))
    print("result", result)
    return result