from app.ai.models import DraftAction, DraftRequest, Evidence, EvidenceKind, GenerationStatus
from app.ai.ollama import OllamaGeneration
from app.ai.orchestrator import DraftOrchestrator
from app.ai.prompting import build_prompt


class FakeOllama:
    model = "test-model"

    def __init__(self, text: str) -> None:
        self.text = text

    def generate_json(self, prompt: str) -> OllamaGeneration:
        self.prompt = prompt
        return OllamaGeneration(text=self.text, latency_ms=12)


OFFICIAL = Evidence("policy-1", "Refund policy", "Refunds follow the published policy.", EvidenceKind.OFFICIAL)


def test_order_context_is_escalated_without_model_call() -> None:
    client = FakeOllama("not used")
    result = DraftOrchestrator(client).create_draft(DraftRequest("Order #ABCD1234", [OFFICIAL], has_individual_order_context=True))
    assert result.action is DraftAction.ESCALATE
    assert result.event.status is GenerationStatus.RULE_ESCALATED
    assert not hasattr(client, "prompt")


def test_draft_requires_official_citation() -> None:
    client = FakeOllama('{"action":"DRAFT_FOR_REVIEW","draft_text":"안내드립니다.","escalation_reason":null,"cited_source_ids":["policy-1"]}')
    result = DraftOrchestrator(client).create_draft(DraftRequest("환불은 어떻게 되나요?", [OFFICIAL]))
    assert result.action is DraftAction.DRAFT_FOR_REVIEW
    assert result.event.status is GenerationStatus.COMPLETED


def test_voc_citation_is_rejected() -> None:
    client = FakeOllama('{"action":"DRAFT_FOR_REVIEW","draft_text":"안내드립니다.","escalation_reason":null,"cited_source_ids":["case-1"]}')
    voc = Evidence("case-1", "Old case", "A past agent response", EvidenceKind.VOC_REFERENCE)
    result = DraftOrchestrator(client).create_draft(DraftRequest("문의", [OFFICIAL], [voc]))
    assert result.action is DraftAction.ESCALATE
    assert result.event.status is GenerationStatus.INVALID_MODEL_OUTPUT


def test_prompt_redacts_direct_identifiers() -> None:
    prompt = build_prompt(DraftRequest("메일 foo@example.com, 010-1234-5678, 주문번호: ABCD1234", [OFFICIAL]))
    assert "foo@example.com" not in prompt
    assert "010-1234-5678" not in prompt
    assert "ABCD1234" not in prompt
