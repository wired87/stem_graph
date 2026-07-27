"""Push product/executable tree to a private GitHub repo via the Git Data API."""

from __future__ import annotations

import base64
import os
from pathlib import Path

import dotenv
import requests

# Admin dir and default executable source (overridable via EXECUTABLE_SOURCE_DIR)
ADMIN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ADMIN_DIR.parent
DEFAULT_EXECUTABLE_DIR = PROJECT_ROOT / "product" / "executable"

# Paths skipped when packaging the executable (aligned with product/executable/.dockerignore)
SKIP_DIR_NAMES = {".git", ".venv", "__pycache__", ".snakemake", "tests", "docs", "example_data"}
SKIP_FILE_SUFFIXES = {".pyc"}


def load_env() -> None:
    """Load admin/.env so GITHUB_* credentials are available."""
    dotenv.load_dotenv(ADMIN_DIR / ".env")


def require_env(name: str) -> str:
    """Return a required env var or raise with a clear message."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name} (set it in admin/.env)")
    return value


def github_headers(token: str) -> dict[str, str]:
    """Standard GitHub REST headers for authenticated API calls."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def api_url(owner: str, repo: str, path: str = "") -> str:
    """Build a GitHub REST URL for a repository endpoint."""
    base = f"https://api.github.com/repos/{owner}/{repo}"
    return f"{base}/{path}" if path else base


def iter_source_files(source_dir: Path) -> list[Path]:
    """Collect publishable files under source_dir, applying skip rules."""
    files: list[Path] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(source_dir).parts):
            continue
        if path.suffix in SKIP_FILE_SUFFIXES:
            continue
        files.append(path)
    return files


def create_blob(session: requests.Session, owner: str, repo: str, file_path: Path) -> str:
    """Upload one file_master as a Git blob; return its SHA."""
    content = base64.b64encode(file_path.read_bytes()).decode("ascii")
    response = session.post(
        api_url(owner, repo, "git/blobs"),
        json={"content": content, "encoding": "base64"},
    )
    response.raise_for_status()
    return response.json()["sha"]


def build_tree_entries(source_dir: Path, session: requests.Session, owner: str, repo: str) -> list[dict]:
    """Create blob SHAs and tree entries for every file_master under source_dir."""
    entries: list[dict] = []
    for file_path in iter_source_files(source_dir):
        rel_path = file_path.relative_to(source_dir).as_posix()
        blob_sha = create_blob(session, owner, repo, file_path)
        entries.append({"path": rel_path, "mode": "100644", "type": "blob", "sha": blob_sha})
    if not entries:
        raise RuntimeError(f"No publishable files found under {source_dir}")
    return entries


def get_branch_ref(session: requests.Session, owner: str, repo: str, branch: str) -> dict | None:
    """Return branch ref JSON when the branch exists, else None."""
    response = session.get(api_url(owner, repo, f"git/ref/heads/{branch}"))
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def create_tree(
    session: requests.Session,
    owner: str,
    repo: str,
    entries: list[dict],
    base_tree: str | None,
) -> str:
    """Create a new git tree on GitHub; return tree SHA."""
    payload: dict = {"tree": entries}
    if base_tree:
        payload["base_tree"] = base_tree
    response = session.post(api_url(owner, repo, "git/trees"), json=payload)
    response.raise_for_status()
    return response.json()["sha"]


def create_commit(
    session: requests.Session,
    owner: str,
    repo: str,
    tree_sha: str,
    message: str,
    parent_sha: str | None,
) -> str:
    """Create a commit pointing at tree_sha; return commit SHA."""
    payload: dict = {"message": message, "tree": tree_sha, "parents": []}
    if parent_sha:
        payload["parents"] = [parent_sha]
    response = session.post(api_url(owner, repo, "git/commits"), json=payload)
    response.raise_for_status()
    return response.json()["sha"]


def update_or_create_ref(
    session: requests.Session,
    owner: str,
    repo: str,
    branch: str,
    commit_sha: str,
    existing_ref: dict | None,
) -> None:
    """Point branch ref at commit_sha (PATCH existing ref or POST new ref)."""
    if existing_ref:
        response = session.patch(
            api_url(owner, repo, f"git/refs/heads/{branch}"),
            json={"sha": commit_sha, "force": True},
        )
    else:
        response = session.post(
            api_url(owner, repo, "git/refs"),
            json={"ref": f"refs/heads/{branch}", "sha": commit_sha},
        )
    response.raise_for_status()


def publish_executable(
    source_dir: Path | None = None,
    commit_message: str | None = None,
) -> str:
    """
    Push executable source to the private GitHub repo using the Git Data API.

    Required admin/.env vars:
      GITHUB_TOKEN, GITHUB_OWNER, GITHUB_EXECUTABLE_REPO
    Optional:
      GITHUB_BRANCH, EXECUTABLE_SOURCE_DIR, EXECUTABLE_COMMIT_MESSAGE
    """
    load_env()
    token = require_env("GITHUB_TOKEN")
    owner = require_env("GITHUB_OWNER")
    repo = require_env("GITHUB_EXECUTABLE_REPO")
    branch = os.getenv("GITHUB_BRANCH", "main").strip() or "main"

    rel_source = os.getenv("EXECUTABLE_SOURCE_DIR", "").strip()
    resolved_source = (ADMIN_DIR / rel_source).resolve() if rel_source else (source_dir or DEFAULT_EXECUTABLE_DIR)
    if not resolved_source.is_dir():
        raise RuntimeError(f"Executable source directory not found: {resolved_source}")

    message = commit_message or os.getenv("EXECUTABLE_COMMIT_MESSAGE", "Publish executable via GitHub API")

    session = requests.Session()
    session.headers.update(github_headers(token))

    ref = get_branch_ref(session, owner, repo, branch)
    parent_sha = ref["object"]["sha"] if ref else None
    base_tree = None
    if parent_sha:
        commit_resp = session.get(api_url(owner, repo, f"git/commits/{parent_sha}"))
        commit_resp.raise_for_status()
        base_tree = commit_resp.json()["tree"]["sha"]

    entries = build_tree_entries(resolved_source, session, owner, repo)
    tree_sha = create_tree(session, owner, repo, entries, base_tree)
    commit_sha = create_commit(session, owner, repo, tree_sha, message, parent_sha)
    update_or_create_ref(session, owner, repo, branch, commit_sha, ref)

    print(f"Published {len(entries)} file_master(s) to {owner}/{repo}@{branch} ({commit_sha[:7]})")
    return commit_sha


if __name__ == "__main__":
    publish_executable()
