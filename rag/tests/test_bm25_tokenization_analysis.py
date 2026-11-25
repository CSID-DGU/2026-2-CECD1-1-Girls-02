from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_bm25_tokenization.py"
_SPEC = importlib.util.spec_from_file_location("analyze_bm25_tokenization", _SCRIPT)
assert _SPEC and _SPEC.loader
analysis = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(analysis)


class BM25TokenizationAnalysisTests(unittest.TestCase):
    def test_analyzes_only_active_faqs_without_changing_rows(self) -> None:
        rows = [
            {"id": "1", "title": "쿠폰은 언제 지급되나요?", "content": "결제 후 지급됩니다.", "active": True},
            {"id": "2", "title": "제외 질문", "content": "제외 답변", "active": False},
        ]
        original = [dict(row) for row in rows]

        summary, per_faq, paraphrases = analysis.analyze(rows)

        self.assertEqual(summary["record_counts"]["active_analyzed"], 1)
        self.assertEqual(summary["record_counts"]["inactive_excluded"], 1)
        self.assertEqual(len(per_faq), 1)
        self.assertEqual(per_faq[0]["source_id"], "faq:1")
        self.assertEqual(len(paraphrases), 1)
        self.assertEqual(rows, original)

    def test_reports_overlap_without_claiming_search_accuracy(self) -> None:
        summary, per_faq, _ = analysis.analyze(
            [{"id": "1", "title": "쿠폰 지급", "content": "쿠폰은 결제 후 지급", "active": True}]
        )

        self.assertEqual(per_faq[0]["question_to_answer_common_token_count"], 1)
        self.assertEqual(per_faq[0]["question_to_answer_match_ratio"], 0.5)
        self.assertNotIn("recall", summary)


if __name__ == "__main__":
    unittest.main()
