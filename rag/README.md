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
