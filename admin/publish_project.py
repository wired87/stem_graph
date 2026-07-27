"""Commit and push the full CNVMaster project (including auth + .env) to a private GitHub repo."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import dotenv

# Admin layout: admin/ sits at project root
ADMIN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ADMIN_DIR.parent

# Paths force-included even when ignored locally (secrets go only to the private remote)
FORCE_ADD_PATHS = [
    ADMIN_DIR / ".env",
    ADMIN_DIR / "auth",
    PROJECT_ROOT / ".env",
]


def load_env() -> None:
    """Load admin/.env for GitHub and git identity settings."""
    dotenv.load_dotenv(ADMIN_DIR / ".env")


def require_env(name: str) -> str:
    """Return a required env var or raise with a clear message."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name} (set it in admin/.env)")
    return value


def run_git(args: list[str], cwd: Path) -> str:
    """Run a git command in cwd; raise on failure and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def ensure_git_repo() -> None:
    """Initialize git in project root when no repository exists yet."""
    if not (PROJECT_ROOT / ".git").exists():
        run_git(["init"], PROJECT_ROOT)
        run_git(["branch", "-M", os.getenv("GITHUB_BRANCH", "main")], PROJECT_ROOT)


def configure_git_identity() -> None:
    """Set local git user.name and user.email from admin/.env."""
    name = require_env("GIT_USER_NAME")
    email = require_env("GIT_USER_EMAIL")
    run_git(["config", "user.name", name], PROJECT_ROOT)
    run_git(["config", "user.email", email], PROJECT_ROOT)


def ensure_remote(owner: str, repo: str, token: str) -> None:
    """Add or update origin remote with token-authenticated HTTPS URL."""
    remote_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    remotes = run_git(["remote"], PROJECT_ROOT)
    if "origin" in remotes.splitlines():
        run_git(["remote", "set-url", "origin", remote_url], PROJECT_ROOT)
    else:
        run_git(["remote", "add", "origin", remote_url], PROJECT_ROOT)


def force_add_secret_paths() -> None:
    """Force-add auth credentials and .env files that local .gitignore would skip."""
    for path in FORCE_ADD_PATHS:
        if path.exists():
            run_git(["add", "-f", str(path.relative_to(PROJECT_ROOT))], PROJECT_ROOT)


def publish_project(commit_message: str | None = None) -> str:
    """
    Stage, commit, and push the full project to a private GitHub repo.

    Required admin/.env vars:
      GITHUB_TOKEN, GITHUB_OWNER, GITHUB_PROJECT_REPO, GIT_USER_NAME, GIT_USER_EMAIL
    Optional:
      GITHUB_BRANCH, PROJECT_COMMIT_MESSAGE
    """
    load_env()
    token = require_env("GITHUB_TOKEN")
    owner = require_env("GITHUB_OWNER")
    repo = require_env("GITHUB_PROJECT_REPO")
    branch = os.getenv("GITHUB_BRANCH", "main").strip() or "main"
    message = commit_message or os.getenv("PROJECT_COMMIT_MESSAGE", "Publish CNVMaster project with auth and .env")

    ensure_git_repo()
    configure_git_identity()
    ensure_remote(owner, repo, token)

    # Stage project files, then force-include secrets for the private remote
    run_git(["add", "-A"], PROJECT_ROOT)
    force_add_secret_paths()

    status = run_git(["status", "--porcelain"], PROJECT_ROOT)
    if not status:
        print("No changes to publish.")
        return run_git(["rev-parse", "HEAD"], PROJECT_ROOT)

    run_git(["commit", "-m", message], PROJECT_ROOT)

    # Push branch; set upstream on first push
    try:
        run_git(["push", "-u", "origin", branch], PROJECT_ROOT)
    except subprocess.CalledProcessError:
        run_git(["push", "-u", "origin", branch, "--force"], PROJECT_ROOT)

    commit_sha = run_git(["rev-parse", "HEAD"], PROJECT_ROOT)
    print(f"Published project to {owner}/{repo}@{branch} ({commit_sha[:7]})")
    return commit_sha


if __name__ == "__main__":
    publish_project()
