from app.ai.context import RetrievedChunk, build_official_context


def _hit(chunk_id: str, text: str = "공식 안내 내용", **metadata: object) -> RetrievedChunk:
    base = {
        "source_id": "faq:1",
        "title": "FAQ: 멤버십",
        "knowledge_scope": "official",
        "is_active": True,
        "review_status": "APPROVED",
        "allowed_use": "DRAFT_ONLY",
    }
    return RetrievedChunk(chunk_id, text, 0.9, {**base, **metadata})


def test_context_keeps_only_approved_official_chunks():
    result = build_official_context(
        [
            _hit("official-1"),
            _hit("voc-1", knowledge_scope="voc"),
            _hit("pending-1", review_status="PENDING_REVIEW"),
            _hit("inactive-1", is_active=False),
        ]
    )

    assert result.selected_chunk_ids == ["official-1"]
    assert result.skipped_chunk_ids == ["voc-1", "pending-1", "inactive-1"]
    assert result.official_evidence[0].source_id == "faq:1"


def test_context_respects_prompt_budget_and_preserves_rejection_trace():
    result = build_official_context(
        [_hit("first", text="가" * 4), _hit("second", text="나" * 4)],
        max_chunks=5,
        max_characters=6,
    )

    assert result.selected_chunk_ids == ["first"]
    assert result.skipped_chunk_ids == ["second"]


def test_context_rejects_invalid_budget():
    try:
        build_official_context([], max_chunks=0)
    except ValueError as error:
        assert "must be positive" in str(error)
    else:
        raise AssertionError("ValueError was not raised")
