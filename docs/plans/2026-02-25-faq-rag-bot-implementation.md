# FAQ RAG Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a RAG-based FAQ bot with FastAPI backend, React admin panel, and Docker deployment.

**Architecture:** Monolith with FastAPI backend, LlamaIndex for RAG, Qdrant for vectors, PostgreSQL for metadata, Redis for sessions. React admin panel using FSD architecture.

**Tech Stack:** Python 3.11, FastAPI, LlamaIndex, Qdrant, PostgreSQL, Redis, React, TypeScript, Chakra UI, React Query

---

## Phase 1: Infrastructure Setup

### Task 1.1: Project Structure

**Files:**
- Create: `backend/`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Move: `react-claude-tempalte/` → `frontend/`

**Step 1: Create backend directory structure**

```bash
mkdir -p backend/app/{api/v1,core/{rag,llm},models,schemas,services}
mkdir -p backend/tests
mkdir -p backend/alembic/versions
```

**Step 2: Move React template to frontend**

```bash
mv react-claude-tempalte frontend
```

**Step 3: Create docker-compose.yml**

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://faq_user:faq_pass@postgres:5432/faq_bot
      - REDIS_URL=redis://redis:6379
      - QDRANT_URL=http://qdrant:6333
      - JWT_SECRET=${JWT_SECRET}
      - LLM_PROVIDER=${LLM_PROVIDER:-openai}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
      qdrant:
        condition: service_started
    volumes:
      - ./backend:/app
      - uploads:/app/uploads

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      - backend

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=faq_user
      - POSTGRES_PASSWORD=faq_pass
      - POSTGRES_DB=faq_bot
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U faq_user -d faq_bot"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  uploads:
```

**Step 4: Create .env.example**

```bash
# LLM Configuration
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
OLLAMA_URL=http://localhost:11434

# Embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small

# RAG Settings
CHUNK_SIZE=512
CHUNK_OVERLAP=50
SIMILARITY_THRESHOLD=0.7
TOP_K_RESULTS=5

# JWT
JWT_SECRET=your-super-secret-key-change-in-production
JWT_EXPIRE_MINUTES=60

# Database (for local development without Docker)
DATABASE_URL=postgresql://faq_user:faq_pass@localhost:5432/faq_bot
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
```

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add project structure and docker-compose"
```

---

### Task 1.2: Backend Dockerfile and Dependencies

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`

**Step 1: Create backend Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

**Step 2: Create pyproject.toml**

```toml
[project]
name = "faq-rag-bot"
version = "0.1.0"
description = "RAG-based FAQ Bot"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "sqlalchemy>=2.0.25",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "redis>=5.0.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.6",
    "llama-index>=0.10.0",
    "llama-index-vector-stores-qdrant>=0.1.0",
    "llama-index-llms-openai>=0.1.0",
    "llama-index-llms-anthropic>=0.1.0",
    "llama-index-llms-ollama>=0.1.0",
    "llama-index-embeddings-openai>=0.1.0",
    "qdrant-client>=1.7.0",
    "pypdf>=3.17.0",
    "python-docx>=1.1.0",
    "openpyxl>=3.1.2",
    "markdown>=3.5.0",
    "beautifulsoup4>=4.12.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.26.0",
    "ruff>=0.1.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Step 3: Create app/__init__.py**

```python
# FAQ RAG Bot Backend
```

**Step 4: Commit**

```bash
git add backend/
git commit -m "feat: add backend Dockerfile and dependencies"
```

---

## Phase 2: Backend Configuration

### Task 2.1: Configuration Module

**Files:**
- Create: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_config.py
import pytest
from app.config import Settings


def test_settings_loads_defaults():
    settings = Settings(
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost",
        QDRANT_URL="http://localhost:6333",
        JWT_SECRET="test-secret",
    )
    assert settings.LLM_PROVIDER == "openai"
    assert settings.CHUNK_SIZE == 512
    assert settings.SIMILARITY_THRESHOLD == 0.7
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_config.py -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'app.config'"

**Step 3: Write minimal implementation**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    REDIS_URL: str
    QDRANT_URL: str

    # JWT
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 60

    # LLM
    LLM_PROVIDER: Literal["openai", "anthropic", "ollama"] = "openai"
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_URL: str = "http://localhost:11434"

    # Embeddings
    EMBEDDING_PROVIDER: Literal["openai", "local"] = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # RAG
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    SIMILARITY_THRESHOLD: float = 0.7
    TOP_K_RESULTS: int = 5

    # Upload
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 50

    class Config:
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()
```

**Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_config.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat: add configuration module"
```

