"""
Hybrid retriever: dense (bge-m3 через Ollama) + sparse (BM25 через FastEmbed) +
RRF fusion. Используется только в eval_rag.py для сравнительного прогона.

Отдельный файл, не трогает прод-код в app/core/rag/retriever.py.
"""

from fastembed import SparseTextEmbedding
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, SparseVectorParams, VectorParams


COLLECTION_NAME = "documents_hybrid"
SPARSE_MODEL_NAME = "Qdrant/bm25"


def _build_sparse_callbacks():
    """Возвращает (sparse_doc_fn, sparse_query_fn) для llama_index QdrantVectorStore."""
    sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)

    def sparse_doc_fn(texts: list[str]):
        # FastEmbed возвращает iterator SparseEmbedding(indices, values).
        indices, values = [], []
        for emb in sparse_model.embed(texts):
            indices.append(emb.indices.tolist())
            values.append(emb.values.tolist())
        return indices, values

    def sparse_query_fn(texts: list[str]):
        indices, values = [], []
        for emb in sparse_model.query_embed(texts):
            indices.append(emb.indices.tolist())
            values.append(emb.values.tolist())
        return indices, values

    return sparse_doc_fn, sparse_query_fn


class HybridQdrantRetriever:
    """Аналог QdrantRetriever, но с hybrid (dense + sparse)."""

    def __init__(self, qdrant_url: str, embedding_model):
        self.client = QdrantClient(url=qdrant_url)
        self.embedding_model = embedding_model
        self.sparse_doc_fn, self.sparse_query_fn = _build_sparse_callbacks()
        self._ensure_collection()

    def _get_embedding_dim(self) -> int:
        return len(self.embedding_model.get_text_embedding("test"))

    def _ensure_collection(self):
        names = [c.name for c in self.client.get_collections().collections]
        if COLLECTION_NAME in names:
            return
        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "text-dense": VectorParams(
                    size=self._get_embedding_dim(),
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "text-sparse": SparseVectorParams(),
            },
        )

    def get_vector_store(self) -> QdrantVectorStore:
        return QdrantVectorStore(
            client=self.client,
            collection_name=COLLECTION_NAME,
            enable_hybrid=True,
            sparse_doc_fn=self.sparse_doc_fn,
            sparse_query_fn=self.sparse_query_fn,
            dense_config=VectorParams(
                size=self._get_embedding_dim(),
                distance=Distance.COSINE,
            ),
            sparse_config=SparseVectorParams(),
        )

    def get_index(self) -> VectorStoreIndex:
        vs = self.get_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vs)
        return VectorStoreIndex.from_vector_store(
            vs,
            embed_model=self.embedding_model,
            storage_context=storage_context,
        )

    def add_documents(self, nodes: list, document_id: str):
        for node in nodes:
            node.metadata["document_id"] = document_id
        vs = self.get_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vs)
        VectorStoreIndex(
            nodes,
            embed_model=self.embedding_model,
            storage_context=storage_context,
        )
