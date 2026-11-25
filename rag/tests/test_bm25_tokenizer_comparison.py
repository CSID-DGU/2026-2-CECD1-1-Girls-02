from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_SCRIPT = _SCRIPTS / "compare_bm25_tokenizers.py"
_SPEC = importlib.util.spec_from_file_location("compare_bm25_tokenizers", _SCRIPT)
assert _SPEC and _SPEC.loader
comparison = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(comparison)


class BM25TokenizerComparisonTests(unittest.TestCase):
    def test_compares_same_active_records_and_builds_both_indexes(self) -> None:
        rows = [
            {"id": "1", "title": "쿠폰은 사용되나요?", "content": "쿠폰 사용이 가능합니다.", "active": True},
            {"id": "2", "title": "제외", "content": "제외", "active": False},
        ]

        summary, per_faq, cases = comparison.compare(rows)

        self.assertEqual(summary["scope"]["active"], 1)
        self.assertEqual(summary["indexes_built"], {"basic_documents": 1, "kiwi_documents": 1})
        self.assertEqual(len(per_faq), 1)
        self.assertEqual(len(cases), 1)
        self.assertIn("token overlap is not BM25 retrieval quality", summary["limitations"])


if __name__ == "__main__":
    unittest.main()
