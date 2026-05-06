import re
from typing import Optional
import tiktoken

MAX_CHUNK_TOKENS = 512
OVERLAP_TOKENS = 50

_encoder = None


def get_encoder():
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    return len(get_encoder().encode(text))


def chunk_document(
    text: str,
    doc_id: str,
    metadata: Optional[dict] = None,
    max_tokens: int = MAX_CHUNK_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[dict]:
    if not text.strip():
        return []

    sections = _split_by_sections(text)
    chunks = []
    chunk_index = 0

    for section_header, section_text in sections:
        section_chunks = _chunk_section(section_text, max_tokens, overlap_tokens)
        for chunk_text in section_chunks:
            chunk = {
                "chunk_id": f"{doc_id}_chunk_{chunk_index:04d}",
                "doc_id": doc_id,
                "text": chunk_text,
                "chunk_index": chunk_index,
                "section_header": section_header,
                "token_count": count_tokens(chunk_text),
            }
            if metadata:
                chunk.update(metadata)
            chunks.append(chunk)
            chunk_index += 1

    for chunk in chunks:
        chunk["total_chunks"] = chunk_index

    return chunks


def _split_by_sections(text: str) -> list[tuple[str, str]]:
    pattern = r"(?m)^(\d+(?:\.\d+)*\s+[A-Z][^\n]*|[A-Z][A-Z\s]{4,}[A-Z])$"
    matches = list(re.finditer(pattern, text))

    if not matches:
        return [("", text)]

    sections = []
    for i, match in enumerate(matches):
        header = match.group().strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        if section_text:
            sections.append((header, section_text))

    # Include text before first header
    if matches[0].start() > 0:
        preamble = text[:matches[0].start()].strip()
        if preamble:
            sections.insert(0, ("", preamble))

    return sections


def _chunk_section(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    if count_tokens(text) <= max_tokens:
        return [text]

    sentences = _split_into_sentences(text)
    chunks = []
    current_chunk: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)

        if sentence_tokens > max_tokens:
            # Single sentence too long - split by words
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_tokens = 0
            words = sentence.split()
            word_chunk: list[str] = []
            word_tokens = 0
            for word in words:
                wt = count_tokens(word + " ")
                if word_tokens + wt > max_tokens:
                    chunks.append(" ".join(word_chunk))
                    word_chunk = [word]
                    word_tokens = wt
                else:
                    word_chunk.append(word)
                    word_tokens += wt
            if word_chunk:
                current_chunk = word_chunk
                current_tokens = word_tokens
            continue

        if current_tokens + sentence_tokens > max_tokens:
            chunks.append(" ".join(current_chunk))
            # Keep overlap from end of previous chunk
            overlap_text = " ".join(current_chunk)
            overlap_sentences = _get_tail_sentences(overlap_text, overlap_tokens)
            current_chunk = overlap_sentences + [sentence]
            current_tokens = count_tokens(" ".join(current_chunk))
        else:
            current_chunk.append(sentence)
            current_tokens += sentence_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def _split_into_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [s.strip() for s in sentences if s.strip()]


def _get_tail_sentences(text: str, max_tokens: int) -> list[str]:
    sentences = _split_into_sentences(text)
    result: list[str] = []
    tokens = 0
    for sentence in reversed(sentences):
        st = count_tokens(sentence)
        if tokens + st > max_tokens:
            break
        result.insert(0, sentence)
        tokens += st
    return result
