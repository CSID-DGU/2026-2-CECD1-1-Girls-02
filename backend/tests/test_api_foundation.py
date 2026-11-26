from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import BrandOrDefault, RequiredBrand
from app.core.exception_handlers import register_exception_handlers
from app.core.public_id import (
    FAQ,
    INQUIRY,
    format_public_id,
    parse_public_id,
)
from app.db.models import Brand
from app.db.session import get_db
from app.schemas.common import AdminPage, Page


def test_public_id_round_trip() -> None:
    assert format_public_id(FAQ, 1) == "faq_001"
    assert format_public_id(INQUIRY, 1001) == "inq_1001"
    assert parse_public_id(FAQ, "faq_001") == 1
    assert parse_public_id(INQUIRY, "inq_1001") == 1001


def test_public_id_rejects_wrong_format() -> None:
    for raw in ("faq_", "faq_abc", "inq_001", "1", "faq_001_x"):
        assert parse_public_id(FAQ, raw) is None


def test_page_shapes_use_spec_keys() -> None:
    page = Page[int].of(
        [1, 2],
        page=0,
        size=2,
        total=5,
    )

    assert page.model_dump(by_alias=True) == {
        "items": [1, 2],
        "page": 0,
        "size": 2,
        "totalElements": 5,
        "totalPages": 3,
    }

    admin = AdminPage[int](
        items=[],
        page=1,
        page_size=20,
        total=0,
    )

    assert admin.model_dump(by_alias=True) == {
        "items": [],
        "page": 1,
        "pageSize": 20,
        "total": 0,
    }


def _brand_app(db: Session) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/required")
    def required(brand: RequiredBrand) -> dict[str, str]:
        return {"brand": brand.code}

    @app.get("/optional")
    def optional(brand: BrandOrDefault) -> dict[str, str]:
        return {"brand": brand.code}

    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_brand_header_dependencies(db_session: Session) -> None:
    db_session.add_all([
        Brand(code="brand_a", name="A"),
        Brand(code="brand_b", name="B"),
    ])
    db_session.commit()

    client = _brand_app(db_session)

    assert client.get(
        "/required",
        headers={"X-Brand-Code": "brand_b"},
    ).json() == {"brand": "brand_b"}

    assert client.get("/required").json()["code"] == "INVALID_PARAMETER"

    unknown = client.get(
        "/required",
        headers={"X-Brand-Code": "nope"},
    )

    assert unknown.status_code == 404
    assert unknown.json()["code"] == "BRAND_NOT_FOUND"

    assert client.get("/optional").json() == {
        "brand": "brand_a"
    }

    assert client.get(
        "/optional",
        headers={"X-Brand-Code": "brand_b"},
    ).json() == {"brand": "brand_b"}
