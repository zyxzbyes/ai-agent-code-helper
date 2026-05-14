from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.db.models import User
from app.rag.retriever import retrieve
from app.schemas.common import success_response


router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.get("/search")
def search_rag(
    query: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
):
    results = retrieve(query)
    return success_response(
        data=[
            {
                "source": item.source,
                "score": item.score,
                "content_preview": item.content[:300],
            }
            for item in results
        ],
        message="success",
    )
