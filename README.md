# CNVMaster

Django API project with section-based apps for product, file, infrastructure, and user endpoints.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Docker (DRF API)

```bash
docker build -t cnvmaster-api .
docker run --rm -p 8000:8000 -e ALLOWED_HOSTS=* cnvmaster-api
```

API at `http://localhost:8000/api/...` (migrations run automatically on container start via `main.py`).

## API Routes

| Section | Endpoint |
|---------|----------|
| Product | `/api/product/run-sample/`, `/api/product/status-run/` |
| File | `/api/file/get-file-names/`, `/api/file/get-file/`, `/api/file/set-file/`, `/api/file/delete-file/`, `/api/file/update-file/` |
| Infrastructure | `/api/infrastructure/machine/on/`, `/api/infrastructure/machine/off/` |
| User | `/api/user/get-file-names/`, `/api/user/get-file/`, `/api/user/set-file/`, `/api/user/delete-file/`, `/api/user/update-file/` |

## Workflow Graph

```mermaid
flowchart LR
  %% Actors
  Client[Client / Frontend]
  GitHub[(GitHub)]
  GCS[(GCS Bucket\nGBUCKET_NAME)]
  Batch[(GCP Batch)]
  AR[(Artifact Registry)]

  %% API surface
  subgraph DjangoAPI[CNVMaster Django API]
    FileSet[/POST /api/file/set-file/]
    FileGet[/POST /api/file/get-file/]
    ProductRun[/POST /api/product/run-sample/]
    ProductStatus[/GET|POST /api/product/status-run/]
  end

  %% Admin publishing
  subgraph AdminTools[admin/*]
    PubExec[publish_executable.py\nGitHub Git Data API push]
    PubProj[publish_project.py\ngit commit + push]
  end

  %% Executable runtime
  subgraph Executable[product/executable container\npython main.py]
    FetchInput[Step 1: download prefix\nUSER_ID/input/SESSION_ID/ → input/]
    Config[Step 2: config.yaml\nuse input/config.yaml if present\nelse build from discovered local paths]
    Run[Step 3: run StemCNV-check\n(stemcnv_check run ...)]
    Metadata[Write logs\nexecution_timing.json + metadata.json]
    Upload[Step 4: upload out/ + logs/\n→ USER_ID/output/SESSION_ID/]
  end

  %% Input preparation via file routes
  Client --> FileSet
  FileSet -->|upload inputs\n(.bpm/.egt/.csv/.idat, sample_table.tsv, ...)| GCS
  FileSet -->|when payload has config={...}\ncreate config.yaml under input/<session_id>/| GCS
  Client --> FileGet --> GCS

  %% Batch submission + status
  Client --> ProductRun --> Batch
  Client --> ProductStatus --> Batch
  Batch -->|starts container with env:\nUSER_ID, SESSION_ID, GBUCKET_NAME| Executable

  %% Executable IO
  Executable --> FetchInput --> Config --> Run --> Metadata --> Upload --> GCS

  %% Admin publish -> image supply chain (high level)
  PubExec --> GitHub
  PubProj --> GitHub
  GitHub -->|CI/build step (external)\nbuilds Docker image| AR
  AR -->|EXEC_DOCKER_PATH points here| ProductRun
```

## Progress

- [x] Django project scaffold
- [x] Django REST framework installed
- [x] `product` app with `views/` APIViews: run-sample, status-run
- [x] `file` app with `views/` APIViews: get-file-names, get-file, set-file, delete-file, update-file
- [x] `infrastructure` app with `views/` APIViews: machine on/off
- [x] `user` app with `views/` APIViews: get-file-names, get-file, set-file, delete-file, update-file
- [x] Root URL wiring under `/api/<section>/`
- [x] Cloned `_g_storage` into `file/_g_storage` and wired file endpoints to `GBucket`
- [x] File routes use `user_id`/`auth` from `request.data`, fallback `TEST_USER_ID` env
- [x] `product/config_creator.py`: StemCNV `config.yaml` builder; `file/set-file` upserts to `input/<session_id>/config.yaml` from `config` payload
- [x] Executable `main.py` uses downloaded `input/config.yaml` when present; falls back to local path discovery
- [x] Executable `main.py` tracks per-step timing in `logs/execution_timing.json`; falls back to `test_data/` when no input
- [x] Executable writes `metadata.json` (start/stop, hardware, limits) and upserts to `{USER_ID}/output/{SESSION_ID}/metadata.json`
- [x] Executable upserts full session output to GCS: `out/` + `logs/` under `{USER_ID}/output/{SESSION_ID}/`
- [x] Cloned `fb_core` and extended with `sync_user_session`, `resolve_billing_user_id`, `record_purchase_event`, `ensure_user_bucket_folder`
- [x] User routes wired to JWT auth (`user.accounts.jwt_auth`), `GBucket` storage, and `FirebaseAdmin` RTDB history
- [x] Registered `accounts` app + `AUTH_USER_MODEL`; `user/` on `sys.path` for legacy `accounts.*` imports
- [x] Root `Dockerfile` + `main.py` expose DRF API on port 8000 (`python main.py`)
- [x] `product/batch/`: GCP Batch config + `BatchManager` (submit, get, cancel, list jobs for executable image)
- [x] Product `run-sample` submits GCP Batch jobs via `EXEC_DOCKER_PATH`; `hardware` POST fields override VM/task sizing
- [x] `file/tests.py`: integration tests for all file API routes; upsert uses `product/executable/example_data`
- [ ] Business logic implementation for infrastructure endpoints
- [x] `admin/` dir: cloned `ar_registry`, `auth/` for credentials, `publish_executable.py` (GitHub API), `publish_project.py` (git push with auth + `.env`), `main.py` orchestrator
- [x] README workflow graph: connected Mermaid flow for file upload, config upsert, Batch run, executable I/O, and admin publish
# Local PostgreSQL startup

The standard local stack uses PostgreSQL 16. Copy `.env.example` to `.env` if
you want to change the local credentials, then start everything with:

```bash
docker compose up --build
```

The `postgres` service is health-checked before `web` starts. The generic
`main.py` entrypoint waits for the database, applies all Django migrations, and
then starts Django/DRF on <http://localhost:8000>.

For a host-run Django process with only PostgreSQL in Docker:

```bash
docker compose up -d postgres
DJANGO_SETTINGS_MODULE=cnvmaster.settings_stemcnv_server python main.py
```

PostgreSQL is the default. SQLite is reserved for isolated tests and must be
selected explicitly with `DJANGO_DB_ENGINE=sqlite`.
