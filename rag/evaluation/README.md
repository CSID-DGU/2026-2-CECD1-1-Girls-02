# Retrieval evaluation protocol

The production baseline is **BGE-M3 embeddings + Chroma dense retrieval** at `top_k=5`.
`SearchRequest` accepts a scope explicitly: `official` and `voc` are separate indexes/metadata domains.
The chatbot is hard-blocked from making a VOC request.

## Ground truth

Keep the authoritative GT JSONL outside version control. Each record contains a stable `case_id`, a reviewed evaluation query, `scope`, and `relevant_document_ids`; an empty ID list is valid only for a reviewed no-evidence case. It must never contain passages, raw internal records, or personal data. Keep the answer key and evaluation queries access-controlled and separate from ingestion corpora to prevent leakage.

Run each candidate over exactly the same frozen GT version and report Recall@5, MRR, nDCG@5, p95 latency, insufficient-evidence detection rate, and its false-positive rate. The report writer stores IDs and aggregates only.

## Adoption gate

Dense is the default. Test Hybrid Search, RRF, or a reranker only as a named candidate against the frozen baseline. Adopt a candidate only if it improves retrieval quality without unacceptable p95 latency or an evidence-safety regression; record the measured delta and error categories (wrong policy, stale document, filter mismatch, insufficient evidence) in the experiment report.
