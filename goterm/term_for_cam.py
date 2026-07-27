
async def terms_for_fetched_cams(fetcher, go_terms, g):
    """get cam for specific term"""
    # start marker
    print(f"[terms_for_fetched_cams] start (input={len(go_terms)})")

    # cache layer: known terms (+ edges) restored into G so the dedup below drops them
    _CAM_SEEN.update(g.cache_load(go_terms))

    # dedup: never request cams for the same term twice in one process
    fresh_terms = [t for t in go_terms if t not in _CAM_SEEN]
    _CAM_SEEN.update(fresh_terms)
    print(f"[terms_for_fetched_cams] fresh={len(fresh_terms)} cached_skip={len(go_terms) - len(fresh_terms)}")

    # bail before any HTTP when there is nothing to do
    if not fresh_terms:
        print("[terms_for_fetched_cams] done (no new terms)")
        return

    cam_pw_tasks = [fetcher.get_cam_pathway(item) for item in fresh_terms]
    cam_pw_results = await asyncio.gather(*cam_pw_tasks)
    #
    for cam_batch, term in zip(cam_pw_results, fresh_terms):
        for item in cam_batch:
            g.add_node(
                dict(
                    id=item["gocam"].split("/")[-1],
                    type="GOCAM",
                    text=f"{item['gonames']} {item['definitions']}",
                    embed_key="text",
                )
            )

            # TERM -> CAM
            g.add_edge(
                src=term,
                trgt=item["gocam"],
                attrs=dict(
                    rel="gocam",
                    src_layer="GO_TERM",
                    trgt_layer="GOCAM",
                )
            )

    # end marker
    print("[terms_for_fetched_cams] done")

