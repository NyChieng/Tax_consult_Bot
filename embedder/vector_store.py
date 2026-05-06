import json
from pathlib import Path
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
import structlog

from config import settings

logger = structlog.get_logger()

PROCESSED_DIR = Path("data/processed")
COLLECTION_NAME = "mycukai_tax_docs"


def get_chroma_client() -> chromadb.ClientAPI:
    if settings.environment == "production":
        return chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
    return chromadb.PersistentClient(path="data/embeddings/chroma")


def get_collection(client: Optional[chromadb.ClientAPI] = None):
    if client is None:
        client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def embed_all_chunks():
    import voyageai

    vo = voyageai.Client(api_key=settings.voyage_api_key)
    collection = get_collection()

    chunk_files = list(PROCESSED_DIR.rglob("*.jsonl"))
    total_embedded = 0

    for chunk_file in chunk_files:
        chunks = _load_chunks(chunk_file)
        if not chunks:
            continue

        # Batch embed (Voyage limit: 128 per batch)
        batch_size = 96
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c["text"] for c in batch]
            ids = [c["chunk_id"] for c in batch]

            # Check if already embedded
            existing = collection.get(ids=ids)
            new_ids = set(ids) - set(existing["ids"])
            if not new_ids:
                continue

            new_batch = [c for c in batch if c["chunk_id"] in new_ids]
            new_texts = [c["text"] for c in new_batch]
            new_ids_list = [c["chunk_id"] for c in new_batch]

            if not new_texts:
                continue

            result = vo.embed(new_texts, model="voyage-3", input_type="document")

            metadatas = []
            for chunk in new_batch:
                meta = {
                    "doc_id": chunk.get("doc_id", ""),
                    "source_url": chunk.get("source_url", ""),
                    "source_type": chunk.get("source_type", ""),
                    "title": chunk.get("title", ""),
                    "section_header": chunk.get("section_header", ""),
                    "tax_category": json.dumps(chunk.get("tax_category", [])),
                    "topic_tags": json.dumps(chunk.get("topic_tags", [])),
                    "language": chunk.get("language", "en"),
                }
                metadatas.append(meta)

            collection.add(
                ids=new_ids_list,
                embeddings=result.embeddings,
                documents=new_texts,
                metadatas=metadatas,
            )
            total_embedded += len(new_ids_list)
            logger.info("embedded_batch", count=len(new_ids_list), total=total_embedded)

    logger.info("embedding_complete", total=total_embedded)
    return total_embedded


def search(
    query: str,
    n_results: int = 20,
    tax_category_filter: Optional[list[str]] = None,
) -> list[dict]:
    import voyageai

    vo = voyageai.Client(api_key=settings.voyage_api_key)
    collection = get_collection()

    query_embedding = vo.embed([query], model="voyage-3", input_type="query").embeddings[0]

    where_filter = None
    if tax_category_filter:
        # ChromaDB $contains for JSON array stored as string
        where_filter = {
            "$or": [
                {"tax_category": {"$contains": cat}}
                for cat in tax_category_filter
            ]
        }

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            chunk = {
                "text": doc,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0,
                "relevance_score": 1 - (results["distances"][0][i] if results["distances"] else 0),
            }
            chunks.append(chunk)

    return chunks


def _load_chunks(chunk_file: Path) -> list[dict]:
    chunks = []
    with open(chunk_file, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


if __name__ == "__main__":
    embed_all_chunks()
