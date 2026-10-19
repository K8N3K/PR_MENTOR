"""Fetch every page of changed files for a GitHub pull request."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.github_service.client import GitHubClient, GitHubServiceError

FILES_PER_PAGE = 100
MAX_FILE_PAGES = 10


def fetch_pull_request_files(
    client: GitHubClient,
    owner: str,
    repo: str,
    number: int,
    *,
    max_pages: int = MAX_FILE_PAGES,
) -> tuple[list[Mapping[str, Any]], bool]:
    """Return changed-file records and whether the safety page limit truncated them."""
    if max_pages < 1:
        raise ValueError("max_pages must be at least one.")

    files: list[Mapping[str, Any]] = []
    for page in range(1, max_pages + 1):
        data = client.get_json(
            f"/repos/{owner}/{repo}/pulls/{number}/files",
            params={"per_page": FILES_PER_PAGE, "page": page},
        )
        if not isinstance(data, list) or any(not isinstance(item, Mapping) for item in data):
            raise GitHubServiceError("GitHub returned malformed changed-file data.")

        files.extend(data)
        if len(data) < FILES_PER_PAGE:
            return files, False

    return files, True
