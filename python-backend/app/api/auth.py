from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.auth_schema import AuthRequest
from app.schemas.common import success_response
from app.services.user_service import authenticate_user, build_auth_data, create_user


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(payload: AuthRequest, db: Session = Depends(get_db)):
    user = create_user(db=db, username=payload.username, password=payload.password)
    return success_response(data=build_auth_data(user), message="success")


@router.post("/login")
def login(payload: AuthRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db=db, username=payload.username, password=payload.password)
    return success_response(data=build_auth_data(user), message="success")


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return success_response(
        data={
            "id": current_user.id,
            "username": current_user.username,
        },
        message="success",
    )


@router.post("/logout")
def logout():
    return success_response(data=True, message="success")
