"""Run executable and project publishers in sequence."""

from publish_executable import publish_executable
from publish_project import publish_project


def main() -> None:
    """Publish executable via GitHub API, then push full project via git."""
    print("=== publish_executable ===")
    publish_executable()
    print("=== publish_project ===")
    publish_project()
    print("=== done ===")


if __name__ == "__main__":
    main()
