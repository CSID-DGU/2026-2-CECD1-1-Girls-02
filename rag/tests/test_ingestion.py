import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ingestion import OFFICIAL_COLLECTION, VOC_COLLECTION, IngestionError, chunk_text, make_chunks, parse_record


class IngestionTests(unittest.TestCase):
    def test_masks_direct_identifiers_before_chunking(self):
        record = parse_record({"source_id": "faq-001", "title": "Synthetic FAQ", "text": "문의는 test@example.com 또는 010-1234-5678로 주세요.", "document_version": "2026-01", "source_type": "official"}, "official")
        chunks, counts = make_chunks(record, OFFICIAL_COLLECTION)
        self.assertEqual(counts, {"email": 1, "phone": 1})
        self.assertNotIn("test@example.com", chunks[0].text)
        self.assertEqual(chunks[0].metadata["usage_scope"], "DRAFT_ONLY")

    def test_voc_is_never_policy_scope(self):
        record = parse_record({"source_id": "case-001", "title": "Synthetic case", "text": "No personal data.", "document_version": "2026-01", "source_type": "voc"}, "voc")
        chunks, _ = make_chunks(record, VOC_COLLECTION)
        self.assertEqual(chunks[0].metadata["usage_scope"], "AGENT_REFERENCE_ONLY")

    def test_rejects_collection_mismatch(self):
        record = parse_record({"source_id": "case-001", "title": "Synthetic case", "text": "Text", "document_version": "v1", "source_type": "voc"}, "voc")
        with self.assertRaises(IngestionError):
            make_chunks(record, OFFICIAL_COLLECTION)

    def test_chunks_are_bounded(self):
        chunks = chunk_text("A. " * 100, chunk_size=40, overlap=10)
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk) <= 40 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
