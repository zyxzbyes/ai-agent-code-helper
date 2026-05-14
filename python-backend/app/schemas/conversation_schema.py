from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=100)


class ConversationOut(BaseModel):
    id: int
    title: str
    memoryId: int
    createdAt: datetime
    updatedAt: datetime


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    createdAt: datetime
