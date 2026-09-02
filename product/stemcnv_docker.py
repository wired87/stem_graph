"""Production adapter for the canonical StemCNV-check Docker image."""
from __future__ import annotations

import os
import base64
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from django.core.files.base import ContentFile
from django.db import transaction

from product.models import StemCNVArtifact, StemCNVInput, StemCNVRun

IMAGE = os.getenv("STEMCNV_DOCKER_IMAGE", "stemcnv-check:1.0.0")
RUN_ROOT = Path(os.getenv("STEMCNV_RUN_ROOT", Path(tempfile.gettempdir()) / "stemcnv-runs"))
CACHE_VOLUME = os.getenv("STEMCNV_CACHE_VOLUME", "stemcnv-cache")
EXAMPLE_DATA_ROOT = Path(os.getenv("STEMCNV_EXAMPLE_DATA_DIR", "/var/lib/stemcnv-upstream/example_data"))
MEMORY_LIMIT = os.getenv("STEMCNV_MEMORY_LIMIT", "6700m")
MEMORY_SWAP_LIMIT = os.getenv("STEMCNV_MEMORY_SWAP_LIMIT", "10g")
WORKFLOW_MEMORY_MB = os.getenv("STEMCNV_WORKFLOW_MEMORY_MB", "6500")
SNAKEMAKE_OPTIONS = os.getenv(
    "STEMCNV_SNAKEMAKE_OPTIONS",
    "--set-resources run_CBS:mem_mb=6500 combined_PennCNV_output:mem_mb=6500",
)
EXECUTION_MODE = os.getenv("STEMCNV_EXECUTION_MODE", "direct")
PROCESS_ROLE = os.getenv("STEMCNV_PROCESS_ROLE", "all")


class StemCNVDockerError(RuntimeError):
    pass


class ActiveStemCNVRunError(StemCNVDockerError):
    """Raised when the single memory-bounded worker already owns a run."""


def _docker_prefix() -> list[str]:
    configured = os.getenv("STEMCNV_DOCKER_COMMAND", "").strip()
    if configured:
        return shlex.split(configured, posix=os.name != "nt")
    if shutil.which("docker"):
        return ["docker"]
    if os.name == "nt" and shutil.which("wsl.exe"):
        return ["wsl.exe", "-d", os.getenv("STEMCNV_WSL_DISTRO", "Ubuntu"), "-u", "root", "--", "docker"]
    raise StemCNVDockerError("No Docker CLI found; set STEMCNV_DOCKER_COMMAND")


