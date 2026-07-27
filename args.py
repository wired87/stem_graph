import httpx

CLIENT = httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
    ),
    timeout=120,
)