from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?82[- ]?)?0?1[0-9][ -]?\d{3,4}[ -]?\d{4}(?!\d)")
_ORDER_LABEL = re.compile(r"(?i)(\b(?:order(?:\s*(?:id|number|no\.?)?)?|reservation)\b|주문(?:번호)?|예약(?:번호)?)\s*[:#]?[\s]*[A-Za-z0-9_-]{4,}")


def redact_pii(text: str) -> str:
    """Remove direct identifiers before any content is sent to a local model."""
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _PHONE.sub("[REDACTED_PHONE]", text)
    return _ORDER_LABEL.sub("[REDACTED_ORDER_REFERENCE]", text)
