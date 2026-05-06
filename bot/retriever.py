import json
from typing import Optional
import structlog

from config import settings

logger = structlog.get_logger()

try:
    from embedder.vector_store import search as vector_search
except ImportError:
    vector_search = None

CATEGORY_KEYWORDS = {
    "corporate_tax": ["company", "corporate", "sdn bhd", "syarikat", "C form", "pioneer"],
    "rpgt": ["property", "RPGT", "rumah", "house", "real estate", "CKHT", "disposal"],
    "stamp_duty": ["stamp duty", "duti setem", "MOT", "transfer"],
    "sst": ["SST", "sales tax", "service tax", "cukai jualan", "cukai perkhidmatan"],
    "withholding_tax": ["withholding", "WHT", "non-resident payment", "CP37", "royalty"],
    "personal_tax": ["personal", "salary", "employment", "gaji", "BE form", "PCB"],
    "reliefs": ["relief", "deduction", "claim", "pelepasan", "medical", "education"],
    "expatriate": ["expatriate", "foreigner", "non-resident", "work permit"],
}

SOURCE_BOOST = {
    "official_government": 1.5,
    "professional_commentary": 1.0,
    "news": 0.7,
}


def retrieve(query: str, intent: Optional[str] = None, top_k: int = 6) -> list[dict]:
    category_filter = _detect_category_filter(query, intent)

    # Semantic search (gracefully skip if vector store not available)
    if vector_search is None:
        return []

    try:
        raw_results = vector_search(
            query=query,
            n_results=20,
            tax_category_filter=category_filter,
        )
    except Exception as e:
        logger.warning("vector_search_unavailable", error=str(e))
        return []

    # Apply source boosting
    for result in raw_results:
        source_type = result.get("metadata", {}).get("source_type", "")
        boost = SOURCE_BOOST.get(source_type, 1.0)
        result["boosted_score"] = result.get("relevance_score", 0) * boost

    # Sort by boosted score
    raw_results.sort(key=lambda x: x["boosted_score"], reverse=True)

    # Re-rank with Cohere if available
    top_results = _rerank(query, raw_results[:20], top_k)

    return top_results


def _detect_category_filter(query: str, intent: Optional[str]) -> Optional[list[str]]:
    query_lower = query.lower()
    matched_categories = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw.lower() in query_lower for kw in keywords):
            matched_categories.append(category)

    if intent and intent in CATEGORY_KEYWORDS:
        if intent not in matched_categories:
            matched_categories.append(intent)

    return matched_categories if matched_categories else None


def _rerank(query: str, results: list[dict], top_k: int) -> list[dict]:
    if not settings.cohere_api_key or not results:
        return results[:top_k]

    try:
        import cohere
        co = cohere.Client(settings.cohere_api_key)

        documents = [r["text"] for r in results]
        rerank_response = co.rerank(
            query=query,
            documents=documents,
            model="rerank-multilingual-v3.0",
            top_n=top_k,
        )

        reranked = []
        for item in rerank_response.results:
            result = results[item.index]
            result["rerank_score"] = item.relevance_score
            reranked.append(result)

        return reranked

    except Exception as e:
        logger.warning("rerank_failed", error=str(e))
        return results[:top_k]


def format_context(chunks: list[dict]) -> str:
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("title", "Unknown Source")
        source_url = meta.get("source_url", "")
        score = chunk.get("rerank_score", chunk.get("boosted_score", chunk.get("relevance_score", 0)))

        context_parts.append(
            f"[SOURCE {i}: {source} | Relevance: {score:.2f}]\n"
            f"[URL: {source_url}]\n"
            f"[TEXT]: {chunk['text']}\n"
        )

    return "\n---\n".join(context_parts)
