from pydantic import BaseModel
from datetime import datetime
from app.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_name: str
    file_type: str
    file_size: int
    chunk_count: int
    status: DocumentStatus
    error_message: str | None
    uploaded_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
