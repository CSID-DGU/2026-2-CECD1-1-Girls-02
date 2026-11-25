"""Analyze the baseline BM25 tokenizer against a local company FAQ export.

The script reads only local data and writes aggregate/diagnostic artifacts. It
does not approve records, build a search index, or connect to Chroma.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rag.app.retrieval.bm25 import Tokenizer, basic_tokenize


_KOREAN_SUFFIXES = (
    "으로", "에서", "에게", "까지", "부터", "처럼", "보다", "하고", "이며",
    "은", "는", "이", "가", "을", "를", "에", "의", "와", "과", "도", "로",
    "입니다", "인가요", "나요", "어요", "아요", "습니다", "세요", "까요",
)
_PARAPHRASE_ENDINGS = (
    ("되나요", "돼요"),
    ("있나요", "있어요"),
    ("인가요", "이에요"),
    ("하나요", "해요"),
    ("되어요", "돼요"),
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _load_faq(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise ValueError("FAQ input must contain an items array of objects")
    return items


def _required_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"FAQ {key} must be a non-empty string")
    return value.strip()


def _ratio(query_tokens: tuple[str, ...], document_tokens: tuple[str, ...]) -> float:
    if not query_tokens:
        return 0.0
    document_vocabulary = set(document_tokens)
    return sum(token in document_vocabulary for token in query_tokens) / len(query_tokens)


def _paraphrase(question: str) -> tuple[str, str] | None:
    stem = question.rstrip().rstrip("?.!")
    for source, replacement in _PARAPHRASE_ENDINGS:
        if stem.endswith(source):
            return stem[: -len(source)] + replacement + "?", f"{source}->{replacement}"
    return None


def analyze(
    rows: list[dict[str, Any]], *, tokenizer: Tokenizer = basic_tokenize
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    active = [row for row in rows if row.get("active") is True]
    inactive = [row for row in rows if row.get("active") is False]
    frequencies: Counter[str] = Counter()
    per_faq: list[dict[str, object]] = []
    paraphrases: list[dict[str, object]] = []
    all_token_lengths: list[int] = []
    suffix_tokens: Counter[str] = Counter()
    long_tokens: Counter[str] = Counter()
    numeric_tokens: Counter[str] = Counter()
    ascii_tokens: Counter[str] = Counter()

    for row in active:
        source_id = f"faq:{_required_text(row, 'id')}"
        question = _required_text(row, "title")
        answer = _required_text(row, "content")
        question_tokens = tuple(tokenizer(question))
        answer_tokens = tuple(tokenizer(answer))
        document_tokens = question_tokens + answer_tokens
        frequencies.update(document_tokens)
        all_token_lengths.extend(map(len, document_tokens))
        for token in document_tokens:
            if len(token) >= 20:
                long_tokens[token] += 1
            if any(character.isdigit() for character in token):
                numeric_tokens[token] += 1
            if any("a" <= character <= "z" for character in token):
                ascii_tokens[token] += 1
            if any(len(token) > len(suffix) and token.endswith(suffix) for suffix in _KOREAN_SUFFIXES):
                suffix_tokens[token] += 1

        per_faq.append(
            {
                "source_id": source_id,
                "question_token_count": len(question_tokens),
                "answer_token_count": len(answer_tokens),
                "document_token_count": len(document_tokens),
                "question_to_answer_common_token_count": sum(
                    token in set(answer_tokens) for token in question_tokens
                ),
                "question_to_answer_match_ratio": round(_ratio(question_tokens, answer_tokens), 4),
            }
        )

        changed = _paraphrase(question)
        if changed:
            query, rule = changed
            query_tokens = tuple(tokenizer(query))
            vocabulary = set(document_tokens)
            paraphrases.append(
                {
                    "source_id": source_id,
                    "generation": "rule_based_not_human_validated",
                    "rule": rule,
                    "query": query,
                    "query_tokens": query_tokens,
                    "common_tokens": [token for token in query_tokens if token in vocabulary],
                    "unmatched_tokens": [token for token in query_tokens if token not in vocabulary],
                    "query_to_faq_match_ratio": round(_ratio(query_tokens, document_tokens), 4),
                }
            )

    faq_token_counts = [int(item["document_token_count"]) for item in per_faq]
    original_ratios = [float(item["question_to_answer_match_ratio"]) for item in per_faq]
    paraphrase_ratios = [float(item["query_to_faq_match_ratio"]) for item in paraphrases]
    summary: dict[str, object] = {
        "scope": "active_company_faq_only",
        "record_counts": {
            "total": len(rows), "active_analyzed": len(active), "inactive_excluded": len(inactive)
        },
        "token_counts": {
            "total_occurrences": sum(frequencies.values()),
            "unique": len(frequencies),
            "per_faq_min": min(faq_token_counts, default=0),
            "per_faq_max": max(faq_token_counts, default=0),
            "per_faq_mean": round(statistics.fmean(faq_token_counts), 4) if faq_token_counts else 0,
            "empty_faqs": sum(count == 0 for count in faq_token_counts),
            "mean_token_character_length": round(statistics.fmean(all_token_lengths), 4) if all_token_lengths else 0,
            "tokens_at_least_20_characters": sum(long_tokens.values()),
        },
        "frequent_tokens": frequencies.most_common(30),
        "heuristic_attached_particle_or_ending": {
            "occurrences": sum(suffix_tokens.values()),
            "unique": len(suffix_tokens),
            "examples": suffix_tokens.most_common(30),
            "note": "suffix heuristic only; not a morphological analysis",
        },
        "expression_preservation": {
            "tokens_containing_digits": numeric_tokens.most_common(30),
            "tokens_containing_ascii": ascii_tokens.most_common(30),
            "long_token_examples": long_tokens.most_common(30),
            "product_name_identification": "not available without product-name labels",
        },
        "question_answer_overlap": {
            "cases": len(original_ratios),
            "mean_question_token_match_ratio": round(statistics.fmean(original_ratios), 4) if original_ratios else 0,
            "median_question_token_match_ratio": round(statistics.median(original_ratios), 4) if original_ratios else 0,
            "zero_overlap_cases": sum(ratio == 0 for ratio in original_ratios),
            "comparison": "original question tokens against answer tokens only",
        },
        "rule_based_paraphrase_overlap": {
            "cases": len(paraphrase_ratios),
            "mean_query_token_match_ratio": round(statistics.fmean(paraphrase_ratios), 4) if paraphrase_ratios else 0,
            "median_query_token_match_ratio": round(statistics.median(paraphrase_ratios), 4) if paraphrase_ratios else 0,
            "zero_overlap_cases": sum(ratio == 0 for ratio in paraphrase_ratios),
            "fully_matched_cases": sum(ratio == 1 for ratio in paraphrase_ratios),
            "warning": "mechanically generated and not human-validated for semantic equivalence",
        },
    }
    return summary, per_faq, paraphrases


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze basic_tokenize against local FAQ data")
    parser.add_argument("--input", type=Path, default=Path("data/faq.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/rag-build/bm25-tokenization"))
    args = parser.parse_args()

    rows = _load_faq(args.input)
    summary, per_faq, paraphrases = analyze(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "summary.json", summary)
    _write_jsonl(args.output_dir / "per_faq_stats.jsonl", per_faq)
    _write_jsonl(args.output_dir / "token_mismatch_cases.jsonl", paraphrases)
    template = (
        {
            "case_id": f"manual-{index:02d}",
            "query": "",
            "relevant_source_id": item["source_id"],
            "review_status": "NEEDS_HUMAN_QUERY",
            "notes": "",
        }
        for index, item in enumerate(per_faq[:25], start=1)
    )
    _write_jsonl(args.output_dir / "manual_query_evaluation_template.jsonl", template)
    counts = summary["record_counts"]
    tokens = summary["token_counts"]
    print(
        f"analyzed={counts['active_analyzed']} inactive_excluded={counts['inactive_excluded']} "
        f"tokens={tokens['total_occurrences']} unique={tokens['unique']} "
        f"paraphrase_cases={len(paraphrases)} output={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
