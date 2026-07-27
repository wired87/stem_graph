
async def term_details(fetcher, go_terms, g):
    print(f"[term_details] start (input={len(go_terms)})")

    #
    term_tasks = [fetcher.get_term_details(item) for item in go_terms]
    term_results = await asyncio.gather(*term_tasks)

    for item in term_results:
        g.add_node(
            dict(
                id=item["goid"].split("/")[-1],
                type="GO_TERM",
                text=f"{item['definition']}, {item['label']} {item.get('name')}",
                embed_key="text",
            )
        )
    # end marker
    print(f"[term_details] done (added={len(term_results)})")

