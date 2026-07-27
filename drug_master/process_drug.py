def process_drug_item(g, drug_record):
    properties = drug_record.get("molecule_properties") or {}
    alogp = properties.get("alogp")

    try:
        alogp_val = float(alogp) if alogp is not None else None
    except Exception as e:
        print("Err include_drugs_for_channels", e)
        alogp_val = None

    # Calculate filters based on structural parameters
    able_pass_bbb = alogp_val < 5 if alogp_val is not None else False
    sweet_spot_algo = alogp_val == 1.78 if alogp_val is not None else False

    # Extract ATC classification codes safely
    atc_list = drug_record.get("atc_classification")
    atc_code = atc_list[0].get("code", "N/A") if atc_list else "N/A"

    drug_id = drug_record.get("pref_name") or drug_record.get("molecule_chembl_id")

    # CHAR: DrugBank ids from ChEMBL cross_references for DDI lookup
    drugbank_ids: list[str] = []
    for xref in drug_record.get("cross_references") or drug_record.get("molecule_cross_references") or []:
        if not isinstance(xref, dict):
            continue
        src = str(xref.get("xref_src") or xref.get("xref_name") or "").lower()
        if "drugbank" in src:
            xid = xref.get("xref_id") or xref.get("xref")
            if xid:
                drugbank_ids.append(str(xid))

    g.add_node(
        dict(
            **{
                k:v
                for k,v in drug_record.items()
                if k not in ["id"]
            },
            **{
                "atc_code": atc_code,
                "able_pass_bbb": able_pass_bbb,
                "sweet_spot_algo": sweet_spot_algo,
                "drugbank_ids": sorted(set(drugbank_ids)),
            },
            type="MOLECULE",
            id=drug_id
        )
    )

