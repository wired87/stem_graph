# GCP Batch settings loaded from environment (aligned with admin/ar_registry)
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BatchConfig:
    """Runtime configuration for GCP Batch job submission."""

    project_id: str
    region: str
    image_uri: str
    machine_type: str
    cpu_milli: int
    memory_mib: int
    max_retry_count: int
    max_run_duration: str
    task_count: int
    bucket_name: str
    gcp_id: str
    service_account: str
    network: str
    subnetwork: str

    @classmethod
    def from_env(cls) -> "BatchConfig":
        # GCP project + region for Batch API parent path
        project_id = os.getenv("GCP_PROJECT_ID", os.getenv("GCP_ID", ""))
        region = os.getenv("GCP_BATCH_REGION", os.getenv("GCP_REGION", "us-central1"))
        # Container image: EXEC_DOCKER_PATH (primary) or Artifact Registry fallback
        repo = os.getenv("GCP_ARTIFACT_REPO", "qfs-repo")
        image_name = os.getenv("GCP_BATCH_IMAGE", os.getenv("GCP_EXECUTABLE_IMAGE", "cnvmaster-executable"))
        tag = os.getenv("GCP_BATCH_IMAGE_TAG", "latest")
        default_image = f"{region}-docker.pkg.dev/{project_id}/{repo}/{image_name}:{tag}"
        image_uri = os.getenv("EXEC_DOCKER_PATH") or os.getenv("GCP_BATCH_IMAGE_URI", default_image)
        return cls(
            project_id=project_id,
            region=region,
            image_uri=image_uri,
            machine_type=os.getenv("GCP_BATCH_MACHINE_TYPE", "e2-standard-8"),
            cpu_milli=int(os.getenv("GCP_BATCH_CPU_MILLI", "8000")),
            memory_mib=int(os.getenv("GCP_BATCH_MEMORY_MIB", "32768")),
            max_retry_count=int(os.getenv("GCP_BATCH_MAX_RETRIES", "1")),
            max_run_duration=os.getenv("GCP_BATCH_MAX_RUN_DURATION", "86400s"),
            task_count=int(os.getenv("GCP_BATCH_TASK_COUNT", "1")),
            bucket_name=os.getenv("GBUCKET_NAME", os.getenv("MAIN_BUCKET", "bestbrain")),
            gcp_id=os.getenv("GCP_ID", project_id),
            service_account=os.getenv("GCP_BATCH_SERVICE_ACCOUNT", ""),
            network=os.getenv("GCP_BATCH_NETWORK", ""),
            subnetwork=os.getenv("GCP_BATCH_SUBNETWORK", ""),
        )

    @property
    def parent(self) -> str:
        # Batch API parent: projects/{project}/locations/{region}
        return f"projects/{self.project_id}/locations/{self.region}"
