"""Review API routes."""

from app.ai_review.client import AIConfigurationError, AIProviderError
from app.github_service.client import GitHubServiceError
from app.github_service.pull_requests import ingest_pull_request
from app.schemas.review import ReviewAnalyzeRequest, ReviewResponse
from app.services.review_orchestrator import run_review
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("/analyze", response_model=ReviewResponse)
def analyze_pull_request(request: ReviewAnalyzeRequest) -> ReviewResponse:
    """Analyze a public GitHub PR URL and return the frontend response shape."""
    try:
        payload = ingest_pull_request(request.url)
        return run_review(payload)
    except GitHubServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except AIConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="AI review is not configured. Set AI_API_KEY and AI_MODEL.",
        ) from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
