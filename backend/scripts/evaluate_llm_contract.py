"""Run synthetic LLM contract cases against a configured Ollama model."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.evaluation import evaluate_case, parse_case
from app.ai.ollama import OllamaClient, OllamaError
from app.ai.prompting import PROMPT_VERSION
from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Evaluate the local LLM response contract.")
    parser.add_argument("--cases", type=Path, default=Path("tests/fixtures/llm_contract_cases.json"))
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("artifacts/llm-evaluation.json"))
    parser.add_argument("--base-url", default=settings.ollama_base_url)
    parser.add_argument("--model", default=settings.ollama_model)
    parser.add_argument("--timeout", type=float, default=settings.ollama_timeout_seconds)
    args = parser.parse_args()
    if args.runs <= 0:
        raise SystemExit("--runs must be positive")
    cases = [parse_case(row) for row in json.loads(args.cases.read_text(encoding="utf-8"))]
    client = OllamaClient(args.base_url, args.model, args.timeout)
    results = []
    for run in range(1, args.runs + 1):
        for case in cases:
            try:
                results.append({"run": run, **evaluate_case(case, client)})
            except OllamaError:
                results.append({"run": run, "case_id": case.case_id, "expected_action": case.expected_action.value, "actual_action": None, "passed": False, "failures": ["model_error"], "latency_ms": None, "prompt_tokens": None, "completion_tokens": None})
    latencies = [row["latency_ms"] for row in results if isinstance(row["latency_ms"], int)]
    by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in results:
        by_case[str(row["case_id"])].append(row)
    stability = [
        {
            "case_id": case_id,
            "actions": sorted({str(row["actual_action"]) for row in rows}),
            "passed_runs": sum(bool(row["passed"]) for row in rows),
            "total_runs": len(rows),
        }
        for case_id, rows in sorted(by_case.items())
    ]
    report = {
        "prompt_version": PROMPT_VERSION,
        "model": args.model,
        "runs": args.runs,
        "total": len(results),
        "passed": sum(row["passed"] for row in results),
        "pass_rate": sum(row["passed"] for row in results) / len(results) if results else 0,
        "latency_median_ms": statistics.median(latencies) if latencies else None,
        "case_stability": stability,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("prompt_version", "model", "total", "passed", "pass_rate", "latency_median_ms")}, ensure_ascii=False))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
