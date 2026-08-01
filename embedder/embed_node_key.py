def _node_embed_text(nid: str, attrs: dict) -> str:
    embed_key = attrs.get("embed_key", "name")
    if embed_key == "id":
        return str(nid)
    value = attrs.get(embed_key)
    if value:
        return str(value)
    return str(attrs.get("name") or attrs.get("definition") or nid)
