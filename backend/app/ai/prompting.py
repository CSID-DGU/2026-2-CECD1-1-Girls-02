from __future__ import annotations

import json

from app.ai.models import DraftRequest, Evidence
from app.ai.privacy import redact_pii

PROMPT_VERSION = "customer-rag-v2"


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
- Do not invent policies, prices, dates, eligibility, commitments, or operational actions, in draft_text or escalation_reason.
- VOC references are context only; never cite them and never use them as policy authority.
- If evidence is incomplete or the question needs account/order-specific confirmation, use ESCALATE.
- If the customer asks why something happened to their own account, points, coupons, payment, or order, or asks you to check it, use ESCALATE even when a general policy might explain it. You cannot see any customer's records.
- For a draft, cite every official source used. For escalation, draft_text must be null.
- Put source ids only in cited_source_ids. draft_text must not contain source ids, document titles in brackets, URLs, links, or Markdown.
- If action is DRAFT_FOR_REVIEW: draft_text is the reply to the customer, written in polite customer-service Korean (합니다/드립니다체), 2 to 4 sentences; escalation_reason must be null.
- If action is ESCALATE: draft_text must be null. Do not write any reply to the customer. escalation_reason is a short internal note for the agent, one Korean sentence, saying what the official evidence does not cover.
- Do not ask for or reveal personal information, order numbers, or staff contact details.

INPUT CONTEXT:
""" + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