---

### Task 2.2: Database Models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/document.py`
- Create: `backend/app/models/settings.py`

**Step 1: Create base model**

```python
# backend/app/models/base.py
from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UUIDMixin:
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
```

**Step 2: Create user model**

```python
# backend/app/models/user.py
from sqlalchemy import String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum
from .base import Base, UUIDMixin, TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole), default=UserRole.USER
    )
    is_active: Mapped[bool] = mapped_column(default=True)
```

**Step 3: Create document model**

```python
# backend/app/models/document.py
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from .base import Base, UUIDMixin, TimestampMixin


class DocumentStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class Document(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "documents"

    filename: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(50))
    file_size: Mapped[int] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus), default=DocumentStatus.PROCESSING
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))

    uploader = relationship("User", backref="documents")
```

**Step 4: Create settings model**

```python
# backend/app/models/settings.py
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, UUIDMixin, TimestampMixin


class SystemSettings(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
```

**Step 5: Create models __init__.py**

```python
# backend/app/models/__init__.py
from .base import Base
from .user import User, UserRole
from .document import Document, DocumentStatus
from .settings import SystemSettings

__all__ = [
    "Base",
    "User",
    "UserRole",
    "Document",
    "DocumentStatus",
    "SystemSettings",
]
```

**Step 6: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add database models"
```

---

### Task 2.3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/schemas/document.py`
- Create: `backend/app/schemas/chat.py`
- Create: `backend/app/schemas/auth.py`

**Step 1: Create user schemas**

```python
# backend/app/schemas/user.py
from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    id: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

**Step 2: Create document schemas**

```python
# backend/app/schemas/document.py
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
```

**Step 3: Create chat schemas**

```python
# backend/app/schemas/chat.py
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


class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatHistoryMessage]
```

**Step 4: Create auth schemas**

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
```

**Step 5: Create schemas __init__.py**

```python
# backend/app/schemas/__init__.py
from .user import UserBase, UserCreate, UserUpdate, UserResponse
from .document import DocumentResponse, DocumentListResponse
from .chat import ChatRequest, ChatResponse, ChatSource, ChatHistoryResponse
from .auth import LoginRequest, TokenResponse, RefreshRequest

__all__ = [
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "DocumentResponse",
    "DocumentListResponse",
    "ChatRequest",
    "ChatResponse",
    "ChatSource",
    "ChatHistoryResponse",
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
]
```

**Step 6: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat: add Pydantic schemas"
```

---

## Phase 3: Authentication

### Task 3.1: Auth Service

**Files:**
- Create: `backend/app/services/auth_service.py`
- Test: `backend/tests/test_auth_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_auth_service.py
import pytest
from app.services.auth_service import AuthService


def test_password_hashing():
    auth = AuthService(jwt_secret="test", jwt_expire_minutes=60)
    password = "mysecretpassword"
    hashed = auth.hash_password(password)

    assert hashed != password
    assert auth.verify_password(password, hashed) is True
    assert auth.verify_password("wrongpassword", hashed) is False


def test_jwt_token_creation():
    auth = AuthService(jwt_secret="test-secret", jwt_expire_minutes=60)
    token = auth.create_access_token(user_id="user-123", role="admin")

    assert token is not None
    payload = auth.decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_auth_service.py -v
```
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/services/auth_service.py
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext


class AuthService:
    def __init__(self, jwt_secret: str, jwt_expire_minutes: int = 60):
        self.jwt_secret = jwt_secret
        self.jwt_expire_minutes = jwt_expire_minutes
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.algorithm = "HS256"

    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(
        self,
        user_id: str,
        role: str,
        expires_delta: timedelta | None = None
    ) -> str:
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=self.jwt_expire_minutes)
        )
        to_encode = {
            "sub": user_id,
            "role": role,
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(to_encode, self.jwt_secret, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
        to_encode = {
            "sub": user_id,
            "exp": expire,
            "type": "refresh"
        }
        return jwt.encode(to_encode, self.jwt_secret, algorithm=self.algorithm)

    def decode_token(self, token: str) -> dict | None:
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None
```

**Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_auth_service.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/auth_service.py backend/tests/test_auth_service.py
git commit -m "feat: add authentication service"
```

---

## Phase 4: RAG Core

### Task 4.1: LLM Adapter Interface

**Files:**
- Create: `backend/app/core/llm/__init__.py`
- Create: `backend/app/core/llm/base.py`
- Create: `backend/app/core/llm/openai.py`
- Create: `backend/app/core/llm/factory.py`

**Step 1: Create base interface**

```python
# backend/app/core/llm/base.py
from abc import ABC, abstractmethod
from llama_index.core.llms import LLM


