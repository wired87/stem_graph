async def cam_for_term(fetcher, go_terms, g):
    """get cam for specific term"""
    # start marker
    print(f"[cam_for_term] start (input={len(go_terms)})")

    missing_terms = set()

    # cache layer: restore cached terms (+ their edges) so they fall straight
    # into _CAM_SEEN and get filtered out before any HTTP roundtrip
    _CAM_SEEN.update(g.cache_load(go_terms))

    # dedup: only ask the API for terms we have not already pulled cams for
    fresh_terms = [t for t in go_terms if t not in _CAM_SEEN]
    # remember them up front so a concurrent caller does not re-enqueue them
    _CAM_SEEN.update(fresh_terms)
    # observable cost
    print(f"[cam_for_term] fresh={len(fresh_terms)} cached_skip={len(go_terms) - len(fresh_terms)}")

    # nothing left to do -> bail before any HTTP
    if not fresh_terms:
        print("[cam_for_term] nothing to fetch -> done")
        return

    #
    cam_pw_tasks = [fetcher.get_cam_pathway(item) for item in fresh_terms]
    cam_pw_results = await asyncio.gather(*cam_pw_tasks)

    #
    for k, (cam_batch, term) in enumerate(zip(cam_pw_results, fresh_terms)):
        cam_detailed_results = await fetcher.get_cam_detailed([_item["gocam"].split("/")[-1] for _item in cam_batch])

        for k, cam_details in enumerate(cam_detailed_results):
            print("cam_details", len(cam_details))

            # GOCAM -> G
            g.add_node(
                dict(
                    id=cam_details["gocam"].split("/")[-1],
                    type="GOCAM",
                    text=f"{cam_details['gonames']} {cam_details['definitions']}",
                    embed_key="text",
                )
            )

            # CENTER TERM -> CAM
            g.add_edge(
                src=term,
                trgt=cam_details["gocam"],
                attrs=dict(
                    rel="gocam",
                    src_layer="GO_TERM",
                    trgt_layer="GOCAM",
                )
            )
            cams_terms = [
                *[_i.split("/")[-1] for _i in cam_details["goclasses"]],
                *[_i.split("/")[-1] for _i in cam_details["goids"]]
            ]

            # CAMS TERMS -> G-> CAM
            for cams_term in cams_terms:

                g.add_node(
                    dict(
                        id=cams_term.split("/")[-1],
                        type="GO_TERM",
                        text="",
                        embed_key="text",
                    )
                )

                g.add_edge(
                    src=cam_details["gocam"],
                    trgt=term,
                    attrs=dict(
                        rel="gocam",
                        src_layer="GOCAM",
                        trgt_layer="GO_TERM",
                    )
                )

    # logical bridge: from CAM expansion into term-detail fetch
    print(f"[cam_for_term] cams expanded, queueing term_details for {len(missing_terms)} new terms")
    await term_details(fetcher, missing_terms, g)
    # end marker
    print("[cam_for_term] done")
    return