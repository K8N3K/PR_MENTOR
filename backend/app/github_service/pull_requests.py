"""Build the agreed ingestion payload for a public GitHub pull request."""

from __future__ import annotations

from typing import Any

from app.github_service.client import GitHubClient
from app.github_service.files import fetch_pull_request_files
from app.github_service.parser import (
    parse_pull_request_file,
    parse_pull_request_metadata,
    parse_pull_request_url,
)


def ingest_pull_request(
    url: str,
    *,
    client: GitHubClient | None = None,
    max_file_pages: int = 10,
) -> dict[str, Any]:
    """Fetch PR metadata and changed-file patches without checking out code."""
    coordinates = parse_pull_request_url(url)
    active_client = client or GitHubClient()
    api_prefix = f"/repos/{coordinates.owner}/{coordinates.repo}"

    pull_request_data = active_client.get_json(
        f"{api_prefix}/pulls/{coordinates.number}"
    )
    metadata = parse_pull_request_metadata(pull_request_data, coordinates)
    file_data, files_truncated = fetch_pull_request_files(
        active_client,
        coordinates.owner,
        coordinates.repo,
        coordinates.number,
        max_pages=max_file_pages,
    )

    return {
        "pull_request": metadata,
        "files": [parse_pull_request_file(file) for file in file_data],
        "files_truncated": files_truncated,
    }
