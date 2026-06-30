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
