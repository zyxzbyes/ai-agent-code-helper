from datetime import datetime

from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuthData(BaseModel):
    token: str
    user: UserOut
