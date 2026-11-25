from __future__ import annotations

import unittest
from unittest.mock import Mock

from rag.app.ingestion import Chunk
from rag.app.retrieval.bm25 import (
    BM25Retriever,
    basic_tokenize,
    build_bm25_index,
    kiwi_tokenize,
)
from rag.app.retrieval.contracts import KnowledgeScope, SearchFilter, SearchRequest


def _chunk(chunk_id: str, text: str, **metadata_overrides: object) -> Chunk:
    metadata: dict[str, object] = {
        "document_id": f"document-{chunk_id}",
        "knowledge_scope": "official",
        "is_active": True,
        "review_status": "APPROVED",
        "allowed_use": "DRAFT_ONLY",
        "document_type": "FAQ",
        "locale": "ko-KR",
    }
    metadata.update(metadata_overrides)
    return Chunk(
        id=chunk_id,
        text=text,
        metadata=metadata,  # type: ignore[arg-type]
    )


class BM25IndexTests(unittest.TestCase):
    def test_builds_index_from_existing_ingestion_chunks(self) -> None:
        first = _chunk("chunk-1", "쿠폰 사용 방법")
        second = _chunk("chunk-2", "배송지 변경 안내")

        index = build_bm25_index([first, second])

        self.assertEqual(len(index), 2)
        self.assertIs(index.get_chunk("chunk-1"), first)
        self.assertEqual(index.get_chunk("chunk-2").text, second.text)
        self.assertEqual(index.get_chunk("chunk-2").metadata, second.metadata)
        self.assertEqual(index.tokenized_corpus[0], ("쿠폰", "사용", "방법"))

    def test_accepts_a_replaceable_tokenizer_and_retains_it(self) -> None:
        def tokenizer(text: str) -> tuple[str, ...]:
            return tuple(text.split("|"))

        index = build_bm25_index([_chunk("chunk-1", "쿠폰|사용")], tokenizer=tokenizer)

        self.assertIs(index.tokenizer, tokenizer)
        self.assertEqual(index.tokenized_corpus, (("쿠폰", "사용"),))

    def test_rejects_empty_and_invalid_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one chunk"):
            build_bm25_index([])
        with self.assertRaisesRegex(TypeError, "ingestion Chunk"):
            build_bm25_index([object()])  # type: ignore[list-item]
        with self.assertRaisesRegex(ValueError, "chunk text"):
            build_bm25_index([_chunk("chunk-1", "  ")])
        with self.assertRaisesRegex(ValueError, "duplicate chunk id"):
            build_bm25_index([_chunk("same", "one"), _chunk("same", "two")])
        with self.assertRaisesRegex(ValueError, "no valid tokens"):
            build_bm25_index([_chunk("chunk-1", "text")], tokenizer=lambda _: ())

    def test_unknown_chunk_id_is_explicit(self) -> None:
        index = build_bm25_index([_chunk("chunk-1", "FAQ text")])
        with self.assertRaisesRegex(KeyError, "unknown chunk id"):
            index.get_chunk("missing")

    def test_retriever_returns_existing_contract_with_bm25_strategy(self) -> None:
        retriever = BM25Retriever(build_bm25_index([_chunk("chunk-1", "FAQ text")]))
        request = SearchRequest(
            query="FAQ",
            filters=SearchFilter(scope=KnowledgeScope.OFFICIAL),
        )

        response = retriever.search(request)

        self.assertEqual(response.strategy, "bm25")
        self.assertGreaterEqual(response.elapsed_ms, 0)
        self.assertEqual(response.hits[0].document_id, "document-chunk-1")
        self.assertEqual(response.hits[0].chunk_id, "chunk-1")
        self.assertEqual(response.hits[0].text, "FAQ text")
        self.assertEqual(response.hits[0].metadata["review_status"], "APPROVED")

    def test_basic_tokenizer_is_minimal_and_deterministic(self) -> None:
        self.assertEqual(basic_tokenize("쿠폰, USE 2026!"), ("쿠폰", "use", "2026"))

    def test_kiwi_separates_particles_and_endings(self) -> None:
        tokens = kiwi_tokenize("쿠폰은 언제 지급되나요?")
        self.assertIn("쿠폰", tokens)
        self.assertIn("지급", tokens)
        self.assertNotIn("은", tokens)
        self.assertNotIn("나요", tokens)

    def test_kiwi_preserves_numbers_english_and_negation(self) -> None:
        tokens = kiwi_tokenize("APP에서 10% 할인되지 않아요.")
        self.assertIn("app", tokens)
        self.assertIn("10", tokens)
        self.assertIn("할인", tokens)
        self.assertIn("않", tokens)

    def test_kiwi_handles_empty_input_and_is_reproducible(self) -> None:
        self.assertEqual(kiwi_tokenize("   "), ())
        self.assertEqual(kiwi_tokenize("쿠폰 사용"), kiwi_tokenize("쿠폰 사용"))

    def test_both_tokenizers_build_the_existing_index_contract(self) -> None:
        chunks = [_chunk("chunk-1", "쿠폰은 온라인에서 사용합니다.")]
        self.assertEqual(len(build_bm25_index(chunks, tokenizer=basic_tokenize)), 1)
        self.assertEqual(len(build_bm25_index(chunks, tokenizer=kiwi_tokenize)), 1)


