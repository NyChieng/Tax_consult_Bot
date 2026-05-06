import pdfplumber
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()

MIN_CHARS_PER_PAGE = 50


def extract_text_from_pdf(pdf_path: Path) -> Optional[str]:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_text.append(text)

            full_text = "\n\n".join(pages_text)

            # Check if extraction yielded useful text
            avg_chars = len(full_text) / max(len(pdf.pages), 1)
            if avg_chars < MIN_CHARS_PER_PAGE:
                logger.warning("low_text_extraction", path=str(pdf_path), avg_chars=avg_chars)
                return _try_ocr_fallback(pdf_path)

            return full_text

    except Exception as e:
        logger.error("pdf_extraction_error", path=str(pdf_path), error=str(e))
        return _try_ocr_fallback(pdf_path)


def _try_ocr_fallback(pdf_path: Path) -> Optional[str]:
    try:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(pdf_path)
        text_parts = []
        for img in images:
            text = pytesseract.image_to_string(img, lang="eng+msa")
            text_parts.append(text)

        full_text = "\n\n".join(text_parts)
        if len(full_text.strip()) > 100:
            logger.info("ocr_fallback_success", path=str(pdf_path))
            return full_text

        return None
    except ImportError:
        logger.warning("ocr_deps_missing", msg="Install pdf2image and pytesseract for OCR")
        return None
    except Exception as e:
        logger.error("ocr_error", path=str(pdf_path), error=str(e))
        return None


def extract_tables_from_pdf(pdf_path: Path) -> list[list[list[str]]]:
    tables = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    tables.extend(page_tables)
    except Exception as e:
        logger.error("table_extraction_error", path=str(pdf_path), error=str(e))
    return tables


def get_pdf_metadata(pdf_path: Path) -> dict:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            meta = pdf.metadata or {}
            return {
                "page_count": len(pdf.pages),
                "title": meta.get("Title", ""),
                "author": meta.get("Author", ""),
                "creation_date": meta.get("CreationDate", ""),
            }
    except Exception:
        return {"page_count": 0}
