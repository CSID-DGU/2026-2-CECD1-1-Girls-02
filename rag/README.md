# RAG ingestion contract

This directory contains code only. Never commit a real brand name, internal document, original VOC, or PII here. Inputs and generated artifacts must stay in an approved private location outside Git.

| Collection | Permitted source | Retrieval use | Policy authority |
| --- | --- | --- | --- |
| `brand_a_official_knowledge` | approved official FAQ, policy, and notice documents | `DRAFT_ONLY` | yes, subject to human review |
| `brand_a_voc_cases` | approved, de-identified historical VOC | `AGENT_REFERENCE_ONLY` | no — never cite as policy |

Each JSONL input line requires `source_id`, `title`, `text`, `document_version`, and `source_type` (`official` or `voc`). Optional metadata: `source_url`, `published_at`, and `category`. The source type must match the chosen collection.

## Workflow

1. Keep approved raw JSONL in a private path, outside this repository.
2. First run without `--apply`: common direct identifiers are masked and only sanitized chunks, an audit log, and rejection reasons are written.
3. Review those records, then add `--apply` to upsert deterministic IDs and verify every written ID in Chroma.
4. Before promotion, link document and pipeline versions to GT evaluation results: retrieval recall, citation correctness, and harmful-leakage rate.

```powershell
$env:PYTHONPATH = "rag"
python rag/scripts/ingest_jsonl.py --input C:\private\official.jsonl --collection brand_a_official_knowledge --output-dir C:\private\rag-build\official-v1
python rag/scripts/ingest_jsonl.py --input C:\private\official.jsonl --collection brand_a_official_knowledge --output-dir C:\private\rag-build\official-v1 --apply
python -m unittest discover -s rag/tests -v
```

The CLI never copies raw input. Retain its artifact directory under access control with ingestion audit, document version, exclusion reason, evaluation run ID, and deployment approval.

## Rebuild the in-process BM25 index after Chroma ingestion

BM25 reads the same deterministic Chroma IDs, documents, and metadata written by
`ingest_jsonl.py`. Rebuild only after the ingestion command has completed and its
Chroma ID verification has succeeded. `OfficialSearchSettings.from_env()` uses
`CHROMA_HOST`, `CHROMA_PORT`, and `CHROMA_OFFICIAL_COLLECTION`; use
`localhost:8001` on the host or `chroma:8000` inside Compose.

The running application process must own and call the manager. A standalone CLI
would lose its in-memory index when it exits and cannot update another process.

```python
from rag.app.retrieval.bm25 import kiwi_tokenize
from rag.app.retrieval.bm25_chroma import BM25IndexManager, OfficialChromaChunkLoader

loader = OfficialChromaChunkLoader.connect()
bm25 = BM25IndexManager(loader, tokenizer=kiwi_tokenize)
status = bm25.rebuild()
assert status.state == "ready"
assert status.loaded_chunk_count == status.index_chunk_count
```

Operational sequence:

1. Confirm Chroma heartbeat and the official collection.
2. Complete approved FAQ ingestion and ID verification.
3. Call `rebuild()` inside the process that serves BM25 requests.
4. Record `status.snapshot_id`, counts, tokenizer, and completion time.
5. Confirm `state == "ready"` before calling `search()`.
6. Run a non-sensitive Top-K smoke query.

The loader pages through only active, approved, `DRAFT_ONLY` official chunks and
validates the same policy again after loading. It preserves Chroma chunk IDs and
document metadata. A count change during pagination aborts the rebuild. Same-count
concurrent updates cannot be detected without a Chroma transaction, so ingestion
and rebuilding must remain sequential.

Rebuilds are fail-closed: the new index is built separately and swapped only after
validation. During a rebuild, or after a failed rebuild, `search()` raises
`BM25IndexUnavailableError`; an older index is not silently presented as current.
Chroma changes do not automatically update BM25—`rebuild()` must be called again.