class BaseLLMAdapter(ABC):
    @abstractmethod
    def get_llm(self) -> LLM:
        """Return LlamaIndex-compatible LLM instance."""
        pass

    @abstractmethod
    def get_embedding_model(self):
        """Return embedding model for vectorization."""
        pass
```

**Step 2: Create OpenAI adapter**

```python
# backend/app/core/llm/openai.py
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from .base import BaseLLMAdapter


class OpenAIAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def get_llm(self):
        return OpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=0.1
        )

    def get_embedding_model(self):
        return OpenAIEmbedding(
            api_key=self.api_key,
            model="text-embedding-3-small"
        )
```

**Step 3: Create factory**

```python
# backend/app/core/llm/factory.py
from app.config import Settings
from .base import BaseLLMAdapter
from .openai import OpenAIAdapter


def create_llm_adapter(settings: Settings) -> BaseLLMAdapter:
    if settings.LLM_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        return OpenAIAdapter(api_key=settings.OPENAI_API_KEY)

    # TODO: Add anthropic and ollama adapters
    raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")
```

**Step 4: Create __init__.py**

```python
# backend/app/core/llm/__init__.py
from .base import BaseLLMAdapter
from .openai import OpenAIAdapter
from .factory import create_llm_adapter

__all__ = ["BaseLLMAdapter", "OpenAIAdapter", "create_llm_adapter"]
```

**Step 5: Commit**

```bash
git add backend/app/core/llm/
git commit -m "feat: add LLM adapter abstraction"
```

---

### Task 4.2: Document Loader

**Files:**
- Create: `backend/app/core/rag/__init__.py`
- Create: `backend/app/core/rag/loader.py`
- Test: `backend/tests/test_loader.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_loader.py
import pytest
import tempfile
import os
from app.core.rag.loader import DocumentLoader


def test_load_txt_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is test content for the RAG bot.")
        f.flush()

        loader = DocumentLoader()
        docs = loader.load_file(f.name)

        assert len(docs) > 0
        assert "test content" in docs[0].text.lower()

        os.unlink(f.name)


def test_load_markdown_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Header\n\nThis is markdown content.")
        f.flush()

        loader = DocumentLoader()
        docs = loader.load_file(f.name)

        assert len(docs) > 0
        os.unlink(f.name)
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_loader.py -v
```
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/core/rag/loader.py
from pathlib import Path
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from pypdf import PdfReader
from docx import Document as DocxDocument
from openpyxl import load_workbook
from bs4 import BeautifulSoup
import markdown


class DocumentLoader:
    SUPPORTED_EXTENSIONS = {'.txt', '.md', '.html', '.pdf', '.docx', '.xlsx'}

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def load_file(self, file_path: str) -> list[Document]:
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {extension}")

        text = self._extract_text(path, extension)

        doc = Document(
            text=text,
            metadata={
                "filename": path.name,
                "file_type": extension[1:],
            }
        )

        return [doc]

    def _extract_text(self, path: Path, extension: str) -> str:
        if extension == '.txt':
            return path.read_text(encoding='utf-8')

        elif extension == '.md':
            md_text = path.read_text(encoding='utf-8')
            html = markdown.markdown(md_text)
            return BeautifulSoup(html, 'html.parser').get_text()

        elif extension == '.html':
            html = path.read_text(encoding='utf-8')
            return BeautifulSoup(html, 'html.parser').get_text()

        elif extension == '.pdf':
            return self._extract_pdf(path)

        elif extension == '.docx':
            return self._extract_docx(path)

        elif extension == '.xlsx':
            return self._extract_xlsx(path)

        return ""

    def _extract_pdf(self, path: Path) -> str:
        reader = PdfReader(str(path))
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            text_parts.append(f"[Page {i+1}]\n{page_text}")
        return "\n\n".join(text_parts)

    def _extract_docx(self, path: Path) -> str:
        doc = DocxDocument(str(path))
        return "\n\n".join(para.text for para in doc.paragraphs if para.text)

    def _extract_xlsx(self, path: Path) -> str:
        wb = load_workbook(str(path), read_only=True)
        text_parts = []
        for sheet in wb.worksheets:
            rows = []
            for row in sheet.iter_rows(values_only=True):
                row_text = " | ".join(str(cell) for cell in row if cell is not None)
                if row_text:
                    rows.append(row_text)
            if rows:
                text_parts.append(f"[Sheet: {sheet.title}]\n" + "\n".join(rows))
        return "\n\n".join(text_parts)

    def chunk_documents(self, documents: list[Document]) -> list:
        return self.splitter.get_nodes_from_documents(documents)
```

**Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_loader.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/rag/loader.py backend/tests/test_loader.py
git commit -m "feat: add document loader with multi-format support"
```

---

### Task 4.3: RAG Engine

**Files:**
- Create: `backend/app/core/rag/engine.py`
- Create: `backend/app/core/rag/retriever.py`

**Step 1: Create retriever**

```python
# backend/app/core/rag/retriever.py
from qdrant_client import QdrantClient
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex, StorageContext


class QdrantRetriever:
    COLLECTION_NAME = "documents"

    def __init__(self, qdrant_url: str, embedding_model):
        self.client = QdrantClient(url=qdrant_url)
        self.embedding_model = embedding_model
        self._ensure_collection()

    def _ensure_collection(self):
        collections = self.client.get_collections().collections
        if not any(c.name == self.COLLECTION_NAME for c in collections):
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config={
                    "size": 1536,  # OpenAI embedding size
                    "distance": "Cosine"
                }
            )

    def get_vector_store(self) -> QdrantVectorStore:
        return QdrantVectorStore(
            client=self.client,
            collection_name=self.COLLECTION_NAME
        )

    def get_index(self) -> VectorStoreIndex:
        vector_store = self.get_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        return VectorStoreIndex.from_vector_store(
            vector_store,
            embed_model=self.embedding_model,
            storage_context=storage_context
        )

    def add_documents(self, nodes: list, document_id: str):
        for node in nodes:
            node.metadata["document_id"] = document_id

        vector_store = self.get_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        VectorStoreIndex(
            nodes,
            embed_model=self.embedding_model,
            storage_context=storage_context
        )

    def delete_document(self, document_id: str):
        self.client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector={
                "filter": {
                    "must": [
                        {"key": "document_id", "match": {"value": document_id}}
                    ]
                }
            }
        )
```

**Step 2: Create RAG engine**

```python
# backend/app/core/rag/engine.py
from llama_index.core import PromptTemplate
from llama_index.core.chat_engine import CondenseQuestionChatEngine
from .retriever import QdrantRetriever
from ..llm.base import BaseLLMAdapter


SYSTEM_PROMPT = """You are a helpful assistant that answers questions based ONLY on the provided documentation.

CRITICAL RULES:
1. ONLY use information from the provided context to answer
2. If the answer is not in the context, say "I could not find this information in the documentation"
3. NEVER make up information or use your general knowledge
4. Always cite which document and section the information came from
5. Be concise and direct in your answers

Context from documentation:
{context_str}

User question: {query_str}

Answer based strictly on the context above:"""


class RAGEngine:
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        qdrant_url: str,
        similarity_threshold: float = 0.7,
        top_k: int = 5
    ):
        self.llm = llm_adapter.get_llm()
        self.embed_model = llm_adapter.get_embedding_model()
        self.retriever = QdrantRetriever(qdrant_url, self.embed_model)
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k

    def query(
        self,
        question: str,
        chat_history: list[dict] | None = None
    ) -> dict:
        index = self.retriever.get_index()

        query_engine = index.as_query_engine(
            llm=self.llm,
            similarity_top_k=self.top_k,
            text_qa_template=PromptTemplate(SYSTEM_PROMPT)
        )

        response = query_engine.query(question)

        sources = []
        max_score = 0.0

        for node in response.source_nodes:
            score = node.score or 0.0
            max_score = max(max_score, score)

            if score >= self.similarity_threshold:
                sources.append({
                    "document": node.metadata.get("filename", "Unknown"),
                    "page": node.metadata.get("page"),
                    "chunk": node.text[:200] + "..." if len(node.text) > 200 else node.text
                })

        if max_score < self.similarity_threshold:
            return {
                "answer": "I could not find relevant information in the documentation to answer this question.",
                "sources": [],
                "confidence": max_score
            }

        return {
            "answer": str(response),
            "sources": sources,
            "confidence": max_score
        }

    def add_document(self, file_path: str, document_id: str) -> int:
        from .loader import DocumentLoader

        loader = DocumentLoader()
        docs = loader.load_file(file_path)
        nodes = loader.chunk_documents(docs)

        self.retriever.add_documents(nodes, document_id)

        return len(nodes)

    def delete_document(self, document_id: str):
        self.retriever.delete_document(document_id)
