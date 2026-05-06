import json
from pathlib import Path
import structlog

from processor.pdf_extractor import extract_text_from_pdf, get_pdf_metadata
from processor.text_cleaner import clean_text
from processor.chunker import chunk_document
from processor.tagger import tag_chunk

logger = structlog.get_logger()

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")


def process_all():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    total_chunks = 0

    # Process PDFs
    for pdf_path in RAW_DIR.rglob("*.pdf"):
        chunks = process_pdf(pdf_path)
        total_chunks += len(chunks)

    # Process text files
    for txt_path in RAW_DIR.rglob("*.txt"):
        chunks = process_text_file(txt_path)
        total_chunks += len(chunks)

    # Process JSONL files (FAQs, news)
    for jsonl_path in RAW_DIR.rglob("*.jsonl"):
        chunks = process_jsonl(jsonl_path)
        total_chunks += len(chunks)

    logger.info("processing_complete", total_chunks=total_chunks)
    return total_chunks


def process_pdf(pdf_path: Path) -> list[dict]:
    logger.info("processing_pdf", path=str(pdf_path))

    text = extract_text_from_pdf(pdf_path)
    if not text:
        logger.warning("no_text_extracted", path=str(pdf_path))
        return []

    text = clean_text(text)
    pdf_meta = get_pdf_metadata(pdf_path)

    # Load scraper metadata if available
    meta_path = pdf_path.with_suffix(".meta.json")
    scraper_meta = {}
    if meta_path.exists():
        with open(meta_path) as f:
            scraper_meta = json.load(f)

    doc_id = _make_doc_id(pdf_path)
    base_metadata = {
        "source_url": scraper_meta.get("source_url", ""),
        "source_type": scraper_meta.get("source_type", "official_government"),
        "document_type": scraper_meta.get("section", ""),
        "title": scraper_meta.get("title", pdf_path.stem),
        "date_scraped": scraper_meta.get("scraped_at", ""),
        "language": scraper_meta.get("language", "en"),
        "page_count": pdf_meta.get("page_count", 0),
    }

    chunks = chunk_document(text, doc_id, base_metadata)

    # Apply tagging to each chunk
    for chunk in chunks:
        tags = tag_chunk(chunk["text"])
        chunk.update(tags)

    _save_chunks(chunks, pdf_path)
    return chunks


def process_text_file(txt_path: Path) -> list[dict]:
    logger.info("processing_text", path=str(txt_path))

    with open(txt_path, encoding="utf-8") as f:
        text = f.read()

    text = clean_text(text)
    if len(text) < 100:
        return []

    meta_path = txt_path.with_suffix(".meta.json")
    scraper_meta = {}
    if meta_path.exists():
        with open(meta_path) as f:
            scraper_meta = json.load(f)

    doc_id = _make_doc_id(txt_path)
    base_metadata = {
        "source_url": scraper_meta.get("source_url", ""),
        "source_type": scraper_meta.get("source_type", "professional_commentary"),
        "title": scraper_meta.get("title", txt_path.stem),
        "date_scraped": scraper_meta.get("scraped_at", ""),
        "language": scraper_meta.get("language", "en"),
    }

    chunks = chunk_document(text, doc_id, base_metadata)
    for chunk in chunks:
        tags = tag_chunk(chunk["text"])
        chunk.update(tags)

    _save_chunks(chunks, txt_path)
    return chunks


def process_jsonl(jsonl_path: Path) -> list[dict]:
    logger.info("processing_jsonl", path=str(jsonl_path))
    all_chunks = []

    with open(jsonl_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            item = json.loads(line)
            text = ""
            if "question" in item and "answer" in item:
                text = f"Q: {item['question']}\nA: {item['answer']}"
            elif "title" in item and "summary" in item:
                text = f"{item['title']}\n{item['summary']}"

            if not text:
                continue

            doc_id = f"{_make_doc_id(jsonl_path)}_{i:04d}"
            chunk = {
                "chunk_id": f"{doc_id}_chunk_0000",
                "doc_id": doc_id,
                "text": clean_text(text),
                "chunk_index": 0,
                "total_chunks": 1,
                "section_header": item.get("question", item.get("title", "")),
                "source_type": "official_government",
            }
            tags = tag_chunk(chunk["text"])
            chunk.update(tags)
            all_chunks.append(chunk)

    _save_chunks(all_chunks, jsonl_path)
    return all_chunks


def _make_doc_id(file_path: Path) -> str:
    relative = file_path.relative_to(RAW_DIR) if RAW_DIR in file_path.parents else file_path
    return str(relative).replace("/", "_").replace("\\", "_").replace(".", "_")


def _save_chunks(chunks: list[dict], source_path: Path):
    if not chunks:
        return

    relative = source_path.relative_to(RAW_DIR) if RAW_DIR in source_path.parents else Path(source_path.name)
    output_path = PROCESSED_DIR / relative.with_suffix(".jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    logger.info("saved_chunks", path=str(output_path), count=len(chunks))


if __name__ == "__main__":
    process_all()
