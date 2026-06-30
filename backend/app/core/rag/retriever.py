from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex, StorageContext


class QdrantRetriever:
    COLLECTION_NAME = "documents"

    def __init__(self, qdrant_url: str, embedding_model):
        self.client = QdrantClient(url=qdrant_url)
        self.embedding_model = embedding_model
        self._ensure_collection()

    def _get_embedding_dim(self) -> int:
        test_embedding = self.embedding_model.get_text_embedding("test")
        return len(test_embedding)

    def _ensure_collection(self):
        collections = self.client.get_collections().collections
        existing = next(
            (c for c in collections if c.name == self.COLLECTION_NAME), None
        )
        if existing is None:
            dim = self._get_embedding_dim()
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=dim,
                    distance=Distance.COSINE,
                ),
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