```

**Step 3: Create rag __init__.py**

```python
# backend/app/core/rag/__init__.py
from .engine import RAGEngine
from .loader import DocumentLoader
from .retriever import QdrantRetriever

__all__ = ["RAGEngine", "DocumentLoader", "QdrantRetriever"]
```

**Step 4: Commit**

```bash
git add backend/app/core/rag/
git commit -m "feat: add RAG engine with Qdrant integration"
```

---

## Phase 5: API Endpoints

### Task 5.1: Database Connection and Dependencies

**Files:**
- Create: `backend/app/api/deps.py`
- Create: `backend/app/database.py`

**Step 1: Create database module**

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

**Step 2: Create dependencies**

```python
# backend/app/api/deps.py
from typing import Annotated
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from app.database import get_db
from app.config import get_settings, Settings
from app.services.auth_service import AuthService
from app.models.user import User
from app.core.rag import RAGEngine
from app.core.llm import create_llm_adapter

security = HTTPBearer()


def get_settings_dep() -> Settings:
    return get_settings()


async def get_redis(settings: Annotated[Settings, Depends(get_settings_dep)]):
    client = redis.from_url(settings.REDIS_URL)
    try:
        yield client
    finally:
        await client.close()


def get_auth_service(settings: Annotated[Settings, Depends(get_settings_dep)]) -> AuthService:
    return AuthService(
        jwt_secret=settings.JWT_SECRET,
        jwt_expire_minutes=settings.JWT_EXPIRE_MINUTES
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    payload = auth.decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return user


async def get_admin_user(
    user: Annotated[User, Depends(get_current_user)]
) -> User:
    if user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def get_rag_engine(settings: Annotated[Settings, Depends(get_settings_dep)]) -> RAGEngine:
    llm_adapter = create_llm_adapter(settings)
    return RAGEngine(
        llm_adapter=llm_adapter,
        qdrant_url=settings.QDRANT_URL,
        similarity_threshold=settings.SIMILARITY_THRESHOLD,
        top_k=settings.TOP_K_RESULTS
    )


def get_session_id(x_session_id: str | None = Header(None)) -> str | None:
    return x_session_id
```

**Step 3: Commit**

```bash
git add backend/app/database.py backend/app/api/deps.py
git commit -m "feat: add database connection and API dependencies"
```

---

### Task 5.2: Auth Endpoints

**Files:**
- Create: `backend/app/api/v1/__init__.py`
- Create: `backend/app/api/v1/auth.py`

**Step 1: Create auth router**

```python
# backend/app/api/v1/auth.py
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_auth_service
from app.services.auth_service import AuthService
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthService, Depends(get_auth_service)]
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not auth.verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    access_token = auth.create_access_token(user.id, user.role.value)
    refresh_token = auth.create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthService, Depends(get_auth_service)]
):
    payload = auth.decode_token(data.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    access_token = auth.create_access_token(user.id, user.role.value)
    refresh_token = auth.create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )
```

**Step 2: Create v1 __init__.py**

```python
# backend/app/api/v1/__init__.py
from fastapi import APIRouter
from .auth import router as auth_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
```

**Step 3: Commit**

```bash
git add backend/app/api/v1/
git commit -m "feat: add auth API endpoints"
```

---

### Task 5.3: Chat Endpoint

**Files:**
- Create: `backend/app/api/v1/chat.py`
- Create: `backend/app/core/session.py`

**Step 1: Create session manager**

```python
# backend/app/core/session.py
import json
from uuid import uuid4
import redis.asyncio as redis


class SessionManager:
    SESSION_TTL = 86400  # 24 hours

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def create_session(self, user_id: str) -> str:
        session_id = str(uuid4())
        data = {
            "user_id": user_id,
            "messages": []
        }
        await self.redis.setex(
            self._key(session_id),
            self.SESSION_TTL,
            json.dumps(data)
        )
        return session_id

    async def get_session(self, session_id: str) -> dict | None:
        data = await self.redis.get(self._key(session_id))
        if data:
            return json.loads(data)
        return None

    async def add_message(self, session_id: str, role: str, content: str):
        session = await self.get_session(session_id)
        if session:
            session["messages"].append({"role": role, "content": content})
            # Keep only last 10 messages for context
            session["messages"] = session["messages"][-10:]
            await self.redis.setex(
                self._key(session_id),
                self.SESSION_TTL,
                json.dumps(session)
            )

    async def get_history(self, session_id: str) -> list[dict]:
        session = await self.get_session(session_id)
        if session:
            return session.get("messages", [])
        return []
