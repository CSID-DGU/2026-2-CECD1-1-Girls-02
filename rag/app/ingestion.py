"""Privacy-preserving JSONL ingestion for separated RAG collections."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Literal, Protocol, Sequence

OFFICIAL_COLLECTION = "brand_a_official_knowledge"
VOC_COLLECTION = "brand_a_voc_cases"
ALLOWED_COLLECTIONS = {OFFICIAL_COLLECTION, VOC_COLLECTION}
OFFICIAL_USAGE = "DRAFT_ONLY"
VOC_USAGE = "AGENT_REFERENCE_ONLY"

_PII_PATTERNS = (
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("phone", re.compile(r"(?<!\d)(?:\+82[- ]?)?0?1[0-9][- ]?\d{3,4}[- ]?\d{4}(?!\d)")),
    ("resident_id", re.compile(r"(?<!\d)\d{6}[- ]?[1-4]\d{6}(?!\d)")),
    ("card", re.compile(r"(?<!\d)(?:\d{4}[- ]?){3}\d{4}(?!\d)")),
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+|\n+")


class IngestionError(ValueError):
    """Raised when a record violates the ingestion contract."""


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    title: str
    text: str
    document_version: str
    source_type: Literal["official", "voc"]
    source_url: str | None = None
    published_at: str | None = None
    category: str | None = None
    document_id: str | None = None
    raw_status: str | None = None
    review_status: str | None = None
    allowed_use: str | None = None
    authority_level: str | None = None
    document_type: str | None = None
    business_domain: str | None = None


class Embedder(Protocol):
    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict[str, str | int]


def _required(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IngestionError(f"missing or empty {name}")
    return value.strip()


def parse_record(payload: dict[str, Any], expected_source_type: str) -> SourceRecord:
    """Validate one approved input record without retaining its raw payload."""
    source_type = _required(payload.get("source_type"), "source_type")
    if source_type not in {"official", "voc"}:
        raise IngestionError("source_type must be official or voc")
    if source_type != expected_source_type:
        raise IngestionError("record source_type does not match selected collection")
    return SourceRecord(
        source_id=_required(payload.get("source_id"), "source_id"),
        title=_required(payload.get("title"), "title"),
        text=_required(payload.get("text"), "text"),
        document_version=_required(payload.get("document_version"), "document_version"),
        source_type=source_type,  # type: ignore[arg-type]
        source_url=payload.get("source_url"),
        published_at=payload.get("published_at"),
        category=payload.get("category"),
        document_id=payload.get("document_id"),
        raw_status=payload.get("raw_status"),
        review_status=payload.get("review_status"),
        allowed_use=payload.get("allowed_use"),
        authority_level=payload.get("authority_level"),
        document_type=payload.get("doc_type"),
        business_domain=payload.get("business_domain"),
    )


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace common direct identifiers and return counts by identifier class."""
    counts: dict[str, int] = {}
    masked = text
    for name, pattern in _PII_PATTERNS:
        masked, count = pattern.subn(f"[{name.upper()}_REDACTED]", masked)
        if count:
            counts[name] = count
    return masked, counts


def normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\r\n?", "\n", text)).strip()


