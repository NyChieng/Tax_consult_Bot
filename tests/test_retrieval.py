import pytest
from processor.tagger import classify_tax_category, extract_topic_tags, detect_act_references
from processor.chunker import chunk_document, count_tokens
from processor.text_cleaner import clean_text


class TestTagger:
    def test_personal_tax_classification(self):
        text = "Individual taxpayer personal income employment salary monthly PCB deduction"
        cats = classify_tax_category(text)
        assert "personal_tax" in cats

    def test_corporate_tax_classification(self):
        text = "Company Sdn Bhd corporate tax rate pioneer status investment tax allowance"
        cats = classify_tax_category(text)
        assert "corporate_tax" in cats

    def test_sst_classification(self):
        text = "SST sales tax service tax registration threshold cukai jualan"
        cats = classify_tax_category(text)
        assert "sst" in cats

    def test_rpgt_classification(self):
        text = "RPGT real property gains tax disposal holding period CKHT"
        cats = classify_tax_category(text)
        assert "rpgt" in cats

    def test_topic_tags_efiling(self):
        text = "e-filing online submission mytax portal"
        tags = extract_topic_tags(text)
        assert "efiling" in tags

    def test_act_references(self):
        text = "Under the Income Tax Act 1967, Section 4(a), residents are taxed on employment income."
        refs = detect_act_references(text)
        assert "ITA1967" in refs


class TestChunker:
    def test_basic_chunking(self):
        text = "This is a test sentence. " * 200
        chunks = chunk_document(text, "test_doc")
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk["token_count"] <= 520  # Small tolerance

    def test_short_document(self):
        text = "This is a short document about tax rates."
        chunks = chunk_document(text, "short_doc")
        assert len(chunks) == 1

    def test_chunk_ids(self):
        text = "Test content. " * 300
        chunks = chunk_document(text, "id_test")
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))  # All unique

    def test_metadata_preserved(self):
        text = "Tax relief information for residents."
        meta = {"source_url": "https://hasil.gov.my/test", "title": "Test Doc"}
        chunks = chunk_document(text, "meta_test", meta)
        assert chunks[0]["source_url"] == "https://hasil.gov.my/test"


class TestTextCleaner:
    def test_normalize_whitespace(self):
        text = "Hello    world\n\n\n\n\nTest"
        cleaned = clean_text(text)
        assert "    " not in cleaned
        assert "\n\n\n" not in cleaned

    def test_rm_fix(self):
        text = "The amount is R M 5,000 per year"
        cleaned = clean_text(text)
        assert "RM 5,000" in cleaned

    def test_page_number_removal(self):
        text = "Content here\n- 5 -\nMore content"
        cleaned = clean_text(text)
        assert "- 5 -" not in cleaned
