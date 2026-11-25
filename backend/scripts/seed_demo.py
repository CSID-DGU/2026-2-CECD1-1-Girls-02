"""시연용 기준 데이터(브랜드·카테고리·FAQ·매장)를 적재한다.

실행 (backend 폴더): python scripts/seed_demo.py
이미 적재돼 있으면 건너뛴다. 모든 데이터는 가상의 예시이며 실제 정책이 아니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 레포 루트 (rag 패키지)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Brand, Faq, FaqCategory, InquiryCategory, Store
from app.db.session import get_session_factory

BRAND_CODE = "demo_brand"

FAQ_CATEGORIES = [
    ("faq_membership", "멤버십"),
    ("faq_event", "할인·이벤트"),
    ("faq_order", "주문·배달"),
    ("faq_franchise", "가맹·창업"),
]

FAQS = {
    "faq_membership": [
        ("멤버십 등급은 어떻게 정해지나요?", "[예시] 최근 6개월 주문 금액을 기준으로 매월 1일에 등급이 갱신됩니다."),
        ("적립 포인트에 유효기간이 있나요?", "[예시] 포인트는 적립일로부터 1년간 사용할 수 있습니다."),
    ],
    "faq_event": [
        ("할인 쿠폰은 중복 사용이 가능한가요?", "[예시] 주문 1건당 쿠폰은 1장만 사용할 수 있습니다."),
    ],
    "faq_order": [
        ("주문 취소는 언제까지 가능한가요?", "[예시] 매장에서 주문을 접수하기 전까지 앱에서 직접 취소할 수 있습니다."),
    ],
    "faq_franchise": [
        ("가맹 상담은 어떻게 신청하나요?", "[예시] 홈페이지의 가맹 문의 메뉴에서 상담을 신청하면 담당자가 연락드립니다."),
    ],
}

INQUIRY_CATEGORIES = [
    ("membership", "멤버십"),
    ("discount", "할인·쿠폰"),
    ("order", "주문·배달"),
    ("franchise", "가맹 문의"),
    ("etc", "기타"),
]

STORES = [
    ("데모점 강남역점", "서울특별시 강남구 (예시 주소)"),
    ("데모점 홍대입구점", "서울특별시 마포구 (예시 주소)"),
    ("데모점 충무로점", "서울특별시 중구 (예시 주소)"),
]


def seed(session: Session) -> bool:
    """기준 데이터를 넣는다. 이미 있으면 False를 반환한다."""
    if session.scalar(select(Brand).where(Brand.code == BRAND_CODE)):
        return False

    brand = Brand(code=BRAND_CODE, name="데모 브랜드")
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

    for order, (code, name) in enumerate(INQUIRY_CATEGORIES):
        session.add(
            InquiryCategory(
                brand_id=brand.id,
                code=code,
                name=name,
                sort_order=order,
            )
        )

    for name, address in STORES:
        session.add(
            Store(
                brand_id=brand.id,
                name=name,
                address=address,
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