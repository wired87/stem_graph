"""
drug -- ChEMBL drug lookup for ion-channel proteins.

User prompt (Cursor session):
    "use a unified class for all web request core infrastructure.
     (schema as gotermfetcher but adaptable to all types of data)
     keep specific processors rely in the current corresponding files."

``ChemblFetcher`` is the unified HTTP core for the whole ChEMBL surface used
by this project (drug-by-uniprot here, target/molecule/activity in
``link_drugs_to_trgts.py``). The graph-construction processors stay where
they were.
"""
from __future__ import annotations
from core.app_utils import AsyncApiFetcher
from drug_master.process_drug import process_drug_item

BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

class ChemblFetcher(AsyncApiFetcher):
    BASE_URL = BASE_URL
    RATE_LIMIT = 8
    DEFAULT_HEADERS = HEADERS

    async def drugs_for_uniprot(self, uniprot_id: str, *, timeout: float = 30.0):
        url = f"{self.BASE_URL}/drug/"
        params = {
            "mechanism_of_action__target_components__accession": uniprot_id,
            "mechanism_of_action__target_organism": "Homo sapiens",
            "format": "json",
        }
        return await self._execute_get(url, params=params, timeout=timeout)

    async def drug_by_id(
            self,
            chembl_id: str,
            timeout: float = 30.0,
    ):
        url = (
            f"{self.BASE_URL}/molecule/"
            f"{chembl_id}.json"
        )
        return await self._execute_get(
            url,
            timeout=timeout,
        )

    async def mechanisms_for_drug_and_target(
            self,
            molecule_chembl_id: str,
            target_chembl_id: str,
            timeout: float = 30.0,
    ):
        #
        url = f"{self.BASE_URL}/mechanism.json"
        #
        params = {
            "molecule_chembl_id": molecule_chembl_id,
            "target_chembl_id": target_chembl_id,
            "format": "json",
            "only": "mechanisms",
        }
        #
        return await self._execute_get(
            url,
            params=params,
            timeout=timeout,
        )


    async def targets_by_drug_and_mechanism(
            self,
            mechanisms: dict,
            mechanism: str | None = None,
    ):
        """
        Receive ChEMBL mechanism response.

        Optional:
            mechanism="INHIBITOR"

        Returns:
            list[target_chembl_id]
        """

        targets = []

        for row in mechanisms.get(
                "mechanisms",
                [],
        ):

            action_type = (
                row.get(
                    "action_type",
                    "",
                )
                .strip()
                .upper()
            )

            if mechanism is not None:
                if action_type != mechanism.upper():
                    continue

            target_id = row.get(
                "target_chembl_id"
            )

            if target_id:
                targets.append(
                    target_id
                )

        return list(
            set(targets)
        )

    async def target_details(self, target_id: str, *, timeout: float = 30.0):
        """Full target record (with component proteins) for a ChEMBL target id."""
        url = f"{self.BASE_URL}/target/{target_id}"
        return await self._execute_get(url, timeout=timeout)

    async def drug_indication(self, params):
        """Drug indications"""
        url = f"{self.BASE_URL}/drug_indication.json"
        return await self._execute_get(url, params=params, timeout=30)

    async def molecule_by_name(self, drug_name: str, *, timeout: float = 30.0):
        """ChEMBL molecule records whose preferred name matches ``drug_name``."""
        url = f"{self.BASE_URL}/molecule.json"
        params = {"pref_name__iexact": drug_name}
        return await self._execute_get(url, params=params, timeout=timeout)

    async def activities_for_molecule(self, molecule_chembl_id: str, *, timeout: float = 30.0):
        """Bioactivity records (IC50 / Ki, nM) for one molecule against human targets."""
        url = f"{self.BASE_URL}/activity.json"
        params = {
            "molecule_chembl_id": molecule_chembl_id,
            "target_organism": "Homo sapiens",
            "standard_type__in": "IC50,Ki",
            "standard_units": "nM",
            "format": "json",
        }
        return await self._execute_get(url, params=params, timeout=timeout)


    async def activities_for_molecule_target(
            self,
            molecule_chembl_id: str,
            target_chembl_id: str,
            timeout: float = 30.0,
    ):
        url = f"{self.BASE_URL}/activity.json"

        params = {
            "molecule_chembl_id": molecule_chembl_id,
            "target_chembl_id": target_chembl_id,
            "target_organism": "Homo sapiens",
            "standard_type__in": "IC50,Ki,Kd,EC50",
            "format": "json",
        }

        return await self._execute_get(
            url,
            params=params,
            timeout=timeout,
        )

    async def mechanisms_for_molecule(
            self,
            molecule_chembl_id: str,
            timeout: float = 30.0,
    ):
        url = f"{self.BASE_URL}/mechanism.json"

        params = {
            "molecule_chembl_id": molecule_chembl_id,
            "format": "json",
        }

        return await self._execute_get(
            url,
            params=params,
            timeout=timeout,
        )

    async def targets_for_uniprots(
            self,
            uniprot_ids: list[str],
            *,
            timeout: float = 30.0,
    ):
        """
        UniProt accession -> ChEMBL targets
        """

        async def fetch_target(uniprot_id: str):
            url = f"{self.BASE_URL}/target/"
            params = {
                "target_components__accession": uniprot_id,
                "format": "json",
            }

            try:
                result = await self._execute_get(
                    url,
                    params=params,
                    timeout=timeout,
                )

                return {
                    "uniprot_id": uniprot_id,
                    "result": result,
                }

            except Exception as e:
                print(f"Failed target lookup {uniprot_id}: {e}")

                return {
                    "uniprot_id": uniprot_id,
                    "result": None,
                    "error": str(e),
                }

        tasks = [
            fetch_target(uniprot_id)
            for uniprot_id in uniprot_ids
        ]
        print("targets_for_uniprots ...done ")

        return await asyncio.gather(
            *tasks,
            return_exceptions=False,
        )


