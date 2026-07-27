"""
ParquetMaster — single I/O surface for parquet files.

PROMPT (for traceability):
    "optimize the ParquetMaster class"

Optimization scope (kept inside this file, public API unchanged):
    * lazy `pq.ParquetFile` handle so write-only flows on a fresh path work
    * atomic downloads via `.part` rename (sync `receive` + async `_download_file`)
    * `receive` now actually returns the `ParquetMaster` instance + skips an
      existing target file (parity with `_download_file`)
    * atomic `write()` via `.tmp` rename so an interrupted write cannot
      corrupt an already-valid parquet on disk
    * `_crawl_parquet_urls` keeps going when a single subdirectory errors
"""

import os
import pyarrow.parquet as pq
import pyarrow as pa
import requests

import asyncio
from pathlib import Path
from typing import Union
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


# helper: small, safe atomic rename used by both download and write paths
def _atomic_replace(src: Path, dst: Path) -> None:
    # os.replace is atomic on the same filesystem on both Windows and POSIX
    os.replace(src, dst)


class ParquetMaster:
    def __init__(self, path: str):
        # accept str or Path without changing the public signature
        self.path = Path(path)
        # lazy parquet handle — only opened on first use (see `parquet` property)
        self._parquet = None

    @staticmethod
    def is_valid_parquet(path: Union[Path, str]) -> bool:
        """True only when pyarrow can open the file (rejects HTML stubs / truncated downloads)."""
        p = Path(path)
        if not p.is_file() or p.stat().st_size < 8:
            return False
        try:
            pq.ParquetFile(p)
            return True
        except Exception:
            return False

    @property
    def parquet(self) -> pq.ParquetFile:
        # open exactly once; re-open is forced by callers via `_invalidate()`
        if self._parquet is None:
            self._parquet = pq.ParquetFile(self.path)
        return self._parquet

    def _invalidate(self) -> None:
        # drop cached handle so a fresh `pq.ParquetFile` is opened next access
        self._parquet = None

    @classmethod
    def receive(
            cls,
            url: str,
            output_path: str,
            chunk_size: int = 1024 * 1024,
            validate: bool = True,
    ):
        """
        Download parquet from endpoint and return ParquetMaster.

        Existing target files are kept as-is (idempotent re-runs).
        The download streams to `<output_path>.part` and is renamed to the
        final name only after the response completes — no half files.

        Example:
            parquet = ParquetMaster.receive(
                "https://example.com/data.parquet",
                "data/data.parquet"
            )
        """

        output_path = Path(output_path)
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # idempotent: reuse only valid parquet — corrupt stubs are re-downloaded
        if output_path.exists():
            if cls.is_valid_parquet(output_path):
                print(f"skip (cached): {output_path}")
                return cls(str(output_path))
            print(f"invalid parquet — re-download: {output_path}")
            output_path.unlink()

        # stage download in a sibling .part so partial writes never look complete
        part_path = output_path.with_suffix(output_path.suffix + ".part")

        print(f"downloading parquet: {url}")

        with requests.get(
                url,
                stream=True,
                timeout=300,
        ) as response:
            response.raise_for_status()

            # write into the staging file
            with open(part_path, "wb") as f:
                for chunk in response.iter_content(
                        chunk_size=chunk_size
                ):
                    if chunk:
                        f.write(chunk)

        # promote staging file to final name only after a clean response
        _atomic_replace(part_path, output_path)

        print(
            f"download complete: "
            f"{output_path} "
            f"({round(output_path.stat().st_size / 1024 / 1024, 2)} MB)"
        )

        # build the instance once, used for optional validation and as return value
        parquet = cls(str(output_path))

        # optional validation kept (unchanged default), now non-blocking for return
        if validate:
            try:
                parquet.read(
                    return_dict=False,
                    print_specs=True,
                )
            except Exception as e:
                print(f"validation failed: {e}")

        # FIX: previously this method silently returned None — callers expected the instance
        return parquet


    def read(
            self,
            return_dict: bool = True,
            print_specs: bool = True,
    ):
        metadata = self.parquet.metadata

        # stat once — both size_bytes and size_mb derive from the same snapshot
        st = self.path.stat()

        specs = {
            "file": str(self.path),
            # reuse the single stat call
            "size_bytes": st.st_size,
            # reuse the single stat call
            "size_mb": round(st.st_size / 1024 / 1024, 2),
            "num_rows": metadata.num_rows,
            "num_row_groups": metadata.num_row_groups,
            "num_columns": metadata.num_columns,
            "columns": self.parquet.schema.names,
            "schema": str(self.parquet.schema),
        }

        if print_specs:
            print("\n=== PARQUET FILE ===")
            print(f"file           : {specs['file']}")
            print(f"size_mb        : {specs['size_mb']}")
            print(f"rows           : {specs['num_rows']}")
            print(f"row_groups     : {specs['num_row_groups']}")
            print(f"columns        : {specs['num_columns']}")

            print("\n=== COLUMN NAMES ===")
            for col in specs["columns"]:
                print(col)

            print("\n=== SCHEMA ===")
            print(specs["schema"])

        if return_dict:
            return specs

        return None

    def iter_batches(
            self,
            batch_size: int = 10000,
            columns=None
    ):
        for batch in self.parquet.iter_batches(
                batch_size=batch_size,
                columns=columns
        ):
            yield batch

    def write(
            self,
            rows: list[dict],
            compression: str = "snappy",
            append: bool = False,
    ):
        """
        rows:
            [
                {"id": 1, "name": "a"},
                {"id": 2, "name": "b"},
            ]
        """

        if not rows:
            print("write skipped (0 rows)")
            return

        table = pa.Table.from_pylist(rows)

        if append and self.path.exists():
            existing = pq.read_table(self.path)
            table = pa.concat_tables(
                [existing, table],
                promote_options="default",
            )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")

        pq.write_table(
            table,
            tmp_path,
            compression=compression,
        )

        _atomic_replace(tmp_path, self.path)

        # force the next `parquet` access to re-open the freshly written file
        self._invalidate()

        print(
            f"parquet write done "
            f"(rows={table.num_rows}, cols={table.num_columns})"
        )


    @staticmethod
    async def _download_file(
            client: httpx.AsyncClient,
            semaphore: asyncio.Semaphore,
            url: str,
            output_file: Path,
            chunk_size: int = 1024 * 1024,
    ):
        async with semaphore:

            if output_file.exists():
                if ParquetMaster.is_valid_parquet(output_file):
                    print(f"skip: {output_file.name}")
                    return output_file
                print(f"invalid parquet — re-download: {output_file.name}")
                output_file.unlink()

            # CHAR: ASCII-only status lines — Unicode arrows crash cp1252 consoles before download starts
            print(f"downloading: {output_file.name}")

            # stage parallel downloads in `.part` files for the same atomicity guarantee
            part_file = output_file.with_suffix(output_file.suffix + ".part")

            async with client.stream(
                    "GET",
                    url,
            ) as response:
                response.raise_for_status()

                # write into the staging file
                with open(part_file, "wb") as f:
                    async for chunk in response.aiter_bytes(
                            chunk_size=chunk_size
                    ):
                        f.write(chunk)

            # promote staging file to final name only after a clean response
            _atomic_replace(part_file, output_file)

            print(f"done: {output_file.name}")

            return output_file

    @classmethod
    async def _crawl_parquet_urls(
            cls,
            client: httpx.AsyncClient,
            root_url: str,
    ) -> list[str]:

        visited = set()
        parquet_urls = []
        # CHAR: never crawl outside the requested FTP subtree (prevents full-platform scans)
        root_canon = root_url.rstrip("/") + "/"

        async def crawl(url: str):

            if url in visited:
                return

            if not url.startswith(root_canon) and url.rstrip("/") != root_url.rstrip("/"):
                return

            visited.add(url)

            print(f"scan: {url}")

            # one bad subdirectory must not abort the whole crawl
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as e:
                # log and skip — siblings keep crawling
                print(f"crawl error ({url}): {e}")
                return

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            tasks = []

            for a in soup.find_all("a"):

                href = a.get("href")

                if not href:
                    continue

                if href.startswith("?"):
                    continue

                if href.startswith("../"):
                    continue

                full_url = urljoin(
                    url,
                    href,
                )

                if href.endswith(".parquet"):
                    parquet_urls.append(full_url)

                elif href.endswith("/"):
                    tasks.append(
                        crawl(full_url)
                    )

            if tasks:
                await asyncio.gather(*tasks)

        await crawl(root_url)

        return sorted(set(parquet_urls))

    @classmethod
    async def receive_all(
            cls,
            ftp_url: str,
            output_dir: str,
            workers: int = 20,
    ) -> list[Path]:

        output_dir = Path(output_dir)

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        timeout = httpx.Timeout(
            connect=60,
            read=300,
            write=300,
            pool=300,
        )

        async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
        ) as client:

            parquet_urls = await cls._crawl_parquet_urls(
                client=client,
                root_url=ftp_url,
            )

            print(
                f"\nfound {len(parquet_urls)} parquet files\n"
            )

            semaphore = asyncio.Semaphore(
                workers,
            )

            tasks = []

            for url in parquet_urls:

                filename = url.split("/")[-1]

                output_file = (
                    output_dir /
                    filename
                )

                tasks.append(
                    cls._download_file(
                        client=client,
                        semaphore=semaphore,
                        url=url,
                        output_file=output_file,
                    )
                )

            files = await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

            success: list[Path] = []
            for item in files:
                if isinstance(item, Path):
                    success.append(item)
                elif isinstance(item, BaseException):
                    # CHAR: surface download failures instead of silent 0/N completed
                    print(f"download error: {item}")

            print(
                f"\ncompleted: "
                f"{len(success)}/{len(parquet_urls)}"
            )

            return success
