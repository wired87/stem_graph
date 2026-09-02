# Deployment split

`Dockerfile.cloudrun` is the unprivileged Django/DRF control plane. It only
reads and writes PostgreSQL and never accesses Docker. Build it and replace the
placeholders in `cloudrun-service.yaml` before deploying to Cloud Run.

`Dockerfile.worker` is the StemCNV executor. Run exactly one instance on a
dedicated Linux VM with Docker, the canonical `stemcnv-check:1.0.0` image, and
the worker container's `/var/run/docker.sock` mounted read/write. Restrict the
VM service account and network access to PostgreSQL only. Configure identical
`POSTGRES_*` values on web and worker.

The split is required because canonical StemCNV invokes Apptainer and needs
privileged nested container execution, which is outside the Cloud Run runtime
contract. The web image therefore remains Cloud Run compatible and the worker
retains canonical scientific behavior on a Docker-capable host.

Local end-to-end startup remains:

```bash
docker compose up --build
```

The Compose file does not require repository-specific absolute paths. Runtime
files default to `./.runtime/stemcnv-runs`, and canonical fixtures default to
`./stemcnv-example-data`. Copy the official StemCNV example bundle into that
directory (so it contains `config.yaml`, a sample table, `RAW`, and
`static-data`) or override `STEMCNV_RUN_ROOT_HOST` and
`STEMCNV_EXAMPLE_DATA_HOST` in `.env` with VM paths when persistent disks are
mounted elsewhere. Never bake a developer home directory into an image or
Compose file.
