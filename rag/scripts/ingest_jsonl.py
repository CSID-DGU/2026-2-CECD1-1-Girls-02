"""Run with: python rag/scripts/ingest_jsonl.py --help"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ingestion import OFFICIAL_COLLECTION, VOC_COLLECTION, build_artifacts, load_jsonl, upsert_chroma, verify_chroma, write_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Mask, chunk, audit, and optionally upsert approved JSONL data.")
    parser.add_argument("--input", required=True, type=Path, help="Private, approved JSONL input outside version control")
    parser.add_argument("--collection", required=True, choices=[OFFICIAL_COLLECTION, VOC_COLLECTION])
    parser.add_argument("--output-dir", required=True, type=Path, help="Private working directory for sanitized artifacts")
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=120)
    parser.add_argument("--apply", action="store_true", help="Actually upsert after artifact generation")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    expected_type = "official" if args.collection == OFFICIAL_COLLECTION else "voc"
    records, rejects = load_jsonl(args.input, expected_type)
    chunks, audit = build_artifacts(records, args.collection, chunk_size=args.chunk_size, overlap=args.overlap)
    write_artifacts(args.output_dir, chunks, audit, rejects)
    if args.apply:
        upsert_chroma(chunks, collection=args.collection, host=args.host, port=args.port)
        verify_chroma([chunk.id for chunk in chunks], collection=args.collection, host=args.host, port=args.port)
    print(f"records={len(records)} chunks={len(chunks)} rejected={len(rejects)} applied={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
