import httpx
import pytest
from app.github_service.client import GitHubClient, GitHubServiceError
from app.github_service.files import fetch_pull_request_files
from app.github_service.parser import parse_pull_request_url
from app.github_service.pull_requests import ingest_pull_request


def sample_pr_response():
    return {
        "number": 12,
        "title": "Improve parser",
        "body": "Handle edge cases",
        "state": "open",
        "html_url": "https://github.com/acme/widget/pull/12",
        "user": {"login": "contributor"},
        "base": {"ref": "main", "sha": "base-sha"},
        "head": {"ref": "fix/parser", "sha": "head-sha"},
        "changed_files": 1,
    }


def sample_file_response():
    return {
        "filename": "src/parser.py",
        "previous_filename": None,
        "status": "modified",
        "additions": 2,
        "deletions": 1,
        "changes": 3,
        "sha": "file-sha",
        "patch": "@@ -1,2 +1,3 @@\n+return True",
    }


def test_parse_pull_request_url_accepts_github_tabs():
    coords = parse_pull_request_url("https://github.com/acme/widget/pull/12/files")

    assert coords.owner == "acme"
    assert coords.repo == "widget"
    assert coords.number == 12


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/acme/widget/pull/12",
        "https://github.com/acme/widget/issues/12",
        "https://evil.example/acme/widget/pull/12",
        "https://github.com/acme/widget/pull/0",
        "https://user@github.com/acme/widget/pull/12",
    ],
)
def test_parse_pull_request_url_rejects_non_pr_or_unsafe_urls(url):
    with pytest.raises(ValueError):
        parse_pull_request_url(url)


def test_ingest_pull_request_builds_agreed_payload():
    def handler(request):
        assert request.headers["Accept"] == "application/vnd.github+json"
        if request.url.path.endswith("/pulls/12"):
            return httpx.Response(200, json=sample_pr_response())
        if request.url.path.endswith("/pulls/12/files"):
            assert request.url.params["per_page"] == "100"
            assert request.url.params["page"] == "1"
            return httpx.Response(200, json=[sample_file_response()])
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        payload = ingest_pull_request(
            "https://github.com/acme/widget/pull/12",
            client=GitHubClient(http_client=http_client, token="test-token"),
        )

    assert payload["pull_request"] == {
        "owner": "acme",
        "repo": "widget",
        "number": 12,
        "title": "Improve parser",
        "body": "Handle edge cases",
        "state": "open",
        "html_url": "https://github.com/acme/widget/pull/12",
        "author": "contributor",
        "base_ref": "main",
        "base_sha": "base-sha",
        "head_ref": "fix/parser",
        "head_sha": "head-sha",
        "changed_files": 1,
    }
    assert payload["files"] == [
        {
            **sample_file_response(),
            "source_content": None,
            "content_unavailable_reason": None,
        }
    ]
    assert payload["files_truncated"] is False


def test_ingest_marks_file_list_truncated_at_page_limit():
    class FullPageClient:
        def get_json(self, path, *, params):
            assert path.endswith("/pulls/12/files")
            return [sample_file_response()] * 100

    files, truncated = fetch_pull_request_files(
        FullPageClient(), "acme", "widget", 12, max_pages=1
    )

    assert len(files) == 100
    assert truncated is True


def test_github_404_is_reported_without_leaking_request_details():
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(404))
    ) as http_client:
        client = GitHubClient(http_client=http_client, token="secret-token")

        with pytest.raises(GitHubServiceError, match="not found") as error:
            client.get_json("/repos/acme/widget/pulls/12")

    assert error.value.status_code == 404
    assert "secret-token" not in str(error.value)


def test_malformed_pull_request_response_is_an_upstream_error():
    class MalformedResponseClient:
        def get_json(self, _path, *, params=None):
            return {}

    with pytest.raises(GitHubServiceError, match="malformed") as error:
        ingest_pull_request(
            "https://github.com/acme/widget/pull/12",
            client=MalformedResponseClient(),
        )

    assert error.value.status_code == 502
