from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.db.models import User
from app.guardrails.input_guardrail import check_user_input
from app.schemas.common import success_response


router = APIRouter(prefix="/api/guardrails", tags=["guardrails"])


class GuardrailCheckRequest(BaseModel):
    message: str = Field(default="")


@router.post("/check")
def check_guardrail(
    payload: GuardrailCheckRequest,
    current_user: User = Depends(get_current_user),
):
    result = check_user_input(payload.message)
    return success_response(
        data={
            "allowed": result.allowed,
            "reason": result.reason,
            "matched_terms": result.matched_terms,
        },
        message="success",
    )
