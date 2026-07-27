# Parse Batch VM / task hardware from API request payloads
from dataclasses import dataclass
from typing import Any

from product.batch.config import BatchConfig


@dataclass(frozen=True)
class BatchHardware:
    """Per-job hardware overrides for GCP Batch allocation and task resources."""

    machine_type: str | None = None
    cpu_milli: int | None = None
    memory_mib: int | None = None
    task_count: int | None = None
    max_run_duration: str | None = None

    def resolve(self, defaults: BatchConfig) -> "BatchHardware":
        # Fill unset fields from env-based BatchConfig defaults
        return BatchHardware(
            machine_type=self.machine_type or defaults.machine_type,
            cpu_milli=self.cpu_milli if self.cpu_milli is not None else defaults.cpu_milli,
            memory_mib=self.memory_mib if self.memory_mib is not None else defaults.memory_mib,
            task_count=self.task_count if self.task_count is not None else defaults.task_count,
            max_run_duration=self.max_run_duration or defaults.max_run_duration,
        )

    def env_overrides(self) -> dict[str, str]:
        # Pass core limits into product/executable/main.py runtime
        env: dict[str, str] = {}
        if self.cpu_milli is not None:
            cores = max(1, self.cpu_milli // 1000)
            env["STEMCNV_LOCAL_CORES"] = str(cores)
            env["LOCAL_CORES"] = str(cores)
        if self.memory_mib is not None:
            env["STEMCNV_MEMORY_MB"] = str(self.memory_mib)
            env["MEMORY_MB"] = str(self.memory_mib)
        return env

    @classmethod
    def from_request(cls, data: dict[str, Any] | None) -> "BatchHardware":
        # Accept nested hardware={...} or flat keys on the POST body
        if not data:
            return cls()
        hw = data.get("hardware") if isinstance(data.get("hardware"), dict) else data
        return cls(
            machine_type=_str(hw.get("machine_type")),
            cpu_milli=_cpu_milli(hw),
            memory_mib=_memory_mib(hw),
            task_count=_int(hw.get("task_count")),
            max_run_duration=_str(hw.get("max_run_duration")),
        )


def _str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value).strip()


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _cpu_milli(hw: dict[str, Any]) -> int | None:
    # cpu_milli wins; cpus/local_cores are converted to milliCPU (1 core = 1000)
    if hw.get("cpu_milli") not in (None, ""):
        return int(hw["cpu_milli"])
    for key in ("cpus", "local_cores", "cores"):
        if hw.get(key) not in (None, ""):
            return int(hw[key]) * 1000
    return None


def _memory_mib(hw: dict[str, Any]) -> int | None:
    # memory_mib or memory_mb both map to Batch ComputeResource.memory_mib
    for key in ("memory_mib", "memory_mb"):
        if hw.get(key) not in (None, ""):
            return int(hw[key])
    return None
