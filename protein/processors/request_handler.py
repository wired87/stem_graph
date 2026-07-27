from typing import Any
from aiolimiter import AsyncLimiter
from core.app_utils import AsyncApiFetcher

UNIPROT_LIMITER = AsyncLimiter(
    max_rate=4,
    time_period=1.0
)

class UniProtSearchFetcher(AsyncApiFetcher):
    BASE_URL = "https://rest.uniprot.org/uniprotkb/search"
    RATE_LIMIT = 4

    async def search(self, query: str, *, size: int = 500, timeout: float = 30.0) -> Any:
        """Run a UniProt KB search and return the parsed JSON payload."""
        params = {"query": query, "format": "json", "size": size}
        return await self._execute_get(self.BASE_URL, params=params, timeout=timeout)


