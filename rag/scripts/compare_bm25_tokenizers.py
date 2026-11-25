"""Compare basic and Kiwi tokenization on local active company FAQs only."""

from __future__ import annotations

import argparse
from collections import Counter
from importlib.metadata import version
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_bm25_tokenization import _load_faq, _paraphrase, _ratio, _required_text, analyze
from rag.app.ingestion import Chunk
from rag.app.retrieval.bm25 import (
    Tokenizer,
    basic_tokenize,
    build_bm25_index,
    kiwi_tokenize,
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _token_length_distribution(tokens: list[str]) -> dict[str, int]:
    counts = Counter(len(token) for token in tokens)
    return {str(length): counts[length] for length in sorted(counts)}


def _preservation(tokens: list[str]) -> dict[str, object]:
    negative_stems = ("안", "못", "않", "없", "불가", "제한")
    return {
        "digit_token_occurrences": sum(any(character.isdigit() for character in token) for token in tokens),
        "ascii_token_occurrences": sum(any("a" <= character <= "z" for character in token) for token in tokens),
        "coupon_token_occurrences": sum("쿠폰" in token for token in tokens),
        "negative_or_restriction_token_occurrences": sum(
            any(stem in token for stem in negative_stems) for token in tokens
        ),
        "product_name_validation": "unavailable_without_product_name_ground_truth",
        "proper_name_validation": "unavailable_without_labeled_proper_names",
    }


def _benchmark(tokenizer: Tokenizer, texts: list[str], repetitions: int = 5) -> dict[str, object]:
    durations: list[float] = []
    produced = 0
    for _ in range(repetitions):
        started = perf_counter()
        produced = sum(len(tokenizer(text)) for text in texts)
        durations.append((perf_counter() - started) * 1000)
    return {
        "repetitions": repetitions,
        "token_count_last_run": produced,
        "median_ms": round(statistics.median(durations), 4),
        "min_ms": round(min(durations), 4),
        "max_ms": round(max(durations), 4),
        "scope": "warm_process_tokenization_only",
    }


def compare(
    rows: list[dict[str, Any]], manual_queries: list[dict[str, Any]] | None = None
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    active = [row for row in rows if row.get("active") is True]
    texts = [
        text
        for row in active
        for text in (_required_text(row, "title"), _required_text(row, "content"))
    ]

    # Initialize Kiwi outside the warm processing benchmark and record that cost separately.
    kiwi_started = perf_counter()
    kiwi_tokenize("토크나이저 초기화")
    kiwi_initialization_ms = (perf_counter() - kiwi_started) * 1000

    basic_summary, _, _ = analyze(rows, tokenizer=basic_tokenize)
    kiwi_summary, _, _ = analyze(rows, tokenizer=kiwi_tokenize)
    all_basic_tokens = [token for text in texts for token in basic_tokenize(text)]
    all_kiwi_tokens = [token for text in texts for token in kiwi_tokenize(text)]

    per_faq: list[dict[str, object]] = []
    cases: list[dict[str, object]] = []
    chunks: list[Chunk] = []
    documents_by_source_id: dict[str, str] = {}
    for row in active:
        source_id = f"faq:{_required_text(row, 'id')}"
        question = _required_text(row, "title")
        answer = _required_text(row, "content")
        document = f"{question}\n{answer}"
        documents_by_source_id[source_id] = document
        basic_question = basic_tokenize(question)
        basic_answer = basic_tokenize(answer)
        kiwi_question = kiwi_tokenize(question)
        kiwi_answer = kiwi_tokenize(answer)
        per_faq.append(
            {
                "source_id": source_id,
                "basic": {
                    "document_token_count": len(basic_question) + len(basic_answer),
                    "question_to_answer_match_ratio": round(_ratio(basic_question, basic_answer), 4),
                },
                "kiwi": {
                    "document_token_count": len(kiwi_question) + len(kiwi_answer),
                    "question_to_answer_match_ratio": round(_ratio(kiwi_question, kiwi_answer), 4),
                },
            }
        )
        chunks.append(Chunk(id=source_id, text=document, metadata={"active": 1}))

        changed = _paraphrase(question)
        if changed:
            query, rule = changed
            case: dict[str, object] = {
                "source_id": source_id,
                "query": query,
                "rule": rule,
                "generation": "rule_based_not_human_validated",
            }
            for name, tokenizer in (("basic", basic_tokenize), ("kiwi", kiwi_tokenize)):
                query_tokens = tuple(tokenizer(query))
                document_tokens = tuple(tokenizer(document))
                vocabulary = set(document_tokens)
                case[name] = {
                    "match_ratio": round(_ratio(query_tokens, document_tokens), 4),
                    "unmatched_tokens": [token for token in query_tokens if token not in vocabulary],
                }
            cases.append(case)

    manual_queries = manual_queries or []
    invalid_manual_queries = 0
    for item in manual_queries:
        query = item.get("query")
        source_id = item.get("relevant_source_id")
        if not isinstance(query, str) or not query.strip():
            continue
        if not isinstance(source_id, str) or source_id not in documents_by_source_id:
            invalid_manual_queries += 1
            continue
        case = {
            "case_id": item.get("case_id", ""),
            "source_id": source_id,
            "query": query.strip(),
            "generation": "human_authored",
        }
        for name, tokenizer in (("basic", basic_tokenize), ("kiwi", kiwi_tokenize)):
            query_tokens = tuple(tokenizer(query))
            document_tokens = tuple(tokenizer(documents_by_source_id[source_id]))
            vocabulary = set(document_tokens)
            case[name] = {
                "match_ratio": round(_ratio(query_tokens, document_tokens), 4),
                "unmatched_tokens": [token for token in query_tokens if token not in vocabulary],
            }
        cases.append(case)

    basic_index = build_bm25_index(chunks, tokenizer=basic_tokenize)
    kiwi_index = build_bm25_index(chunks, tokenizer=kiwi_tokenize)
    rule_cases = [case for case in cases if case["generation"] == "rule_based_not_human_validated"]
    human_cases = [case for case in cases if case["generation"] == "human_authored"]
    basic_case_ratios = [float(case["basic"]["match_ratio"]) for case in rule_cases]  # type: ignore[index]
    kiwi_case_ratios = [float(case["kiwi"]["match_ratio"]) for case in rule_cases]  # type: ignore[index]
    summary: dict[str, object] = {
        "scope": {"total": len(rows), "active": len(active), "inactive_excluded": len(rows) - len(active)},
        "manual_query_evaluation": {
            "filled_queries": len(human_cases),
            "invalid_or_unknown_source_ids": invalid_manual_queries,
            "used": bool(human_cases),
            "reason": "used only when query and known relevant_source_id are both present",
        },
        "tokenizers": {
            "basic": {
                "average_tokens_per_faq": basic_summary["token_counts"]["per_faq_mean"],  # type: ignore[index]
                "unique_tokens": basic_summary["token_counts"]["unique"],  # type: ignore[index]
                "mean_token_character_length": basic_summary["token_counts"]["mean_token_character_length"],  # type: ignore[index]
                "token_length_distribution": _token_length_distribution(all_basic_tokens),
                "original_question_to_answer_mean_match_ratio": basic_summary["question_answer_overlap"]["mean_question_token_match_ratio"],  # type: ignore[index]
                "rule_paraphrase_to_faq_mean_match_ratio": round(statistics.fmean(basic_case_ratios), 4),
                "rule_paraphrase_fully_matched": sum(value == 1 for value in basic_case_ratios),
                "preservation": _preservation(all_basic_tokens),
                "timing": _benchmark(basic_tokenize, texts),
            },
            "kiwi": {
                "version": version("kiwipiepy"),
                "kept_pos_prefixes": ["N", "V", "M", "XR", "XSN", "XSV", "XSA", "SL", "SH", "SN"],
                "excluded_tag_groups": [
                    "J* particles", "E* endings", "symbol tags except retained SH/SN"
                ],
                "average_tokens_per_faq": kiwi_summary["token_counts"]["per_faq_mean"],  # type: ignore[index]
                "unique_tokens": kiwi_summary["token_counts"]["unique"],  # type: ignore[index]
                "mean_token_character_length": kiwi_summary["token_counts"]["mean_token_character_length"],  # type: ignore[index]
                "token_length_distribution": _token_length_distribution(all_kiwi_tokens),
                "original_question_to_answer_mean_match_ratio": kiwi_summary["question_answer_overlap"]["mean_question_token_match_ratio"],  # type: ignore[index]
                "rule_paraphrase_to_faq_mean_match_ratio": round(statistics.fmean(kiwi_case_ratios), 4),
                "rule_paraphrase_fully_matched": sum(value == 1 for value in kiwi_case_ratios),
                "preservation": _preservation(all_kiwi_tokens),
                "timing": {
                    **_benchmark(kiwi_tokenize, texts),
                    "initialization_ms_separate": round(kiwi_initialization_ms, 4),
                },
            },
        },
        "rule_based_paraphrase_cases": len(rule_cases),
        "human_authored_query_cases": len(human_cases),
        "indexes_built": {"basic_documents": len(basic_index), "kiwi_documents": len(kiwi_index)},
        "limitations": [
            "token overlap is not BM25 retrieval quality",
            "rule paraphrases are not human-validated",
            "product and coupon names have no labeled preservation ground truth",
        ],
    }
    return summary, per_faq, cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Basic and Kiwi BM25 tokenization")
    parser.add_argument("--input", type=Path, default=Path("data/faq.json"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/rag-build/bm25-tokenizer-comparison")
    )
    parser.add_argument(
        "--manual-queries",
        type=Path,
        default=Path("data/rag-build/bm25-tokenization/manual_query_evaluation_template.jsonl"),
    )
    args = parser.parse_args()
    manual_queries = (
        [json.loads(line) for line in args.manual_queries.read_text(encoding="utf-8").splitlines() if line.strip()]
        if args.manual_queries.exists()
        else []
    )
    summary, per_faq, cases = compare(_load_faq(args.input), manual_queries)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "tokenizer_comparison_summary.json", summary)
    _write_jsonl(args.output_dir / "tokenizer_comparison_per_faq.jsonl", per_faq)
    _write_jsonl(args.output_dir / "tokenizer_comparison_cases.jsonl", cases)
    print(
        f"active={summary['scope']['active']} cases={len(cases)} "  # type: ignore[index]
        f"output={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
