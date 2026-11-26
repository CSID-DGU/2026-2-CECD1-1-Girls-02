"""시연용 기준 데이터(브랜드·FAQ·문의 분류·매장)를 적재한다.

실행 (backend 폴더): python scripts/seed_demo.py
이미 적재돼 있으면 건너뛴다.
모든 데이터는 가상의 예시이며 실제 정책이 아니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Brand, Faq, FaqCategory, InquiryCategory, Store
from app.db.session import get_session_factory


BRAND_CODE = "brand_a"


FAQ_CATEGORIES = [
    ("faq_event", "이벤트 및 할인"),
    ("faq_membership", "멤버십"),
    ("faq_order", "주문·배달"),
    ("faq_franchise", "가맹·창업"),
]


FAQS = {
    "faq_event": [
        (
            "할인 혜택은 어떻게 받을 수 있나요?",
            "[예시] 멤버십, 제휴 할인, 기간별 이벤트를 통해 할인 혜택을 받을 수 있습니다.",
        ),
        (
            "할인 쿠폰은 중복 사용이 가능한가요?",
            "[예시] 주문 1건당 쿠폰은 1장만 사용할 수 있습니다.",
        ),
    ],
    "faq_membership": [
        (
            "멤버십 등급은 어떻게 정해지나요?",
            "[예시] 최근 6개월 주문 금액을 기준으로 매월 1일에 등급이 갱신됩니다.",
        ),
        (
            "적립 포인트에 유효기간이 있나요?",
            "[예시] 포인트는 적립일로부터 1년간 사용할 수 있습니다.",
        ),
    ],
    "faq_order": [
        (
            "주문 취소는 언제까지 가능한가요?",
            "[예시] 매장에서 주문을 접수하기 전까지 앱에서 직접 취소할 수 있습니다.",
        ),
    ],
    "faq_franchise": [
        (
            "가맹 상담은 어떻게 신청하나요?",
            "[예시] 홈페이지의 가맹 문의 메뉴에서 상담을 신청하면 담당자가 연락드립니다.",
        ),
    ],
}


# (code, name, children) 형태의 3단계 트리
INQUIRY_CATEGORY_TREE = [
    ("event", "이벤트", [
        ("event_discount", "할인 혜택", [
            ("event_discount_partner", "제휴 할인", []),
            ("event_discount_coupon", "쿠폰", []),
        ]),
        ("event_promotion", "프로모션", []),
    ]),
    ("membership", "멤버십", [
        ("membership_grade", "등급", []),
        ("membership_point", "포인트", []),
    ]),
    ("order", "주문·배달", [
        ("order_delivery", "배달", []),
        ("order_cancel", "주문 취소", []),
    ]),
    ("franchise", "가맹", [
        ("franchise_consult", "가맹 상담", []),
    ]),
    ("etc", "기타", []),
]


STORES = [
    ("S001", "브랜드A 강남점", "서울특별시 강남구 (예시 주소)", True),
    ("S002", "브랜드A 홍대입구점", "서울특별시 마포구 (예시 주소)", True),
    ("S003", "브랜드A 충무로점", "서울특별시 중구 (예시 주소)", True),
    ("S004", "브랜드A 신촌점", "서울특별시 서대문구 (예시 주소)", False),
]


def _add_categories(
    session: Session,
    brand_id: int,
    nodes: list,
    parent: InquiryCategory | None,
    depth: int,
) -> None:
    for order, (code, name, children) in enumerate(nodes):
        category = InquiryCategory(
            brand_id=brand_id,
            parent_id=parent.id if parent else None,
            depth=depth,
            code=code,
            name=name,
            sort_order=order,
        )

        session.add(category)
        session.flush()

        _add_categories(
            session,
            brand_id,
            children,
            category,
            depth + 1,
        )


def seed(session: Session) -> bool:
    """기준 데이터를 넣는다. 이미 있으면 False를 반환한다."""

    if session.scalar(
        select(Brand).where(Brand.code == BRAND_CODE)
    ):
        return False

    brand = Brand(
        code=BRAND_CODE,
        name="브랜드 A",
    )

    session.add(brand)
    session.flush()

    for order, (code, name) in enumerate(FAQ_CATEGORIES):
        category = FaqCategory(
            brand_id=brand.id,
            code=code,
            name=name,
            sort_order=order,
        )

        session.add(category)
        session.flush()

        for question, answer in FAQS.get(code, []):
            session.add(
                Faq(
                    brand_id=brand.id,
                    category_id=category.id,
                    question=question,
                    answer=answer,
                )
            )

    _add_categories(
        session,
        brand.id,
        INQUIRY_CATEGORY_TREE,
        parent=None,
        depth=1,
    )

    for code, name, address, is_active in STORES:
        session.add(
            Store(
                brand_id=brand.id,
                code=code,
                name=name,
                address=address,
                is_active=is_active,
            )
        )

    return True


def main() -> int:
    with get_session_factory()() as session, session.begin():
        created = seed(session)

    print(
        "시연용 기준 데이터를 적재했습니다."
        if created
        else "이미 적재돼 있어 건너뜁니다."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())