class BM25SearchTests(unittest.TestCase):
    @staticmethod
    def _retriever(chunks: list[Chunk], scores: list[float] | None = None, *, tokenizer=basic_tokenize):
        index = build_bm25_index(chunks, tokenizer=tokenizer)
        if scores is not None:
            engine = Mock()
            engine.get_scores.return_value = scores
            object.__setattr__(index, "_engine", engine)
        return BM25Retriever(index)

    @staticmethod
    def _request(query: str = "쿠폰", top_k: int = 5, **filter_overrides: object) -> SearchRequest:
        return SearchRequest(
            query=query,
            top_k=top_k,
            filters=SearchFilter(scope=KnowledgeScope.OFFICIAL, **filter_overrides),  # type: ignore[arg-type]
        )

    def test_applies_top_k_after_descending_score_sort(self) -> None:
        chunks = [_chunk(f"chunk-{number}", f"쿠폰 안내 {number}") for number in range(5)]
        retriever = self._retriever(chunks, [1.0, 5.0, 3.0, 4.0, 2.0])

        for top_k, expected in (
            (1, ["chunk-1"]),
            (3, ["chunk-1", "chunk-3", "chunk-2"]),
            (5, ["chunk-1", "chunk-3", "chunk-2", "chunk-4", "chunk-0"]),
        ):
            with self.subTest(top_k=top_k):
                response = retriever.search(self._request(top_k=top_k))
                self.assertEqual([hit.chunk_id for hit in response.hits], expected)
                self.assertEqual([hit.score for hit in response.hits], sorted([hit.score for hit in response.hits], reverse=True))

    def test_ties_are_sorted_by_chunk_id(self) -> None:
        retriever = self._retriever(
            [_chunk("chunk-b", "쿠폰"), _chunk("chunk-a", "쿠폰")], [1.0, 1.0]
        )
        self.assertEqual(
            [hit.chunk_id for hit in retriever.search(self._request()).hits],
            ["chunk-a", "chunk-b"],
        )

    def test_filters_unsafe_documents_before_top_k(self) -> None:
        chunks = [
            _chunk("inactive", "쿠폰", is_active=False),
            _chunk("pending", "쿠폰", review_status="PENDING_REVIEW"),
            _chunk("forbidden", "쿠폰", allowed_use="NOT_ALLOWED"),
            _chunk("voc", "쿠폰", knowledge_scope="voc"),
            _chunk("approved", "쿠폰"),
        ]
        response = self._retriever(chunks, [100, 90, 80, 70, -1]).search(
            self._request(top_k=1)
        )
        self.assertEqual([hit.chunk_id for hit in response.hits], ["approved"])
        self.assertEqual(response.hits[0].score, -1.0)

    def test_document_type_and_locale_filters_exclude_missing_or_other_values(self) -> None:
        chunks = [
            _chunk("faq-ko", "쿠폰", document_type="FAQ", locale="ko-KR"),
            _chunk("guide-ko", "쿠폰", document_type="GUIDE", locale="ko-KR"),
            _chunk("faq-en", "쿠폰", document_type="FAQ", locale="en-US"),
            _chunk("missing", "쿠폰", document_type=None, locale=None),
        ]
        request = SearchRequest(
            "쿠폰",
            SearchFilter(
                scope=KnowledgeScope.OFFICIAL,
                document_types=("FAQ",),
                locales=("ko-KR",),
            ),
        )
        response = self._retriever(chunks, [1, 10, 9, 8]).search(request)
        self.assertEqual([hit.chunk_id for hit in response.hits], ["faq-ko"])

    def test_no_lexical_match_returns_empty_even_for_positive_scores(self) -> None:
        retriever = self._retriever([_chunk("delivery", "배송지 변경")], [100.0])
        self.assertEqual(tuple(retriever.search(self._request("쿠폰")).hits), ())

    def test_zero_and_negative_scores_are_kept_only_for_lexical_matches(self) -> None:
        retriever = self._retriever(
            [_chunk("zero", "쿠폰 안내"), _chunk("negative", "쿠폰 사용")],
            [0.0, -2.0],
        )
        response = retriever.search(self._request())
        self.assertEqual([hit.score for hit in response.hits], [0.0, -2.0])

    def test_empty_query_tokens_and_no_filtered_candidates_return_empty(self) -> None:
        punctuation_only = self._retriever([_chunk("chunk", "쿠폰")]).search(
            self._request("!!!")
        )
        unsafe_only = self._retriever(
            [_chunk("pending", "쿠폰", review_status="PENDING_REVIEW")]
        ).search(self._request())
        self.assertEqual(tuple(punctuation_only.hits), ())
        self.assertEqual(tuple(unsafe_only.hits), ())

    def test_fewer_candidates_than_k_and_kiwi_query_tokenization(self) -> None:
        retriever = self._retriever(
            [_chunk("coupon", "쿠폰은 온라인에서 사용합니다.")], tokenizer=kiwi_tokenize
        )
        response = retriever.search(self._request("쿠폰을 사용해요?", top_k=5))
        self.assertEqual([hit.chunk_id for hit in response.hits], ["coupon"])

    def test_official_inactive_request_and_scoring_errors_are_not_hidden(self) -> None:
        retriever = self._retriever([_chunk("chunk", "쿠폰")])
        with self.assertRaisesRegex(ValueError, "active_only=True"):
            retriever.search(self._request(active_only=False))

        retriever.index._engine.get_scores = Mock(side_effect=RuntimeError("scoring failed"))
        with self.assertRaisesRegex(RuntimeError, "scoring failed"):
            retriever.search(self._request())

    def test_existing_request_validation_still_rejects_invalid_k(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 50"):
            self._request(top_k=0)
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            self._request(query="   ")

    def test_non_finite_or_mismatched_scores_are_system_errors(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "non-finite"):
            self._retriever([_chunk("chunk", "쿠폰")], [float("nan")]).search(
                self._request()
            )
        with self.assertRaisesRegex(RuntimeError, "score count"):
            self._retriever([_chunk("chunk", "쿠폰")], []).search(self._request())


if __name__ == "__main__":
    unittest.main()
