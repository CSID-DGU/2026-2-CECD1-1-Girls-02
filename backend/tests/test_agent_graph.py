import importlib.util
import unittest

from app.ai.agent import build_rag_agent_graph
from app.ai.context import RetrievedChunk
from app.ai.models import DraftAction, GenerationStatus
from app.ai.ollama import OllamaGeneration
from app.ai.orchestrator import DraftOrchestrator
from app.ai.retrieval_adapter import OfficialRetrievalUnavailable


class FakeSearch:
    def __init__(self, hits: list[RetrievedChunk]) -> None:
        self.hits = hits
        self.calls = 0

    def search_official(self, query: str, *, top_k: int) -> list[RetrievedChunk]:
        self.calls += 1
        self.query = query
        self.top_k = top_k
        return self.hits


class FakeOllama:
    model = "test-model"

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def generate_json(self, prompt: str) -> OllamaGeneration:
        self.calls += 1
        self.prompt = prompt
        return OllamaGeneration(text=self.text, latency_ms=12)


class UnavailableSearch:
    def search_official(self, query: str, *, top_k: int) -> list[RetrievedChunk]:
        raise OfficialRetrievalUnavailable("Chroma is unavailable")


def _official_hit() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="membership-1",
        text="멤버십 등급별 혜택은 공식 안내를 따릅니다.",
        score=0.9,
        metadata={
            "source_id": "faq:membership-1",
            "title": "FAQ: 멤버십 혜택",
            "knowledge_scope": "official",
            "is_active": True,
            "review_status": "APPROVED",
            "allowed_use": "DRAFT_ONLY",
        },
    )


@unittest.skipUnless(importlib.util.find_spec("langgraph"), "langgraph is not installed")
class AgentGraphTests(unittest.TestCase):
    def _graph(self, search: FakeSearch, client: FakeOllama):
        return build_rag_agent_graph(search=search, orchestrator=DraftOrchestrator(client))

    def test_general_question_retrieves_official_context_then_generates_draft(self):
        search = FakeSearch([_official_hit()])
        client = FakeOllama(
            '{"action":"DRAFT_FOR_REVIEW","draft_text":"멤버십 혜택을 안내드립니다.",'
            '"escalation_reason":null,"cited_source_ids":["faq:membership-1"]}'
        )
        result = self._graph(search, client).invoke({"inquiry_text": "멤버십 혜택이 궁금해요."})

        self.assertIs(result["result"].action, DraftAction.DRAFT_FOR_REVIEW)
        self.assertEqual(search.calls, 1)
        self.assertEqual(client.calls, 1)
        self.assertEqual(result["context"].selected_chunk_ids, ["membership-1"])

    def test_order_inquiry_bypasses_search_and_model_then_escalates(self):
        search = FakeSearch([_official_hit()])
        client = FakeOllama("not used")
        result = self._graph(search, client).invoke(
            {"inquiry_text": "주문 상태를 확인해주세요.", "has_individual_order_context": True}
        )

        self.assertIs(result["result"].action, DraftAction.ESCALATE)
        self.assertIs(result["result"].event.status, GenerationStatus.RULE_ESCALATED)
        self.assertEqual(search.calls, 0)
        self.assertEqual(client.calls, 0)

    def test_personal_account_question_bypasses_search_and_model_then_escalates(self):
        search = FakeSearch([_official_hit()])
        client = FakeOllama("not used")
        result = self._graph(search, client).invoke(
            {"inquiry_text": "제 계정 포인트가 어제 사라졌는데 확인해 주세요."}
        )

        self.assertIs(result["result"].action, DraftAction.ESCALATE)
        self.assertEqual(search.calls, 0)
        self.assertEqual(client.calls, 0)

    def test_voc_or_pending_hits_cannot_become_llm_context(self):
        official = _official_hit()
        voc = RetrievedChunk(official.chunk_id, official.text, official.score, {**official.metadata, "knowledge_scope": "voc"})
        pending = RetrievedChunk(official.chunk_id + "-pending", official.text, official.score, {**official.metadata, "review_status": "PENDING_REVIEW"})
        search = FakeSearch([voc, pending])
        client = FakeOllama("not used")
        result = self._graph(search, client).invoke({"inquiry_text": "멤버십 혜택이 궁금해요."})

        self.assertIs(result["result"].action, DraftAction.ESCALATE)
        self.assertIs(result["result"].event.status, GenerationStatus.RULE_ESCALATED)
        self.assertEqual(result["context"].official_evidence, [])
        self.assertEqual(client.calls, 0)

    def test_invalid_model_output_falls_back_to_escalation(self):
        search = FakeSearch([_official_hit()])
        client = FakeOllama(
            '{"action":"DRAFT_FOR_REVIEW","draft_text":"근거 없는 답변",'
            '"escalation_reason":null,"cited_source_ids":["unknown"]}'
        )
        result = self._graph(search, client).invoke({"inquiry_text": "멤버십 혜택이 궁금해요."})

        self.assertIs(result["result"].action, DraftAction.ESCALATE)
        self.assertIs(result["result"].event.status, GenerationStatus.INVALID_MODEL_OUTPUT)
        self.assertEqual(search.calls, 1)
        self.assertEqual(client.calls, 1)

    def test_retrieval_outage_escalates_without_calling_the_model(self):
        client = FakeOllama("not used")
        result = self._graph(UnavailableSearch(), client).invoke(
            {"inquiry_text": "멤버십 혜택이 궁금해요."}
        )

        self.assertIs(result["result"].action, DraftAction.ESCALATE)
        self.assertIs(result["result"].event.status, GenerationStatus.RULE_ESCALATED)
        self.assertIn("공식 지식 검색", result["result"].escalation_reason)
        self.assertEqual(client.calls, 0)


if __name__ == "__main__":
    unittest.main()
