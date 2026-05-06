import re


def clean_text(text: str) -> str:
    # Remove repeated header/footer patterns
    lines = text.split("\n")
    if len(lines) > 20:
        text = _remove_repeated_lines(lines)

    # Fix common OCR errors
    text = _fix_ocr_errors(text)

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +\n", "\n", text)

    # Remove page numbers
    text = re.sub(r"\n\s*-?\s*\d+\s*-?\s*\n", "\n", text)
    text = re.sub(r"\nPage \d+ of \d+\n", "\n", text)

    # Remove excessive dots (table of contents leaders)
    text = re.sub(r"\.{5,}", " ", text)

    return text.strip()


def _remove_repeated_lines(lines: list[str]) -> str:
    if len(lines) < 10:
        return "\n".join(lines)

    # Count occurrences of each line
    line_counts: dict[str, int] = {}
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 5:
            line_counts[stripped] = line_counts.get(stripped, 0) + 1

    # Lines appearing more than 3 times are likely headers/footers
    repeated = {line for line, count in line_counts.items() if count > 3}

    filtered = [line for line in lines if line.strip() not in repeated]
    return "\n".join(filtered)


def _fix_ocr_errors(text: str) -> str:
    replacements = {
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "'": "'",
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "\xa0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Fix "RM" with space: "R M 5,000" -> "RM 5,000"
    text = re.sub(r"\bR\s+M\s+(\d)", r"RM \1", text)

    return text


def extract_section_headers(text: str) -> list[dict]:
    headers = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match numbered sections like "3.2 Medical Expenses"
        if re.match(r"^\d+(\.\d+)*\s+[A-Z]", stripped):
            headers.append({"index": i, "text": stripped})
        # Match all-caps headers
        elif stripped.isupper() and 5 < len(stripped) < 100:
            headers.append({"index": i, "text": stripped})

    return headers