def _run_docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([*_docker_prefix(), *args], capture_output=True, text=True,
                              timeout=int(os.getenv("STEMCNV_DOCKER_TIMEOUT", "300")), check=check)
    except (OSError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        raise StemCNVDockerError(detail.strip()) from exc


def _docker_host_path(path: Path) -> str:
    resolved = str(path.resolve())
    if _docker_prefix()[0].lower() != "wsl.exe":
        return resolved
    converted = subprocess.run(
        ["wsl.exe", "-d", os.getenv("STEMCNV_WSL_DISTRO", "Ubuntu"), "--", "wslpath", "-a", resolved],
        capture_output=True, text=True, check=True, timeout=30)
    return converted.stdout.strip()


def _safe_relative(value: str) -> Path:
    path = Path(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe path in StemCNV config: {value}")
    return path


def _upload_bytes(upload) -> bytes:
    upload.seek(0)
    content = upload.read()
    upload.seek(0)
    return content


def validate_upload_bundle(files) -> dict:
    """Validate a researcher bundle without staging or launching Docker."""
    uploads = list(files)
    by_name: dict[str, object] = {}
    duplicates = []
    for upload in uploads:
        name = Path(upload.name).name
        if name in by_name:
            duplicates.append(name)
        by_name[name] = upload
    if duplicates:
        raise ValueError(f"Duplicate filenames are not supported: {', '.join(sorted(set(duplicates)))}")
    config_upload = by_name.get("config.yaml")
    if config_upload is None:
        raise ValueError(
            "Custom-data mode: config.yaml is missing. Add it to the upload; "
            "StemCNV reads it inside Docker as /work/config.yaml. Example data will not be substituted."
        )
    try:
        config = yaml.safe_load(_upload_bytes(config_upload)) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"config.yaml cannot be read: {exc}") from exc
    definitions = config.get("array_definition") or {}
    if not isinstance(definitions, dict) or not definitions:
        raise ValueError("config.yaml must contain at least one array_definition")
    raw_folder = _safe_relative(str(config.get("raw_data_folder", "RAW")))
    required: dict[str, Path] = {}
    for definition in definitions.values():
        if not isinstance(definition, dict):
            raise ValueError("Each array_definition in config.yaml must be a mapping")
        for key, value in definition.items():
            if key.endswith("_file") and isinstance(value, str) and value != "__cache-default__":
                _safe_relative(value)
                required[Path(value).name] = _safe_relative(value)
    if not {"sample_table.tsv", "sample_table.xlsx"}.intersection(by_name):
        raise ValueError(
            "Custom-data mode: sample_table.tsv or sample_table.xlsx is missing. "
            "Add one of them; Docker reads it as /work/sample_table.tsv or /work/sample_table.xlsx. "
            "Example data will not be substituted."
        )
    missing = sorted(set(required).difference(by_name))
    if missing:
        locations = ", ".join(f"{name} → /work/{required[name].as_posix()}" for name in missing)
        raise ValueError(
            f"Custom-data mode: files named by config.yaml are missing: {locations}. "
            "Add these files to the same upload. Example data will not be substituted."
        )
    idat_names = [name for name in by_name if name.lower().endswith(".idat")]
    if not idat_names:
        raise ValueError(
            f"Custom-data mode: no IDAT measurements were found. Add matching *_Grn.idat and "
            f"*_Red.idat files; Docker reads them below /work/{raw_folder.as_posix()}/<sample>/. "
            "Example data will not be substituted."
        )
    pairs: dict[str, set[str]] = {}
    original_stems: dict[str, str] = {}
    for name in idat_names:
        lower = name.lower()
        if lower.endswith("_grn.idat"):
            stem = lower[:-9]
            pairs.setdefault(stem, set()).add("grn")
            original_stems[stem] = name[:-9]
        elif lower.endswith("_red.idat"):
            stem = lower[:-9]
            pairs.setdefault(stem, set()).add("red")
            original_stems[stem] = name[:-9]
    incomplete = sorted(key for key, colors in pairs.items() if colors != {"grn", "red"})
    unrecognized = len(idat_names) - sum(len(colors) for colors in pairs.values())
    if incomplete or unrecognized:
        details = []
        for stem in incomplete:
            original = original_stems[stem]
            sample_folder = original.split("_", 1)[0]
            missing_channels = ({"grn", "red"} - pairs[stem])
            for channel in sorted(missing_channels):
                suffix = "Grn" if channel == "grn" else "Red"
                details.append(
                    f"{original}_{suffix}.idat → /work/{raw_folder.as_posix()}/{sample_folder}/"
                    f"{original}_{suffix}.idat"
                )
        if unrecognized:
            details.append(f"{unrecognized} IDAT filename(s) do not end in _Grn.idat or _Red.idat")
        raise ValueError(
            "Custom-data mode: every sample needs a matching Green/Red IDAT pair. Missing or invalid: "
            + "; ".join(details)
            + ". Example data will not be substituted."
        )
    return {
        "files": len(uploads), "idat_pairs": len(pairs),
        "array_definitions": len(definitions), "required_config_files": len(required),
        "docker_config_path": "/work/config.yaml",
        "docker_sample_table_path": "/work/sample_table.tsv or /work/sample_table.xlsx",
        "docker_raw_data_path": f"/work/{raw_folder.as_posix()}",
    }


def _stage_uploads(files, run_dir: Path) -> None:
    uploads = list(files)
    validate_upload_bundle(uploads)
    names = {Path(upload.name).name for upload in uploads}
    config_upload = next((item for item in uploads if Path(item.name).name == "config.yaml"), None)
    if config_upload is None:
        raise ValueError("A canonical StemCNV config.yaml is required")
    config = yaml.safe_load(_upload_bytes(config_upload)) or {}
    destinations = {"config.yaml": Path("config.yaml"), "sample_table.tsv": Path("sample_table.tsv"),
                    "sample_table.xlsx": Path("sample_table.xlsx")}
    for definition in (config.get("array_definition") or {}).values():
        for key, value in definition.items():
            if key.endswith("_file") and isinstance(value, str) and value != "__cache-default__":
                destinations[Path(value).name] = _safe_relative(value)
    raw_folder = _safe_relative(str(config.get("raw_data_folder", "RAW")))
    for upload in uploads:
        name = Path(upload.name).name
        target = destinations.get(name)
        if target is None and ".idat" in [suffix.lower() for suffix in Path(name).suffixes]:
            target = raw_folder / name.split("_", 1)[0] / name
        destination = run_dir / (target or Path(name))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as handle:
            for chunk in upload.chunks():
                handle.write(chunk)
    missing = [name for name, relative in destinations.items() if name not in names and not (run_dir / relative).exists()]
    if "sample_table.xlsx" in missing and "sample_table.tsv" not in missing:
        missing.remove("sample_table.xlsx")
    if "sample_table.tsv" in missing and "sample_table.xlsx" not in missing:
        missing.remove("sample_table.tsv")
    if missing:
        raise ValueError(f"Missing StemCNV inputs: {', '.join(sorted(missing))}")


def _stage_example_data(run_dir: Path) -> None:
    """Stage only the canonical inputs, never outputs from a previous example run."""
    if not (EXAMPLE_DATA_ROOT / "config.yaml").is_file():
        raise ValueError(f"StemCNV example data is unavailable at {EXAMPLE_DATA_ROOT}")
    for name in ("config.yaml", "sample_table.tsv", "sample_table.xlsx"):
        source = EXAMPLE_DATA_ROOT / name
        if source.is_file():
            shutil.copy2(source, run_dir / name)
    for name in ("RAW", "static-data"):
        source = EXAMPLE_DATA_ROOT / name
        if source.is_dir():
            try:
                shutil.copytree(source, run_dir / name, copy_function=os.link)
            except OSError:
                shutil.copytree(source, run_dir / name, copy_function=shutil.copy2)


def _persist_artifacts(record: StemCNVRun, run_dir: Path) -> list[str]:
    if record.artifacts.exists():
        return [
            path for path in record.artifacts.values_list("path", flat=True)
            if _is_final_artifact(path)
        ]
    stored = []
    for path in run_dir.rglob("*"):
        relative = path.relative_to(run_dir)
        artifact_path = str(relative).replace("\\", "/")
        if not path.is_file() or not _is_final_artifact(artifact_path):
            continue
        content = path.read_bytes()
        if artifact_path.lower().endswith(".html"):
            content = _embed_report_images(content, lambda name: path.parent / "StemCNV-check-report-html_images" / name)
        StemCNVArtifact.objects.create(
            run=record, path=artifact_path, size=len(content), content=content
        )
        stored.append(artifact_path)
    return stored


def _is_final_artifact(path: str) -> bool:
    """Return only researcher-facing results, never workflow working files."""
    normalized = path.lower()
    return (
        normalized.endswith(".stemcnv-check-report.html")
        or normalized.endswith(".xlsx")
        or (".cnv_calls." in normalized and normalized.endswith((".vcf", ".vcf.gz")))
    )


_REPORT_IMAGE = re.compile(
    rb"(?:\./)?StemCNV-check-report-html_images/+([A-Za-z0-9_.-]+\.png)"
)


def _embed_report_images(content: bytes, image_source) -> bytes:
    """Make a StemCNV HTML report portable by embedding its linked PNG plots."""
    cache: dict[bytes, bytes] = {}

    def replace(match: re.Match[bytes]) -> bytes:
        name = match.group(1)
        if name not in cache:
            source = image_source(name.decode("ascii"))
            try:
                image = source.read_bytes() if isinstance(source, Path) else bytes(source)
            except (FileNotFoundError, TypeError):
                return match.group(0)
            cache[name] = b"data:image/png;base64," + base64.b64encode(image)
        return cache[name]

    return _REPORT_IMAGE.sub(replace, content)


def _download_content(artifact: StemCNVArtifact) -> bytes:
    """Return portable content while retaining the original DB artifact history."""
    content = bytes(artifact.content)
    if not artifact.path.lower().endswith(".html") or b"StemCNV-check-report-html_images" not in content:
        return content
    parent = artifact.path.rsplit("/", 1)[0]
    prefix = f"{parent}/StemCNV-check-report-html_images/"

    def image_source(name: str):
        return StemCNVArtifact.objects.only("content").get(
            run_id=artifact.run_id, path=f"{prefix}{name}"
        ).content

    return _embed_report_images(content, image_source)


def _launch_record(record: StemCNVRun) -> dict:
    run_id = record.run_id
    run_dir = RUN_ROOT / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    try:
        if record.input_source == "upload":
            uploads = [ContentFile(bytes(item.content), name=item.name) for item in record.inputs.all()]
            _stage_uploads(uploads, run_dir)
        else:
            _stage_example_data(run_dir)
        result = _run_docker("run", "-d", "--name", run_id, "--privileged",
                             "--memory", MEMORY_LIMIT, "--memory-swap", MEMORY_SWAP_LIMIT,
                             "--cpus", str(record.cores),
                             "-e", f"STEMCNV_LOCAL_CORES={record.cores}",
                             "-e", f"STEMCNV_MEMORY_MB={WORKFLOW_MEMORY_MB}",
                             "-e", f"STEMCNV_SNAKEMAKE_OPTIONS={SNAKEMAKE_OPTIONS}",
                             "-v", f"{_docker_host_path(run_dir)}:/work",
                             "-v", f"{CACHE_VOLUME}:/cache", IMAGE, "run")
    except Exception as exc:
        record.status = "failed"
        record.events = [*record.events, {"type": "failed", "message": str(exc),
                                         "at": datetime.now(timezone.utc).isoformat()}]
        record.save()
        shutil.rmtree(run_dir, ignore_errors=True)
        raise
    record.container_id = result.stdout.strip()
    record.status = "running"
    record.events = [*record.events, {"type": "run_started", "message": "Docker analysis started",
                                      "at": datetime.now(timezone.utc).isoformat()}]
    record.save()
    return {"status": record.status, "run_id": run_id, "container_id": record.container_id,
            "input_source": record.input_source, "output_name": record.output_name,
            "events": record.events}


def start_run(files, *, cores: int = 3, output_name: str = "stemcnv-results.zip") -> dict:
    active = StemCNVRun.objects.filter(status__in=["queued", "starting", "created", "running"]).first()
    if active:
        if active.status in {"queued", "starting"}:
            raise StemCNVDockerError(
                f"Run {active.run_id} is already queued. Wait for it to finish before starting another analysis."
            )
        try:
            active_state = get_run(active.run_id)
        except (FileNotFoundError, StemCNVDockerError):
            active_state = None
        if active_state and active_state["status"] in {"queued", "starting", "created", "running"}:
            raise ActiveStemCNVRunError(
                f"Run {active.run_id} is already active. Wait for it to finish before starting another analysis."
            )
    run_id = f"stemcnv-{uuid.uuid4().hex}"
    uploads = list(files)
    queued_event = {"type": "queued", "message": "Analysis queued for the StemCNV worker",
                    "at": datetime.now(timezone.utc).isoformat()}
    with transaction.atomic():
        record = StemCNVRun.objects.create(
            run_id=run_id, container_id="", status="queued",
            input_source="upload" if uploads else "canonical-example",
            output_name=output_name, cores=cores, events=[queued_event]
        )
        for upload in uploads:
            StemCNVInput.objects.create(
                run=record, name=Path(upload.name).name, size=upload.size, content=_upload_bytes(upload)
            )
    if EXECUTION_MODE == "direct":
        return _launch_record(record)
    return {"status": "queued", "run_id": run_id, "input_source": record.input_source,
            "output_name": output_name, "events": record.events}


def claim_and_launch_next() -> dict | None:
    with transaction.atomic():
        record = StemCNVRun.objects.select_for_update(skip_locked=True).filter(status="queued").first()
        if record is None:
            return None
        record.status = "starting"
        record.save(update_fields=["status", "updated_at"])
    return _launch_record(record)


def _collect_events(log_text: str, existing: list[dict]) -> list[dict]:
    seen = {(event.get("type"), event.get("message")) for event in existing}
    events = list(existing)
    for raw in log_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        event_type = None
        message = line
        if line.startswith("localrule "):
            event_type = "step_started"
            message = line.removeprefix("localrule ").rstrip(":").replace("_", " ")
        elif " of " in line and " steps (" in line and line.endswith("done"):
            event_type = "progress"
        elif line.startswith("Finished job "):
            event_type = "step_finished"
        elif line.startswith("Complete log:"):
            event_type = "workflow_complete"
        elif "Error" in line or "Exception" in line:
            event_type = "error"
        if event_type and (event_type, message) not in seen:
            events.append({"type": event_type, "message": message, "at": datetime.now(timezone.utc).isoformat()})
            seen.add((event_type, message))
    return events[-500:]


def get_run(run_id: str) -> dict:
    if not run_id.startswith("stemcnv-"):
        raise FileNotFoundError(run_id)
    try:
        record = StemCNVRun.objects.get(run_id=run_id)
    except StemCNVRun.DoesNotExist as exc:
        raise FileNotFoundError(run_id) from exc
    if record.status in {"queued", "starting"}:
        return {
            "run_id": run_id, "status": record.status, "exit_code": None,
            "input_source": record.input_source, "output_name": record.output_name,
            "events": record.events, "logs": record.logs,
        }
    if PROCESS_ROLE == "web":
        payload = {
            "run_id": run_id, "status": record.status,
            "exit_code": 0 if record.status == "complete" else None,
            "input_source": record.input_source, "output_name": record.output_name,
            "events": record.events, "logs": record.logs,
        }
        if record.status == "complete":
            payload["artifacts_url"] = f"/api/product/status-run/{run_id}/?download=1"
            payload["artifacts"] = [
                path for path in record.artifacts.values_list("path", flat=True)
                if _is_final_artifact(path)
            ]
        return payload
    state = _run_docker("inspect", "-f", "{{.State.Status}}|{{.State.ExitCode}}", run_id, check=False)
    if state.returncode:
        raise FileNotFoundError(run_id)
    container_status, exit_code = state.stdout.strip().split("|", 1)
    logs = _run_docker("logs", "--tail", "500", run_id, check=False)
    log_text = logs.stdout + logs.stderr
    events = _collect_events(log_text, record.events)
    public_status = container_status
    if container_status == "exited":
        public_status = "complete" if exit_code == "0" else "failed"
        if not events or events[-1].get("type") != public_status:
            events.append({"type": public_status, "message": f"Workflow {public_status}",
                           "at": datetime.now(timezone.utc).isoformat()})
        if record.completed_at is None:
            record.completed_at = datetime.now(timezone.utc)
        if exit_code == "0":
            artifacts_url = f"/api/product/status-run/{run_id}/?download=1"
        else:
            artifacts_url = None
    else:
        artifacts_url = None
    record.status, record.events, record.logs = public_status, events, log_text[-50000:]
    record.save()
    payload = {"run_id": run_id, "status": public_status, "exit_code": int(exit_code),
               "input_source": record.input_source, "output_name": record.output_name,
               "events": events, "logs": record.logs}
    if artifacts_url:
        payload["artifacts_url"] = artifacts_url
        payload["artifacts"] = _persist_artifacts(record, RUN_ROOT / run_id)
        shutil.rmtree(RUN_ROOT / run_id, ignore_errors=True)
    return payload


def archive_run(run_id: str):
    state = get_run(run_id)
    if state["status"] != "complete":
        raise StemCNVDockerError(f"Run is {state['status']}")
    archive = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, suffix=".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        artifacts = StemCNVArtifact.objects.filter(run_id=run_id)
        for artifact in artifacts.iterator(chunk_size=1):
            if not _is_final_artifact(artifact.path):
                continue
            bundle.writestr(artifact.path, _download_content(artifact))
    archive.seek(0)
    return archive


def get_download_name(run_id: str) -> str:
    return StemCNVRun.objects.values_list("output_name", flat=True).get(run_id=run_id)


def cancel_run(run_id: str) -> dict:
    record = StemCNVRun.objects.get(run_id=run_id)
    if record.status not in {"queued", "starting", "created", "running", "cancelling"}:
        return {"run_id": run_id, "status": record.status}
    if record.status in {"running", "cancelling"} and PROCESS_ROLE != "web":
        _run_docker("stop", "--time", "30", run_id, check=False)
    elif record.status == "running":
        record.events = [*record.events, {"type": "cancellation_requested",
                                          "message": "Cancellation requested from web service",
                                          "at": datetime.now(timezone.utc).isoformat()}]
        record.status = "cancelling"
        record.save()
        return {"run_id": run_id, "status": record.status, "events": record.events}
    record.status = "cancelled"
    record.completed_at = datetime.now(timezone.utc)
    record.events = [*record.events, {"type": "cancelled", "message": "Run cancelled safely",
                                      "at": record.completed_at.isoformat()}]
    record.save()
    return {"run_id": run_id, "status": "cancelled", "events": record.events}
