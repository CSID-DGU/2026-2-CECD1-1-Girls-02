from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Brand, InquiryCategory, Store


def _brands(db: Session) -> tuple[Brand, Brand]:
    brand = Brand(code="brand_a", name="브랜드 A")
    other = Brand(code="brand_b", name="브랜드 B")
    db.add_all([brand, other])
    db.flush()
    return brand, other


def _category(
    db: Session,
    brand: Brand,
    code: str,
    name: str,
    parent: InquiryCategory | None = None,
    order: int = 0,
    active: bool = True,
) -> InquiryCategory:
    category = InquiryCategory(
        brand_id=brand.id,
        parent_id=parent.id if parent else None,
        depth=parent.depth + 1 if parent else 1,
        code=code,
        name=name,
        sort_order=order,
        is_active=active,
    )
    db.add(category)
    db.flush()
    return category


# ---------- 문의 유형/카테고리 ----------

def test_inquiry_categories_tree_matches_spec(
    client: TestClient, db_session: Session
) -> None:
    brand, other = _brands(db_session)

    event = _category(db_session, brand, "event", "이벤트")
    discount = _category(
        db_session, brand, "event_discount", "할인 혜택", event
    )
    _category(
        db_session, brand,
        "event_discount_partner", "제휴 할인", discount
    )
    _category(db_session, brand, "etc", "기타", order=1)
    _category(db_session, other, "other_root", "다른 브랜드")
    db_session.commit()

    body = client.get("/api/v1/inquiry-categories").json()

    assert body["code"] == "GET_INQUIRY_CATEGORIES_SUCCESS"
    assert body["message"] == "문의 카테고리 조회에 성공했습니다."

    assert body["data"]["inquiryTypes"] == [
        {"code": "QUESTION", "name": "문의"},
        {"code": "SUGGESTION", "name": "제안"},
        {"code": "COMPLIMENT", "name": "칭찬"},
        {"code": "COMPLAINT", "name": "불만"},
    ]

    assert body["data"]["categories"] == [
        {
            "categoryId": "event",
            "name": "이벤트",
            "depth": 1,
            "children": [
                {
                    "categoryId": "event_discount",
                    "name": "할인 혜택",
                    "depth": 2,
                    "children": [
                        {
                            "categoryId": "event_discount_partner",
                            "name": "제휴 할인",
                            "depth": 3,
                        },
                    ],
                }
            ],
        },
        {
            "categoryId": "etc",
            "name": "기타",
            "depth": 1,
        },
    ]


def test_inactive_category_hides_its_subtree(
    client: TestClient, db_session: Session
) -> None:
    brand, _ = _brands(db_session)

    closed = _category(
        db_session, brand, "closed", "종료된 분류", active=False
    )
    _category(db_session, brand, "closed_child", "하위", closed)
    _category(db_session, brand, "open", "운영 분류", order=1)
    db_session.commit()

    categories = client.get(
        "/api/v1/inquiry-categories"
    ).json()["data"]["categories"]

    assert [c["categoryId"] for c in categories] == ["open"]


def test_inquiry_categories_brand_header(
    client: TestClient, db_session: Session
) -> None:
    brand, other = _brands(db_session)
    _category(db_session, other, "other_root", "다른 브랜드")
    db_session.commit()

    by_header = client.get(
        "/api/v1/inquiry-categories",
        headers={"X-Brand-Code": "brand_b"},
    ).json()

    assert [
        c["categoryId"]
        for c in by_header["data"]["categories"]
    ] == ["other_root"]

    unknown = client.get(
        "/api/v1/inquiry-categories",
        headers={"X-Brand-Code": "nope"},
    )

    assert unknown.status_code == 404
    assert unknown.json()["code"] == "BRAND_NOT_FOUND"


# ---------- 이용 매장 검색 ----------

def _stores(db: Session) -> None:
    brand, other = _brands(db)

    db.add_all([
        Store(
            brand_id=brand.id,
            code="S001",
            name="브랜드A 강남점",
            address="서울특별시 강남구",
        ),
        Store(
            brand_id=brand.id,
            code="S002",
            name="브랜드A 홍대입구점",
            address="서울특별시 마포구",
        ),
        Store(
            brand_id=brand.id,
            code="S004",
            name="브랜드A 강남역2호점",
            address=None,
            is_active=False,
        ),
        Store(
            brand_id=other.id,
            code="S001",
            name="다른 브랜드 강남점",
            address="서울",
        ),
    ])

    db.commit()


def test_store_search_matches_spec_shape(
    client: TestClient, db_session: Session
) -> None:
    _stores(db_session)

    body = client.get(
        "/api/v1/stores",
        params={"keyword": "강남"},
    ).json()

    assert body["code"] == "GET_STORES_SUCCESS"
    assert body["message"] == "매장 목록 조회에 성공했습니다."

    data = body["data"]

    assert {
        k: data[k]
        for k in ("page", "size", "totalElements", "totalPages")
    } == {
        "page": 0,
        "size": 20,
        "totalElements": 2,
        "totalPages": 1,
    }

    assert data["items"] == [
        {
            "storeCode": "S001",
            "storeName": "브랜드A 강남점",
            "address": "서울특별시 강남구",
            "isActive": True,
        },
        {
            "storeCode": "S004",
            "storeName": "브랜드A 강남역2호점",
            "address": None,
            "isActive": False,
        },
    ]


def test_store_search_by_code_and_without_keyword(
    client: TestClient, db_session: Session
) -> None:
    _stores(db_session)

    by_code = client.get(
        "/api/v1/stores",
        params={"keyword": "s002"},
    ).json()["data"]

    assert [
        i["storeCode"] for i in by_code["items"]
    ] == ["S002"]

    everything = client.get("/api/v1/stores").json()["data"]

    assert everything["totalElements"] == 3


def test_store_search_pagination(
    client: TestClient, db_session: Session
) -> None:
    _stores(db_session)

    data = client.get(
        "/api/v1/stores",
        params={"page": 1, "size": 2},
    ).json()["data"]

    assert data["totalPages"] == 2
    assert len(data["items"]) == 1

    for params in ({"page": -1}, {"size": 51}):
        response = client.get(
            "/api/v1/stores",
            params=params,
        )

        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_PAGINATION"