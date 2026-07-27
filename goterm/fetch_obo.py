import requests
from core.app_utils import DB
from embedder import embed_batch

GO_OBO_URL = "https://current.geneontology.org/ontology/go-basic.obo"

def fetch_obo(g):
    print("Downloading GO ontology...")
    resp = requests.get(GO_OBO_URL, timeout=300)
    resp.raise_for_status()

    terms = []

    current = None

    for line in resp.iter_lines(
            decode_unicode=True,
    ):
        line = line.strip()

        if line == "[Term]":
            if current and current.get("id") and current.get("name"):
                terms.append(current)

            current = {}
            continue

        if current is None:
            continue

        if not line:
            continue

        if line.startswith("id: "):
            current["id"] = line[4:]

        elif line.startswith("name: "):
            current["name"] = line[6:]

        elif line.startswith("namespace: "):
            current["namespace"] = line[11:]

        elif line.startswith("def: "):
            current["definition"] = line[5:]

    if current and current.get("id") and current.get("name"):
        terms.append(current)

    print(f"Parsed {len(terms)} GO terms")
    texts = [t["name"] for t in terms]

    print("Embedding GO terms...")
    embeddings = embed_batch(texts)

    rows = []
    for term, embedding in zip(terms, embeddings):
        node = dict(
            id=term["id"],
            description=term["name"],
            namespace=term.get("namespace"),
            embedding=embedding,
            type="GO_TERM",
            sub_type="GO",
            embed_key="name",
        )

        g.add_node(node)

        rows.append(
            {
                "id": term["id"],
                "name": term["name"],
                "namespace": term.get("namespace"),
                "embedding": embedding.tolist(),
            }
        )

    DB.insert(table="GO_TERM", rows=rows, upsert=True)

    print(
        f"Stored {len(rows)} GO terms -> DB"
    )