_CHEMBL_FETCHER = ChemblFetcher()
import asyncio


async def drugs_details_for_ids(g) -> list:
    print("UPDATE DRUGS WITH DETAILS...")
    molecule_ids: list[str] = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "MOLECULE"
    ]

    drug_tasks = [
        _CHEMBL_FETCHER.drug_by_id(
            molecule_id
        )
        for molecule_id in molecule_ids
    ]

    drug_results = await asyncio.gather(
        *drug_tasks,
        return_exceptions=True,
    )

    for res, nid in zip(drug_results, molecule_ids):
        process_drug_item(g, dict(id=nid, **res))
    print("DRUGS UPDATED WITH DETAILS... DONE")









def include_drugs_for_channels(data, uniprot_id, g) -> list:
    """
    Processes a drug action o a speciific uniprt target id
    """
    try:
        drugs_data = data.get("drugs", [])

        parsed_drugs = []
        for drug_record in drugs_data:
            process_drug_item(g, drug_record)

        print(f"[+] Successfully resolved {len(parsed_drugs)} human-targeted drugs for UniProt: {uniprot_id}")
        return parsed_drugs
    except Exception as e:
        print(f"[!] Error resolving drug data for UniProt: {e}")
        return []


async def get_drugs_for_channels(g):
    print("get_drugs_for_channels...")
    uniprot_ids = [
        nid
        for nid, attrs in g.G.nodes(data=True)
        if attrs.get("type") == "PROTEIN"
        and attrs.get("sub_type", "") != "PURE_INFLUENCE"
    ]
    print(f"Process {len(uniprot_ids)} protein ion channel targets...")

    tasks = [_CHEMBL_FETCHER.drugs_for_uniprot(uid) for uid in uniprot_ids]
    batch_results = await asyncio.gather(*tasks)

    print("[*] Merging datasets and injecting relations into graph wrapper...")
    for continuous_list, upid in zip(batch_results, uniprot_ids):
        include_drugs_for_channels(
            data=continuous_list,
            uniprot_id=upid,
            g=g
        )

    print("[+] Batch optimization pipeline completed successfully.")



if __name__ == "__main__":
    sample_uniprot_targets = ["O15554", "P12345", "Q9ABC4"]

