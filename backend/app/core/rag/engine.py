from llama_index.core import PromptTemplate
from .retriever import QdrantRetriever
from ..llm.base import BaseLLMAdapter


SYSTEM_PROMPT = """Ты — помощник, который отвечает на вопросы ТОЛЬКО на основе предоставленной документации.

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:
1. Используй ТОЛЬКО информацию из предоставленного контекста
2. Если ответа нет в контексте, скажи "Я не нашёл эту информацию в документации"
3. НИКОГДА не придумывай информацию и не используй общие знания
4. Отвечай на том же языке, на котором задан вопрос
5. Будь кратким и точным в ответах

Контекст из документации:
{context_str}

Вопрос пользователя: {query_str}

Ответ строго по контексту выше:"""


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
                "answer": "Я не нашёл релевантную информацию в документации для ответа на этот вопрос.",
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
