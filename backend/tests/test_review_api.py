"""Tests for the URL-to-review API integration without external services."""

import pytest
from app.ai_review.client import AIConfigurationError, AIProviderError
from app.github_service.client import GitHubServiceError
from app.main import app
from app.routes import review as review_route
from app.schemas.review import ReviewAnalyzeRequest, ReviewResponse
from fastapi import HTTPException
from pydantic import ValidationError


def test_analyze_endpoint_ingests_url_and_returns_frontend_shape(monkeypatch):
    payload = {"pull_request": {"owner": "acme", "repo": "widget", "number": 12}}
    review = {
        "repository": "acme/widget",
        "pull_request_title": "Improve parser",
        "pull_request_number": 12,
        "url": "https://github.com/acme/widget/pull/12",
        "findings": [
            {
                "severity": "High",
                "title": "Missing guard",
                "file": "src/parser.py",
                "line": 14,
                "text": "The changed code dereferences the value before checking it.",
                "proof": "value is accessed before the null check",
                "status": "unverified AI suggestion",
            }
        ],
        "status": "completed",
    }
    ingested_urls = []
    reviewed_payloads = []

    def fake_ingest(url):
        ingested_urls.append(url)
        return payload

    def fake_review(received_payload):
        reviewed_payloads.append(received_payload)
        return review

    monkeypatch.setattr(review_route, "ingest_pull_request", fake_ingest)
    monkeypatch.setattr(review_route, "run_review", fake_review)

    response = review_route.analyze_pull_request(
        ReviewAnalyzeRequest(url="https://github.com/acme/widget/pull/12")
    )

    assert response == review
    assert ReviewResponse.model_validate(response).model_dump(exclude_none=True) == review
    assert ingested_urls == ["https://github.com/acme/widget/pull/12"]
    assert reviewed_payloads == [payload]


def test_analyze_endpoint_maps_invalid_pull_request_url_to_422(monkeypatch):
    def reject_url(_url):
        raise ValueError("Only GitHub pull request URLs are supported.")

    monkeypatch.setattr(review_route, "ingest_pull_request", reject_url)

    with pytest.raises(HTTPException) as error:
        review_route.analyze_pull_request(ReviewAnalyzeRequest(url="not-a-pr"))

    assert error.value.status_code == 422
    assert "pull request URLs" in error.value.detail


def test_analyze_endpoint_maps_github_errors(monkeypatch):
    def github_failure(_url):
        raise GitHubServiceError("The pull request was not found.", status_code=404)

    monkeypatch.setattr(review_route, "ingest_pull_request", github_failure)

    with pytest.raises(HTTPException) as error:
        review_route.analyze_pull_request(
            ReviewAnalyzeRequest(url="https://github.com/acme/widget/pull/12")
        )

    assert error.value.status_code == 404
    assert error.value.detail == "The pull request was not found."


@pytest.mark.parametrize(
    ("ai_error", "expected_status", "expected_detail"),
    [
        (AIConfigurationError("missing key"), 503, "AI review is not configured. Set AI_API_KEY and AI_MODEL."),
        (AIProviderError("provider unavailable"), 502, "provider unavailable"),
    ],
)
def test_analyze_endpoint_maps_ai_errors(
    monkeypatch, ai_error, expected_status, expected_detail
):
    monkeypatch.setattr(
        review_route,
        "ingest_pull_request",
        lambda _url: {"pull_request": {"owner": "acme"}},
    )

    def fail_review(_payload):
        raise ai_error

    monkeypatch.setattr(review_route, "run_review", fail_review)

    with pytest.raises(HTTPException) as http_error:
        review_route.analyze_pull_request(
            ReviewAnalyzeRequest(url="https://github.com/acme/widget/pull/12")
        )

    assert http_error.value.status_code == expected_status
    assert http_error.value.detail == expected_detail


def test_analyze_endpoint_validates_request_and_keeps_health_route():
    with pytest.raises(ValidationError):
        ReviewAnalyzeRequest(url="")

    paths = app.openapi()["paths"]
    assert "/api/reviews/analyze" in paths
    assert "/health" in paths
