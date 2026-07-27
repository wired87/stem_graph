import asyncio



async def go_term_hierarchy(fetcher, g, term_ids):
    print("Get term hierarchy...")

    missing_nodes = set()

    hierarchy_tasks = [
        fetcher.get_term_hierarchy(term_id)
        for term_id in term_ids
    ]
    hierarchy_results = await asyncio.gather(*hierarchy_tasks)

    print(f"[hierarchy_process] hierarchies fetched ({len(hierarchy_results)} stacks)")

    for center_id, children in zip(term_ids, hierarchy_results):

        if not children:
            continue

        for child in children:
            child_id = child["GO"].split("/")[-1]

            if not g.get_node(child_id):
                g.add_node(
                    dict(
                        id=child_id,
                        type="GO_TERM",
                        embed_key="text",
                        **child,
                    )
                )
                missing_nodes.add(child_id)
            else:
                g.update_node(
                    dict(
                        id=child_id,
                        embed_key="text",
                        **child,
                    )
                )

            g.add_edge(
                src=center_id,
                trgt=child_id,
                attrs=dict(
                    rel="child_of",
                    src_layer="GO_TERM",
                    trgt_layer="GO_TERM",
                ),
            )

    print(f"GO hierarchy added ({len(missing_nodes)} new nodes)... done")



async def hierarchy_process(go_terms, g):
    "get goterm hierarch for specific term"
    # start marker
    print(f"[hierarchy_process] start (input={len(go_terms)})")
    _HIERARCHY_SEEN: set[str] = set()

    _HIERARCHY_SEEN.update(g.cache_load(go_terms))

    term_ids = [t for t in go_terms if t not in _HIERARCHY_SEEN]
    # reserve the ids before awaiting so concurrent callers do not duplicate work
    _HIERARCHY_SEEN.update(term_ids)
    # observable cost
    print(f"[hierarchy_process] fresh={len(term_ids)} cached_skip={len(go_terms) - len(term_ids)}")

    # nothing left to expand -> short-circuit
    if not term_ids:
        print("[hierarchy_process] done (no new terms)")
        return

    print("[hierarchy_process] done")