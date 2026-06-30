from typing import Annotated
import os
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_admin_user, get_rag_engine, get_settings_dep
from app.models.user import User
from app.models.document import Document, DocumentStatus
from app.core.rag import RAGEngine
from app.config import Settings
from app.schemas.document import DocumentResponse, DocumentListResponse

router = APIRouter(prefix="/admin/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {"txt", "md", "html", "pdf", "docx", "xlsx"}


def get_file_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    documents = list(result.scalars().all())
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=len(documents)
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(document)


@router.post("", response_model=DocumentResponse)
async def upload_document(
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    rag: Annotated[RAGEngine, Depends(get_rag_engine)],
    file: UploadFile = File(...)
):
    ext = get_file_extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
        )

    # Save file
    file_id = str(uuid4())
    filename = f"{file_id}.{ext}"
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename

    with open(file_path, "wb") as f:
        f.write(content)

    # Create document record
    document = Document(
        filename=filename,
        original_name=file.filename or "unknown",
        file_type=ext,
        file_size=len(content),
        uploaded_by=user.id,
        status=DocumentStatus.PROCESSING
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Process document
    try:
        chunk_count = rag.add_document(str(file_path), document.id)
        document.chunk_count = chunk_count
        document.status = DocumentStatus.READY
    except Exception as e:
        document.status = DocumentStatus.ERROR
        document.error_message = str(e)[:500]

    await db.commit()
    await db.refresh(document)

    return DocumentResponse.model_validate(document)


@router.put("/{doc_id}", response_model=DocumentResponse)
async def replace_document(
    doc_id: str,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    rag: Annotated[RAGEngine, Depends(get_rag_engine)],
    file: UploadFile = File(...)
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    ext = get_file_extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")

    content = await file.read()

    # Delete old chunks from Qdrant
    rag.delete_document(doc_id)

    # Delete old file
    upload_dir = Path(settings.UPLOAD_DIR)
    old_file_path = upload_dir / document.filename
    if old_file_path.exists():
        os.remove(old_file_path)

    # Save new file
    new_filename = f"{doc_id}.{ext}"
    new_file_path = upload_dir / new_filename
    with open(new_file_path, "wb") as f:
        f.write(content)

    # Update document
    document.filename = new_filename
    document.original_name = file.filename or "unknown"
    document.file_type = ext
    document.file_size = len(content)
    document.status = DocumentStatus.PROCESSING
    document.error_message = None

    await db.commit()

    # Re-index
    try:
        chunk_count = rag.add_document(str(new_file_path), doc_id)
        document.chunk_count = chunk_count
        document.status = DocumentStatus.READY
    except Exception as e:
        document.status = DocumentStatus.ERROR
        document.error_message = str(e)[:500]

    await db.commit()
    await db.refresh(document)

    return DocumentResponse.model_validate(document)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    rag: Annotated[RAGEngine, Depends(get_rag_engine)]
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from Qdrant
    rag.delete_document(doc_id)

    # Delete file
    file_path = Path(settings.UPLOAD_DIR) / document.filename
    if file_path.exists():
        os.remove(file_path)

    # Delete from database
    await db.delete(document)
    await db.commit()

    return {"message": "Document deleted successfully"}
