from datetime import datetime
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ChatSource(BaseModel):
    document: str
    page: int | None
    chunk: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    confidence: float
    session_id: str


class ChatHistoryItem(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryItem]
    total: int
    limit: int
    offset: int
    has_more: bool


class DeleteHistoryResponse(BaseModel):
    deleted_count: int
