"""Run the approved RAG golden set against the configured official collection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPOSITORY_ROOT = _BACKEND_ROOT.parent
sys.path.insert(0, str(_REPOSITORY_ROOT))
sys.path.insert(0, str(_BACKEND_ROOT))

from app.ai.rag_evaluation import evaluate_case, parse_case, summarize
from app.ai.retrieval_adapter import OfficialRetrievalAdapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate real official-knowledge retrieval and routing.")
    parser.add_argument("--cases", type=Path, default=Path("backend/tests/fixtures/rag_golden_cases.json"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("backend/artifacts/rag-evaluation.json"))
    args = parser.parse_args()
    if not 1 <= args.top_k <= 50:
        raise SystemExit("--top-k must be between 1 and 50")

    cases = [parse_case(row) for row in json.loads(args.cases.read_text(encoding="utf-8"))]
    search = OfficialRetrievalAdapter.connect()
    results = [evaluate_case(case, search, top_k=args.top_k) for case in cases]
    report = {"top_k": args.top_k, "summary": summarize(results), "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
