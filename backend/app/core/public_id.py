"""외부에 노출하는 ID 형식.

DB에는 정수 ID를 저장하고, API에서는 `faq_001`, `inq_001`처럼 접두어를 붙여 내보낸다.
"""
import re

FAQ = "faq"
INQUIRY = "inq"
CONVERSATION = "conv"
MESSAGE = "msg"


def format_public_id(prefix: str, value: int) -> str:
    return f"{prefix}_{value:03d}"


def parse_public_id(prefix: str, raw: str) -> int | None:
    """형식이 맞지 않으면 None을 반환한다."""
    match = re.fullmatch(rf"{re.escape(prefix)}_(\d+)", raw)
    return int(match.group(1)) if match else None