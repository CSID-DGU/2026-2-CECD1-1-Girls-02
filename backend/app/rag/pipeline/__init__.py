"""Offline data preparation for the RAG knowledge collections."""

from .normalization import (
    NormalizedRecord,
    NormalizationError,
    normalize_faq_record,
    normalize_voc_record,
)
from .company_sources import (
    PreparedDocument,
    SourceProfile,
    draft_eligible,
    prepare_company_faq_rows,
    prepare_markdown_sections,
)
from .voc import PreparedVocCase, prepare_voc_rows

__all__ = [
    "NormalizedRecord",
    "NormalizationError",
    "normalize_faq_record",
    "normalize_voc_record",
    "PreparedDocument",
    "SourceProfile",
    "draft_eligible",
    "prepare_company_faq_rows",
    "prepare_markdown_sections",
    "PreparedVocCase",
    "prepare_voc_rows",
]
