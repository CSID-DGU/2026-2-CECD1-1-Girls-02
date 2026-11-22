from __future__ import annotations

import json

from app.ai.models import DraftRequest, Evidence
from app.ai.privacy import redact_pii

PROMPT_VERSION = "voc-draft-v1"


def _evidence_payload(evidence: list[Evidence]) -> list[dict[str, str]]:
    return [{"source_id": item.source_id, "title": redact_pii(item.title), "excerpt": redact_pii(item.excerpt)} for item in evidence]


def build_prompt(request: DraftRequest) -> str:
    """Keep authoritative policy evidence visibly separate from non-authoritative VOC examples."""
    context = {"customer_inquiry_redacted": redact_pii(request.inquiry_text), "official_evidence_authoritative": _evidence_payload(request.official_evidence), "voc_references_non_authoritative": _evidence_payload(request.voc_references)}
    return """You draft Korean customer-service replies for a human agent. This is NOT an auto-send.
Return exactly one JSON object, no Markdown:
{"action":"DRAFT_FOR_REVIEW"|"ESCALATE","draft_text":string|null,"escalation_reason":string|null,"cited_source_ids":[string]}
Rules:
- Only write DRAFT_FOR_REVIEW when authoritative official evidence fully supports it.
- Do not invent policies, prices, dates, eligibility, commitments, or operational actions.
- VOC references are context only; never cite them and never use them as policy authority.
- If evidence is incomplete or the question needs account/order-specific confirmation, use ESCALATE.
- For a draft, cite every official source used. For escalation, draft_text must be null.
- Do not ask for or reveal personal information, order numbers, or staff contact details.

INPUT CONTEXT:
""" + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
