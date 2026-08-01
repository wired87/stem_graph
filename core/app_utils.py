"""
app_utils -- shared application infrastructure.

User prompt (Cursor session):
    "use a unified class for all web request core infrastructure.
     (schema as gotermfetcher but adaptable to all types of data)
     keep specific processors rely in the current corresponding files."

What lives here:
  * The single shared ``CLIENT`` (``httpx.AsyncClient``) used across the project.
  * ``AsyncApiFetcher`` -- the unified base class for all async web requests.
    Subclasses set ``BASE_URL`` / ``DEFAULT_HEADERS`` / ``RATE_LIMIT`` and add
    endpoint methods that call ``self._execute_get`` / ``self._execute_post``.
  * Constants (UniProt / PubChem / Uberon URLs, default timeout) and the Gem
    LLM handle used by the query pipeline.

Specific processors (graph construction, business logic that consumes the
JSON responses) stay in their corresponding files; only the HTTP core lives
here.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, ClassVar
import httpx

from _db import get_db_manager
from firegraph._db import DBManager

_UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
_PUBCHEM_COMPOUND = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/JSON"


_TISSLIST_URL = (
    "https://ftp.uniprot.org/pub/databases/uniprot/"
    "knowledgebase/complete/docs/tisslist.txt"
)

_UBERON_URL = "http://purl.obolibrary.org/obo/uberon/basic.obo"

_HTTP_TIMEOUT = 30
_UNIPROT_FIELDS = "accession,protein_name,gene_names,cc_function,go,cc_disease,cc_tissue_specificity"
_MAX_PROTEINS_PER_ORGAN = 50

CLIENT = httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
    ),
    timeout=120,
)

_logger = logging.getLogger(__name__)

DB = get_db_manager()


class AsyncApiFetcher:
    """
    Unified async web-request core.

    Schema (identical to the original ``go_term.GoApiFetcher`` but generic):
      * subclass sets ``BASE_URL`` (string) and may override
        ``DEFAULT_HEADERS`` and ``RATE_LIMIT``
      * subclass adds endpoint-specific async methods that build the full
        URL and call ``self._execute_get`` / ``self._execute_post``

    The base owns ALL HTTP plumbing:
      * shared ``CLIENT`` (``httpx.AsyncClient``)
      * per-subclass semaphore for concurrency control
      * uniform JSON-accept defaults + header merging
      * httpx-correct request flow (await get/post, sync ``raise_for_status``,
        sync ``.json()``); logs and re-raises ``httpx.HTTPError`` so callers
        can wrap with retry / fallback as needed.
    """

    BASE_URL: str = ""
    DEFAULT_HEADERS: dict[str, str] = {"Accept": "application/json"}
    RATE_LIMIT: int = 10

    # one semaphore per concrete subclass *class object* (created lazily so
    # subclasses do not have to call super().__init__)
    _SEMAPHORES: ClassVar[dict[type, asyncio.Semaphore]] = {}

    @classmethod
    def _semaphore(cls) -> asyncio.Semaphore:
        sem = asyncio.Semaphore(cls.RATE_LIMIT)
        return sem

    @classmethod
    def _merge_headers(cls, extra: dict[str, str] | None) -> dict[str, str]:
        # never mutate the class-level defaults
        merged = dict(cls.DEFAULT_HEADERS)
        if extra:
            merged.update(extra)
        return merged

    async def _execute_get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """GET ``url`` with rate-limit + uniform error handling, return parsed JSON."""
        async with self._semaphore():
            try:
                _logger.debug("GET %s", url)
                # build kwargs lazily so we never send ``timeout=None`` etc.
                kwargs: dict[str, Any] = {"headers": self._merge_headers(headers)}
                if params is not None:
                    kwargs["params"] = params
                if timeout is not None:
                    kwargs["timeout"] = timeout
                response = await CLIENT.get(url, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                _logger.error("GET %s failed: %s", url, e)
                raise

    async def _execute_post(
        self,
        url: str,
        *,
        json: Any | None = None,
        params: dict | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """POST ``url`` (typically JSON payload), return parsed JSON response."""
        async with self._semaphore():
            try:
                _logger.debug("POST %s", url)
                # same lazy-kwargs pattern as _execute_get for httpx clarity
                kwargs: dict[str, Any] = {"headers": self._merge_headers(headers)}
                if json is not None:
                    kwargs["json"] = json
                if params is not None:
                    kwargs["params"] = params
                if timeout is not None:
                    kwargs["timeout"] = timeout
                response = await CLIENT.post(url, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                _logger.error("POST %s failed: %s", url, e)
                raise

# Prompt: adapt GUI anatomical structure — BRAIN_TERMS presets for whole brain vs sub-parts (BME).
BRAIN_TERMS = [
    "Brain",
    "CNS",
    "Nervous system",
    "Limbic system",
    "Brain cortex",
    "Cerebellum",
    "Hippocampus",
    "Hypothalamus",
    "Brain stem",
    "Spinal cord",
    "Ganglion",
    "Glial cell",
    "Neuron",
    "Microglia",
    "Astrocyte",
]


QUERY_TRANSFORM_PROMPT=f"""
You are a query tansformator. Analyze the given Prompt and create a list of 5 comma sepparated keyywords that 
describe this biological process.  
Return just the keywords comma separated, no additional text.
"""
