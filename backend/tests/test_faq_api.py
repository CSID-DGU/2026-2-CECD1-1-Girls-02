from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Brand, Faq, FaqCategory

HEADERS = {"X-Brand-Code": "brand_a"}


def _seed(db: Session) -> dict[str, int]:
    brand = Brand(code="brand_a", name="브랜드 A")
    other = Brand(code="brand_b", name="브랜드 B")
    db.add_all([brand, other])
    db.flush()

    event = FaqCategory(
        brand_id=brand.id,
        code="faq_event",
        name="이벤트 및 할인",
        sort_order=0,
    )
    membership = FaqCategory(
        brand_id=brand.id,
        code="faq_membership",
        name="멤버십",
        sort_order=1,
    )
    hidden_category = FaqCategory(
        brand_id=brand.id,
        code="faq_hidden",
        name="숨김",
        sort_order=2,
        is_active=False,
    )
    other_category = FaqCategory(
        brand_id=other.id,
        code="faq_event",
        name="다른 브랜드",
        sort_order=0,
    )

    db.add_all([
        event, membership, hidden_category, other_category
    ])
    db.flush()

    rows = {
        "discount": Faq(
            brand_id=brand.id,
            category_id=event.id,
            question="할인 혜택은 어떻게 받을 수 있나요?",
            answer="멤버십, 제휴 할인으로 받을 수 있습니다.",
        ),
        "grade": Faq(
            brand_id=brand.id,
            category_id=membership.id,
            question="등급 기준이 궁금해요",
            answer="6개월 주문 금액 기준입니다. " * 20,
        ),
        "inactive": Faq(
            brand_id=brand.id,
            category_id=membership.id,
            question="비활성 FAQ",
            answer="노출되면 안 됨",
            is_active=False,
        ),
        "in_hidden_category": Faq(
            brand_id=brand.id,
            category_id=hidden_category.id,
            question="숨김 카테고리 FAQ",
            answer="노출되면 안 됨",
        ),
        "other_brand": Faq(
            brand_id=other.id,
            category_id=other_category.id,
            question="다른 브랜드 FAQ",
            answer="노출되면 안 됨",
        ),
    }

    db.add_all(rows.values())
    db.commit()

    return {key: faq.id for key, faq in rows.items()}


def test_list_matches_spec_shape(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    body = client.get(
        "/api/v1/faqs", headers=HEADERS
    ).json()

    assert body["status"] == 200
    assert body["code"] == "GET_FAQS_SUCCESS"
    assert body["message"] == "FAQ 목록 조회에 성공했습니다."

    data = body["data"]

    assert {
        k: data[k]
        for k in ("page", "size", "totalElements", "totalPages")
    } == {
        "page": 0,
        "size": 10,
        "totalElements": 2,
        "totalPages": 1,
    }

    first = data["items"][0]

    assert set(first) == {
        "faqId", "categoryId", "categoryName",
        "title", "preview", "updatedAt",
    }
    assert first["faqId"] == f"faq_{ids['discount']:03d}"
    assert first["categoryId"] == "faq_event"
    assert first["categoryName"] == "이벤트 및 할인"


def test_list_hides_inactive_hidden_category_and_other_brand(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    titles = [
        i["title"]
        for i in client.get(
            "/api/v1/faqs", headers=HEADERS
        ).json()["data"]["items"]
    ]

    assert titles == [
        "할인 혜택은 어떻게 받을 수 있나요?",
        "등급 기준이 궁금해요",
    ]


def test_preview_is_truncated(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    items = client.get(
        "/api/v1/faqs",
        params={"categoryId": "faq_membership"},
        headers=HEADERS,
    ).json()["data"]["items"]

    assert len(items[0]["preview"]) <= 101
    assert items[0]["preview"].endswith("…")


def test_filter_by_category_and_keyword(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    by_category = client.get(
        "/api/v1/faqs",
        params={"categoryId": "faq_event"},
        headers=HEADERS,
    ).json()["data"]

    assert [
        i["categoryId"] for i in by_category["items"]
    ] == ["faq_event"]

    by_keyword = client.get(
        "/api/v1/faqs",
        params={"keyword": "할인"},
        headers=HEADERS,
    ).json()["data"]

    assert by_keyword["totalElements"] == 1

    by_answer = client.get(
        "/api/v1/faqs",
        params={"keyword": "주문 금액"},
        headers=HEADERS,
    ).json()["data"]

    assert by_answer["items"][0]["title"] == "등급 기준이 궁금해요"


def test_zero_based_pagination(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    data = client.get(
        "/api/v1/faqs",
        params={"page": 1, "size": 1},
        headers=HEADERS,
    ).json()["data"]

    assert data["page"] == 1
    assert data["totalPages"] == 2
    assert data["items"][0]["title"] == "등급 기준이 궁금해요"


def test_invalid_pagination(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    for params in (
        {"page": -1},
        {"size": 0},
        {"size": 51},
        {"page": "abc"},
    ):
        response = client.get(
            "/api/v1/faqs",
            params=params,
            headers=HEADERS,
        )

        assert response.status_code == 400, params
        assert response.json()["code"] == "INVALID_PAGINATION"


def test_unknown_or_inactive_category_is_not_found(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    for code in ("nope", "faq_hidden"):
        response = client.get(
            "/api/v1/faqs",
            params={"categoryId": code},
            headers=HEADERS,
        )

        assert response.status_code == 404
        assert response.json()["code"] == "FAQ_CATEGORY_NOT_FOUND"


def test_brand_header_is_required(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session)

    assert client.get("/api/v1/faqs").status_code == 400

    unknown = client.get(
        "/api/v1/faqs",
        headers={"X-Brand-Code": "nope"},
    )

    assert unknown.status_code == 404
    assert unknown.json()["code"] == "BRAND_NOT_FOUND"


def test_detail(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    body = client.get(
        f"/api/v1/faqs/faq_{ids['discount']:03d}"
    ).json()

    assert body["code"] == "GET_FAQ_DETAIL_SUCCESS"
    assert body["message"] == "FAQ 상세 조회에 성공했습니다."

    assert set(body["data"]) == {
        "faqId", "categoryId", "categoryName",
        "title", "content", "updatedAt",
    }

    assert body["data"]["content"] == (
        "멤버십, 제휴 할인으로 받을 수 있습니다."
    )


def test_detail_not_found_cases(
    client: TestClient, db_session: Session
) -> None:
    ids = _seed(db_session)

    for faq_id in (
        f"faq_{ids['inactive']:03d}",
        f"faq_{ids['in_hidden_category']:03d}",
        "faq_999",
        "abc",
        "1",
    ):
        response = client.get(f"/api/v1/faqs/{faq_id}")

        assert response.status_code == 404, faq_id
        assert response.json()["code"] == "FAQ_NOT_FOUND"