```

**Step 2: Create chat router**

```python
# backend/app/api/v1/chat.py
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
import redis.asyncio as redis

from app.api.deps import (
    get_current_user,
    get_rag_engine,
    get_redis,
    get_session_id
)
from app.models.user import User
from app.core.rag import RAGEngine
from app.core.session import SessionManager
from app.schemas.chat import ChatRequest, ChatResponse, ChatHistoryResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    rag: Annotated[RAGEngine, Depends(get_rag_engine)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    session_id: Annotated[str | None, Depends(get_session_id)]
):
    session_mgr = SessionManager(redis_client)

    # Create or validate session
    if session_id:
        session = await session_mgr.get_session(session_id)
        if not session:
            session_id = await session_mgr.create_session(user.id)
    else:
        session_id = await session_mgr.create_session(user.id)

    # Get chat history for context
    history = await session_mgr.get_history(session_id)

    # Query RAG engine
    result = rag.query(data.message, chat_history=history)

    # Save messages to session
    await session_mgr.add_message(session_id, "user", data.message)
    await session_mgr.add_message(session_id, "assistant", result["answer"])

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        confidence=result["confidence"],
        session_id=session_id
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)]
):
    session_mgr = SessionManager(redis_client)
    session = await session_mgr.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return ChatHistoryResponse(
        session_id=session_id,
        messages=session.get("messages", [])
    )
```

**Step 3: Update v1 __init__.py**

```python
# backend/app/api/v1/__init__.py
from fastapi import APIRouter
from .auth import router as auth_router
from .chat import router as chat_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(chat_router)
```

**Step 4: Commit**

```bash
git add backend/app/core/session.py backend/app/api/v1/chat.py backend/app/api/v1/__init__.py
git commit -m "feat: add chat API endpoint with session management"
```

---

### Task 5.4: Documents Endpoint

**Files:**
- Create: `backend/app/api/v1/documents.py`
- Create: `backend/app/services/document_service.py`

**Step 1: Create document service**

```python
# backend/app/services/document_service.py
import os
import shutil
from uuid import uuid4
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document, DocumentStatus
from app.core.rag import RAGEngine
from app.config import Settings


class DocumentService:
    def __init__(self, db: AsyncSession, settings: Settings, rag: RAGEngine):
        self.db = db
        self.settings = settings
        self.rag = rag
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def list_documents(self) -> list[Document]:
        result = await self.db.execute(
            select(Document).order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_document(self, doc_id: str) -> Document | None:
        result = await self.db.execute(
            select(Document).where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def upload_document(
        self,
        file_content: bytes,
        original_name: str,
        file_type: str,
        user_id: str
    ) -> Document:
        # Generate unique filename
        file_id = str(uuid4())
        filename = f"{file_id}.{file_type}"
        file_path = self.upload_dir / filename

        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Create document record
        document = Document(
            filename=filename,
            original_name=original_name,
            file_type=file_type,
            file_size=len(file_content),
            uploaded_by=user_id,
            status=DocumentStatus.PROCESSING
        )

        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        # Process document (index in Qdrant)
        try:
            chunk_count = self.rag.add_document(str(file_path), document.id)
            document.chunk_count = chunk_count
            document.status = DocumentStatus.READY
        except Exception as e:
            document.status = DocumentStatus.ERROR
            document.error_message = str(e)[:500]

        await self.db.commit()
        await self.db.refresh(document)

        return document

    async def replace_document(
        self,
        doc_id: str,
        file_content: bytes,
        original_name: str,
        file_type: str
    ) -> Document:
        document = await self.get_document(doc_id)
        if not document:
            raise ValueError("Document not found")

        # Delete old chunks from Qdrant
        self.rag.delete_document(doc_id)

        # Delete old file
        old_file_path = self.upload_dir / document.filename
        if old_file_path.exists():
            os.remove(old_file_path)

        # Save new file
        new_filename = f"{doc_id}.{file_type}"
        new_file_path = self.upload_dir / new_filename
        with open(new_file_path, "wb") as f:
            f.write(file_content)

        # Update document record
        document.filename = new_filename
        document.original_name = original_name
        document.file_type = file_type
        document.file_size = len(file_content)
        document.status = DocumentStatus.PROCESSING
        document.error_message = None

        await self.db.commit()

        # Re-index document
        try:
            chunk_count = self.rag.add_document(str(new_file_path), doc_id)
            document.chunk_count = chunk_count
            document.status = DocumentStatus.READY
        except Exception as e:
            document.status = DocumentStatus.ERROR
            document.error_message = str(e)[:500]

        await self.db.commit()
        await self.db.refresh(document)

        return document

    async def delete_document(self, doc_id: str) -> bool:
        document = await self.get_document(doc_id)
        if not document:
            return False

        # Delete from Qdrant
        self.rag.delete_document(doc_id)

        # Delete file
        file_path = self.upload_dir / document.filename
        if file_path.exists():
            os.remove(file_path)

        # Delete from database
        await self.db.delete(document)
        await self.db.commit()

        return True
```

**Step 2: Create documents router**

```python
# backend/app/api/v1/documents.py
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_admin_user, get_rag_engine, get_settings_dep
from app.models.user import User
from app.core.rag import RAGEngine
from app.config import Settings
from app.services.document_service import DocumentService
from app.schemas.document import DocumentResponse, DocumentListResponse

router = APIRouter(prefix="/admin/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {"txt", "md", "html", "pdf", "docx", "xlsx"}


def get_file_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    rag: Annotated[RAGEngine, Depends(get_rag_engine)]
):
    service = DocumentService(db, settings, rag)
    documents = await service.list_documents()
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=len(documents)
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    rag: Annotated[RAGEngine, Depends(get_rag_engine)]
):
    service = DocumentService(db, settings, rag)
    document = await service.get_document(doc_id)
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

    service = DocumentService(db, settings, rag)
    document = await service.upload_document(
        file_content=content,
        original_name=file.filename or "unknown",
        file_type=ext,
        user_id=user.id
    )

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
    ext = get_file_extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await file.read()

    service = DocumentService(db, settings, rag)
    try:
        document = await service.replace_document(
            doc_id=doc_id,
            file_content=content,
            original_name=file.filename or "unknown",
            file_type=ext
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return DocumentResponse.model_validate(document)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    rag: Annotated[RAGEngine, Depends(get_rag_engine)]
):
    service = DocumentService(db, settings, rag)
    deleted = await service.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}
