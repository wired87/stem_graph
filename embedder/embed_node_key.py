def _node_embed_text(nid: str, attrs: dict) -> str:
    """Best available text for embedding / display."""
    embed_key = attrs.get("embed_key", "name")
    if embed_key == "id":
        return str(nid)
    val = attrs.get(embed_key)
    if val:
        return str(val)
    return str(attrs.get("name") or attrs.get("definition") or nid)
