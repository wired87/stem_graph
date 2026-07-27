# GCP Batch client: submit, inspect, cancel, and list StemCNV executable jobs
import re
import uuid
from typing import Any

from google.cloud import batch_v1
from google.protobuf import json_format

from product.batch.config import BatchConfig
from product.batch.hardware import BatchHardware


# GCP Batch job_id: lowercase letters, digits, hyphens, max 63 chars
_JOB_ID_RE = re.compile(r"[^a-z0-9-]")


def sanitize_job_id(value: str) -> str:
    # Normalize arbitrary session ids into a valid Batch job_id
    job_id = _JOB_ID_RE.sub("-", value.lower().strip("-"))
    job_id = re.sub(r"-+", "-", job_id).strip("-")
    if not job_id:
        job_id = f"cnvmaster-{uuid.uuid4().hex[:12]}"
    return job_id[:63]


def job_to_dict(job: batch_v1.Job) -> dict[str, Any]:
    # Convert protobuf Job to JSON-serializable dict for API responses
    payload = json_format.MessageToDict(job._pb)
    return {
        "name": job.name,
        "uid": job.uid,
        "state": batch_v1.Job.State(job.state).name if job.state else "STATE_UNSPECIFIED",
        "create_time": job.create_time.isoformat() if job.create_time else None,
        "update_time": job.update_time.isoformat() if job.update_time else None,
        "labels": dict(job.labels),
        "status": payload.get("status", {}),
    }


class BatchManager:
    """Start and manage GCP Batch jobs for product/executable runs."""

    def __init__(self, config: BatchConfig | None = None):
        # Lazy client — created on first API call
        self.config = config or BatchConfig.from_env()
        self._client: batch_v1.BatchServiceClient | None = None

    @property
    def client(self) -> batch_v1.BatchServiceClient:
        if self._client is None:
            self._client = batch_v1.BatchServiceClient()
        return self._client

    def _build_job(
        self,
        user_id: str,
        session_id: str,
        env_overrides: dict[str, str] | None = None,
        hardware: BatchHardware | None = None,
        image_uri: str | None = None,
    ) -> batch_v1.Job:
        # Resolved VM/task sizing: POST hardware overrides env defaults
        hw = (hardware or BatchHardware()).resolve(self.config)

        # Container runnable: EXEC_DOCKER_PATH image, CMD is python main.py
        runnable = batch_v1.Runnable()
        runnable.container = batch_v1.Runnable.Container()
        runnable.container.image_uri = image_uri or self.config.image_uri

        # Env vars consumed by product/executable/main.py
        env = {
            "USER_ID": user_id,
            "SESSION_ID": session_id,
            "GBUCKET_NAME": self.config.bucket_name,
            "MAIN_BUCKET": self.config.bucket_name,
            "GCP_ID": self.config.gcp_id,
        }
        if env_overrides:
            env.update({k: str(v) for k, v in env_overrides.items()})
        runnable.environment = batch_v1.Environment(variables=env)

        # Per-task CPU/RAM for Snakemake workload
        resources = batch_v1.ComputeResource()
        resources.cpu_milli = hw.cpu_milli
        resources.memory_mib = hw.memory_mib

        task = batch_v1.TaskSpec()
        task.runnables = [runnable]
        task.compute_resource = resources
        task.max_retry_count = self.config.max_retry_count
        task.max_run_duration = hw.max_run_duration

        group = batch_v1.TaskGroup()
        group.task_count = hw.task_count
        group.task_spec = task

        # VM shape for Batch workers
        policy = batch_v1.AllocationPolicy.InstancePolicy()
        policy.machine_type = hw.machine_type
        instances = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
        instances.policy = policy

        allocation = batch_v1.AllocationPolicy()
        allocation.instances = [instances]
        if self.config.service_account:
            sa = batch_v1.ServiceAccount()
            sa.email = self.config.service_account
            allocation.service_account = sa
        if self.config.network:
            net = batch_v1.AllocationPolicy.NetworkPolicy()
            net.network_interfaces = [
                batch_v1.AllocationPolicy.NetworkInterface(
                    network=self.config.network,
                    subnetwork=self.config.subnetwork or None,
                )
            ]
            allocation.network = net

        job = batch_v1.Job()
        job.task_groups = [group]
        job.allocation_policy = allocation
        job.labels = {
            "app": "cnvmaster",
            "user_id": sanitize_job_id(user_id)[:63],
            "session_id": sanitize_job_id(session_id)[:63],
        }
        job.logs_policy = batch_v1.LogsPolicy()
        job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING
        return job

    def submit_session_job(
        self,
        user_id: str,
        session_id: str | None = None,
        job_id: str | None = None,
        env_overrides: dict[str, str] | None = None,
        hardware: BatchHardware | None = None,
        image_uri: str | None = None,
    ) -> dict[str, Any]:
        # Create a Batch job for one StemCNV session
        if not self.config.project_id:
            raise ValueError("GCP_PROJECT_ID or GCP_ID must be set")
        if not user_id:
            raise ValueError("user_id is required")
        docker_image = image_uri or self.config.image_uri
        if not docker_image:
            raise ValueError("EXEC_DOCKER_PATH must be set")

        session_id = session_id or uuid.uuid4().hex
        job_id = sanitize_job_id(job_id or f"cnvmaster-{session_id}")
        job = self._build_job(user_id, session_id, env_overrides, hardware, docker_image)

        request = batch_v1.CreateJobRequest()
        request.parent = self.config.parent
        request.job_id = job_id
        request.job = job

        created = self.client.create_job(request=request)
        info = job_to_dict(created)
        info["job_id"] = job_id
        info["user_id"] = user_id
        info["session_id"] = session_id
        info["image_uri"] = docker_image
        resolved = (hardware or BatchHardware()).resolve(self.config)
        info["hardware"] = {
            "machine_type": resolved.machine_type,
            "cpu_milli": resolved.cpu_milli,
            "memory_mib": resolved.memory_mib,
            "task_count": resolved.task_count,
            "max_run_duration": resolved.max_run_duration,
        }
        return info

    def get_job(self, job_id: str) -> dict[str, Any]:
        # Fetch job state by short job_id or full resource name
        name = job_id if job_id.startswith("projects/") else f"{self.config.parent}/jobs/{sanitize_job_id(job_id)}"
        job = self.client.get_job(name=name)
        info = job_to_dict(job)
        info["job_id"] = name.rsplit("/", 1)[-1]
        return info

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        # Request graceful job cancellation
        name = job_id if job_id.startswith("projects/") else f"{self.config.parent}/jobs/{sanitize_job_id(job_id)}"
        self.client.delete_job(name=name)
        return {"job_id": name.rsplit("/", 1)[-1], "action": "cancel_requested"}

    def list_jobs(self, user_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        # List recent jobs, optionally filtered by user_id label
        filter_parts = ['labels.app="cnvmaster"']
        if user_id:
            filter_parts.append(f'labels.user_id="{sanitize_job_id(user_id)[:63]}"')
        request = batch_v1.ListJobsRequest()
        request.parent = self.config.parent
        request.filter = " AND ".join(filter_parts)
        request.order_by = "create_time desc"

        jobs: list[dict[str, Any]] = []
        for job in self.client.list_jobs(request=request):
            info = job_to_dict(job)
            info["job_id"] = job.name.rsplit("/", 1)[-1]
            jobs.append(info)
            if len(jobs) >= limit:
                break
        return jobs
