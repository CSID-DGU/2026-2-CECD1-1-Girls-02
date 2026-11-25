"""Create auditable APPROVED decisions for an explicitly reviewed active source set."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.pipeline.normalization import write_jsonl


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Write decisions only for human-reviewed active draftable documents.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--category", help="Optional category_code filter")
    args = parser.parse_args()

    decisions = []
    for row in _read_jsonl(args.manifest):
        if (
            row.get("raw_status") == "ACTIVE"
            and row.get("review_status") == "PENDING_REVIEW"
            and row.get("allowed_use") == "DRAFT_ONLY"
            and (args.category is None or row.get("category_code") == args.category)
        ):
            decisions.append(
                {
                    "source_id": row["source_id"],
                    "review_status": "APPROVED",
                    "reason": args.reason,
                    "reviewed_by": args.reviewed_by,
                    "reviewed_at": args.reviewed_at,
                }
            )
    write_jsonl(args.output, decisions)
    print(f"approval_decisions={len(decisions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
