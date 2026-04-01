from pydantic import BaseModel
from datetime import datetime
from app.models import QuestionType


class SessionCreate(BaseModel):
    title: str
    admin_password: str


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionCreate(BaseModel):
    type: QuestionType
    title: str
    options: list[str] | None = None  # For multiple choice


class QuestionResponse(BaseModel):
    id: str
    type: QuestionType
    title: str
    options: list[str] | None = None
    is_active: bool
    display_order: int

    class Config:
        from_attributes = True


class ResponseCreate(BaseModel):
    question_id: str
    value: str


class ResponseData(BaseModel):
    id: str
    value: str
    created_at: datetime

    class Config:
        from_attributes = True


class WebSocketMessage(BaseModel):
    type: str
    data: dict
