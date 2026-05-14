from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.db.models import User
from app.schemas.common import success_response
from app.tools.interview_question import search_interview_questions
from app.tools.web_search import search_web, search_web_with_debug


router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("/interview/search")
def search_interview(
    keyword: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
):
    questions = search_interview_questions(keyword)
    return success_response(
        data=[{"title": item.title, "url": item.url} for item in questions],
        message="success",
    )


@router.get("/web/search")
def search_web_api(
    query: str = Query(..., min_length=1),
    debug: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    search_response = search_web_with_debug(query) if debug else None
    results = search_response.results if search_response else search_web(query)
    result_data = [
            {
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
                "source_type": item.source_type,
            }
            for item in results
        ]

    if debug and search_response is not None:
        return success_response(
            data={
                "results": result_data,
                "fallback_reason": search_response.debug.fallback_reason,
                "mcp_status": search_response.debug.as_dict(),
            },
            message="success",
        )

    return success_response(
        data=result_data,
        message="success",
    )