def chunk_text(text: str, *, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Create bounded, deterministic chunks while preferring sentence boundaries."""
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError("chunk_size must be positive and overlap smaller than chunk_size")
    text = normalize_text(text)
    if not text:
        return []
    sentences = [part.strip() for part in _SENTENCE_BOUNDARY.split(text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(sentence), chunk_size - overlap):
                piece = sentence[start : start + chunk_size]
                if piece:
                    chunks.append(piece)
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > chunk_size:
            chunks.append(current)
            current = current[-overlap:] + " " + sentence if overlap else sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def make_chunks(record: SourceRecord, collection: str, *, chunk_size: int = 800, overlap: int = 120) -> tuple[list[Chunk], dict[str, int]]:
    if collection not in ALLOWED_COLLECTIONS:
        raise IngestionError("unsupported collection")
    expected = "official" if collection == OFFICIAL_COLLECTION else "voc"
    if record.source_type != expected:
        raise IngestionError("source type and collection are incompatible")
    masked, pii_counts = mask_pii(record.text)
    usage = OFFICIAL_USAGE if expected == "official" else VOC_USAGE
    chunks = []
    for index, content in enumerate(chunk_text(masked, chunk_size=chunk_size, overlap=overlap)):
        identity = f"{collection}:{record.source_id}:{record.document_version}:{index}:{content}"
        metadata: dict[str, str | int] = {
            "collection": collection, "source_id": record.source_id,
            "document_version": record.document_version, "source_type": record.source_type,
            "usage_scope": usage, "chunk_index": index, "title": record.title,
            "content_sha256": sha256(content.encode("utf-8")).hexdigest(),
            "document_id": record.document_id or record.source_id,
            "knowledge_scope": "official" if expected == "official" else "voc",
            "is_active": record.raw_status == "ACTIVE",
            "review_status": record.review_status or "UNREVIEWED",
            "allowed_use": record.allowed_use or usage,
        }
        for key in ("authority_level", "document_type", "business_domain"):
            value = getattr(record, key)
            if isinstance(value, str) and value.strip():
                metadata[key] = value.strip()
        for key in ("source_url", "published_at", "category"):
            value = getattr(record, key)
            if isinstance(value, str) and value.strip():
                metadata[key] = value.strip()
        chunks.append(Chunk(id=sha256(identity.encode("utf-8")).hexdigest(), text=content, metadata=metadata))
    return chunks, pii_counts


def load_jsonl(path: Path, expected_source_type: str) -> tuple[list[SourceRecord], list[dict[str, str | int]]]:
    records: list[SourceRecord] = []
    rejects: list[dict[str, str | int]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(parse_record(json.loads(line), expected_source_type))
            except (json.JSONDecodeError, IngestionError) as error:
                rejects.append({"line": line_number, "reason": str(error)})
    return records, rejects


def build_artifacts(records: Iterable[SourceRecord], collection: str, *, chunk_size: int = 800, overlap: int = 120) -> tuple[list[Chunk], list[dict[str, str | int]]]:
    chunks: list[Chunk] = []
    audit: list[dict[str, str | int]] = []
    for record in records:
        produced, pii_counts = make_chunks(record, collection, chunk_size=chunk_size, overlap=overlap)
        chunks.extend(produced)
        audit.append({"source_id": record.source_id, "document_version": record.document_version, "chunks": len(produced), "pii_matches": sum(pii_counts.values())})
    return chunks, audit


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_artifacts(output_dir: Path, chunks: list[Chunk], audit: list[dict[str, str | int]], rejects: list[dict[str, str | int]]) -> None:
    """Write sanitized chunks and traceability records; never copy the raw source."""
    timestamp = datetime.now(UTC).isoformat()
    write_jsonl(output_dir / "chunks.jsonl", ({"id": c.id, "text": c.text, "metadata": c.metadata} for c in chunks))
    write_jsonl(output_dir / "ingestion_audit.jsonl", ({**row, "processed_at": timestamp} for row in audit))
    write_jsonl(output_dir / "rejected_records.jsonl", rejects)


def _assert_indexable(chunks: list[Chunk], collection: str) -> None:
    """Defence in depth: the approved file name is not an authorization boundary."""
    if collection != OFFICIAL_COLLECTION:
        raise IngestionError("VOC indexing is disabled in the initial customer-answer baseline")
    for chunk in chunks:
        metadata = chunk.metadata
        if (
            metadata.get("knowledge_scope") != "official"
            or metadata.get("is_active") is not True
            or metadata.get("review_status") != "APPROVED"
            or metadata.get("allowed_use") != OFFICIAL_USAGE
        ):
            raise IngestionError("only active, approved, DRAFT_ONLY official chunks may be indexed")


def upsert_chroma(chunks: list[Chunk], *, collection: str, embedder: Embedder, host: str = "localhost", port: int = 8001) -> None:
    """Index BGE-M3 vectors and remove superseded versions for each logical document."""
    if collection not in ALLOWED_COLLECTIONS:
        raise IngestionError("unsupported collection")
    _assert_indexable(chunks, collection)
    try:
        import chromadb  # type: ignore[import-not-found]
    except ImportError as error:
        raise RuntimeError("Install chromadb before using --apply") from error
    target = chromadb.HttpClient(host=host, port=port).get_or_create_collection(name=collection)
    versions = {(str(item.metadata["document_id"]), str(item.metadata["document_version"])) for item in chunks}
    for document_id, current_version in versions:
        existing = target.get(where={"document_id": document_id}, include=["metadatas"])
        stale_ids = [
            item_id
            for item_id, metadata in zip(existing.get("ids", []), existing.get("metadatas", []), strict=True)
            if metadata and str(metadata.get("document_version")) != current_version
        ]
        if stale_ids:
            target.delete(ids=stale_ids)
    for start in range(0, len(chunks), 100):
        batch = chunks[start : start + 100]
        documents = [item.text for item in batch]
        embeddings = embedder.encode(documents)
        target.upsert(
            ids=[item.id for item in batch],
            documents=documents,
            embeddings=list(embeddings),
            metadatas=[item.metadata for item in batch],
        )


def verify_chroma(expected_ids: list[str], *, collection: str, host: str = "localhost", port: int = 8001) -> None:
    try:
        import chromadb  # type: ignore[import-not-found]
    except ImportError as error:
        raise RuntimeError("Install chromadb before using --apply") from error
    found = chromadb.HttpClient(host=host, port=port).get_collection(collection).get(ids=expected_ids, include=[])["ids"]
    if set(found) != set(expected_ids):
        raise RuntimeError("Chroma verification failed: one or more chunk IDs are missing")