```

**Step 3: Update v1 __init__.py**

```python
# backend/app/api/v1/__init__.py
from fastapi import APIRouter
from .auth import router as auth_router
from .chat import router as chat_router
from .documents import router as documents_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(documents_router)
```

**Step 4: Commit**

```bash
git add backend/app/services/document_service.py backend/app/api/v1/documents.py backend/app/api/v1/__init__.py
git commit -m "feat: add documents CRUD API with upload/replace/delete"
```

---

### Task 5.5: Users and Settings Endpoints

**Files:**
- Create: `backend/app/api/v1/users.py`
- Create: `backend/app/api/v1/settings.py`

**Step 1: Create users router**

```python
# backend/app/api/v1/users.py
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_admin_user, get_auth_service
from app.services.auth_service import AuthService
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/admin/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthService, Depends(get_auth_service)]
):
    # Check if email exists
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=data.email,
        password_hash=auth.hash_password(data.password),
        role=data.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UserUpdate,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthService, Depends(get_auth_service)]
):
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.email is not None:
        target_user.email = data.email
    if data.password is not None:
        target_user.password_hash = auth.hash_password(data.password)
    if data.role is not None:
        target_user.role = data.role
    if data.is_active is not None:
        target_user.is_active = data.is_active

    await db.commit()
    await db.refresh(target_user)

    return UserResponse.model_validate(target_user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(target_user)
    await db.commit()

    return {"message": "User deleted successfully"}
```

**Step 2: Create settings router**

```python
# backend/app/api/v1/settings.py
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_admin_user
from app.models.user import User
from app.models.settings import SystemSettings

router = APIRouter(prefix="/admin/settings", tags=["settings"])


@router.get("")
async def get_settings(
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(SystemSettings))
    settings = {s.key: s.value for s in result.scalars().all()}
    return settings


@router.put("")
async def update_settings(
    data: dict,
    user: Annotated[User, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    for key, value in data.items():
        result = await db.execute(
            select(SystemSettings).where(SystemSettings.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
        else:
            setting = SystemSettings(key=key, value=value)
            db.add(setting)

    await db.commit()
    return {"message": "Settings updated successfully"}
```

**Step 3: Update v1 __init__.py**

```python
# backend/app/api/v1/__init__.py
from fastapi import APIRouter
from .auth import router as auth_router
from .chat import router as chat_router
from .documents import router as documents_router
from .users import router as users_router
from .settings import router as settings_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(documents_router)
api_router.include_router(users_router)
api_router.include_router(settings_router)
```

**Step 4: Commit**

```bash
git add backend/app/api/v1/users.py backend/app/api/v1/settings.py backend/app/api/v1/__init__.py
git commit -m "feat: add users and settings admin endpoints"
```

---

### Task 5.6: Main Application Entry Point

**Files:**
- Create: `backend/app/main.py`

**Step 1: Create FastAPI application**

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    print(f"Starting FAQ RAG Bot with LLM provider: {settings.LLM_PROVIDER}")
    yield
    # Shutdown
    print("Shutting down FAQ RAG Bot")


app = FastAPI(
    title="FAQ RAG Bot API",
    description="RAG-based FAQ Bot for documentation Q&A",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

**Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: add FastAPI main application"
```

---

### Task 5.7: Alembic Migrations Setup

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`

**Step 1: Create alembic.ini**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = driver://user:pass@localhost/dbname

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**Step 2: Create alembic env.py**

```python
# backend/alembic/env.py
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import get_settings
from app.models import Base

config = context.config
settings = get_settings()

config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 3: Create script.py.mako**

```python
# backend/alembic/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

**Step 4: Commit**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "feat: add Alembic migrations setup"
```

---

## Phase 6: Frontend Setup

### Task 6.1: Configure Frontend for Admin Panel

**Files:**
- Modify: `frontend/src/shared/api/httpClient.ts`
- Modify: `frontend/vite.config.ts`
- Create: `frontend/.env.example`

**Step 1: Create .env.example**

```bash
VITE_API_URL=http://localhost:8000
```

**Step 2: Update vite.config.ts with proxy**

Add proxy configuration to `frontend/vite.config.ts`:

```typescript
// Add to server config
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
},
```

**Step 3: Commit**

```bash
git add frontend/
git commit -m "feat: configure frontend for API integration"
```

---

## Phase 7: Frontend Features (следует делать по шаблону FSD)

> Фронтенд разрабатывается согласно правилам и скиллам из `.claude/rules/` и `.claude/skills/`.
> При создании каждой фичи использовать соответствующий скилл:
> - `@.claude/skills/create/create-auth-flow.md` — для авторизации
> - `@.claude/skills/create/create-page.md` — для страниц
> - `@.claude/skills/create/create-feature.md` — для фич
> - `@.claude/skills/create/create-table-with-pagination.md` — для таблицы документов

### Task 7.1: Auth Feature

Использовать скилл: `@.claude/skills/create/create-auth-flow.md`

**Создать:**
- `src/features/auth/` — логика авторизации
- `src/entities/user/` — сущность пользователя
- `src/pages/login/` — страница входа

### Task 7.2: Documents Feature

Использовать скиллы:
- `@.claude/skills/create/create-feature.md`
- `@.claude/skills/create/create-table-with-pagination.md`

**Создать:**
- `src/entities/document/` — сущность документа
- `src/features/documents-table/` — таблица документов
- `src/features/document-upload/` — загрузка документов
- `src/pages/documents/` — страница управления документами

### Task 7.3: Users Feature

**Создать:**
- `src/features/users-table/` — таблица пользователей
- `src/pages/users/` — страница управления пользователями

### Task 7.4: Settings Feature

**Создать:**
- `src/features/settings-form/` — форма настроек
- `src/pages/settings/` — страница настроек

### Task 7.5: Navigation and Layout

**Создать:**
- `src/widgets/admin-sidebar/` — боковая навигация
- `src/widgets/admin-header/` — шапка админки
- Обновить `src/app/providers/router.tsx` — добавить маршруты

---

## Verification Checklist

После завершения всех задач:

1. **Backend:**
   - [ ] `docker-compose up` запускает все сервисы
   - [ ] `POST /api/v1/auth/login` возвращает токены
   - [ ] `POST /api/v1/chat` отвечает на вопросы
   - [ ] `POST /api/v1/admin/documents` загружает документы
   - [ ] `GET /api/v1/admin/documents` показывает список
   - [ ] `PUT /api/v1/admin/documents/{id}` заменяет документ
   - [ ] `DELETE /api/v1/admin/documents/{id}` удаляет документ

2. **Frontend:**
   - [ ] `pnpm dev` запускается без ошибок
   - [ ] `pnpm lint` проходит без ошибок
   - [ ] `pnpm typecheck` проходит без ошибок
   - [ ] Логин работает
   - [ ] Таблица документов отображается
   - [ ] Загрузка/замена/удаление документов работает

3. **Integration:**
   - [ ] Загрузить тестовый документ
   - [ ] Задать вопрос по документу
   - [ ] Проверить, что ответ содержит источники
   - [ ] Проверить, что бот говорит "не знаю" на нерелевантный вопрос
