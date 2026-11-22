from rag.app.evaluation.metrics import compute_metrics
from rag.app.evaluation.schema import GroundTruthCase
from rag.app.retrieval.contracts import KnowledgeScope, SearchFilter, SearchRequest
from rag.app.retrieval.filters import chroma_where


def test_chatbot_cannot_query_voc() -> None:
    try:
        SearchRequest("case", SearchFilter(scope=KnowledgeScope.VOC), caller="chatbot")
    except PermissionError:
        pass
    else:
        raise AssertionError("VOC access must be rejected")


def test_chroma_filter_always_scopes_results() -> None:
    assert chroma_where(SearchFilter(scope=KnowledgeScope.OFFICIAL)) == {"$and": [{"knowledge_scope": "official"}, {"is_active": True}]}


def test_gt_rejects_embedded_source_text() -> None:
    try:
        GroundTruthCase.from_dict({"case_id": "x", "query": "q", "scope": "official", "relevant_document_ids": ["d"], "document_text": "secret"})
    except ValueError:
        pass
    else:
        raise AssertionError("source text must not enter GT")


def test_metrics_cover_required_baseline_measures() -> None:
    result = compute_metrics([(["a", "b"], {"a"}, 10.0, False)])
    assert result.recall_at_5 == result.mrr == result.ndcg_at_5 == 1.0
    assert result.p95_latency_ms == 10.0
