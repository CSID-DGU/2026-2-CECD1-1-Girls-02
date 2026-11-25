"""Create a fictional Dongguk Pizza knowledge base from supplied source text.

This is an explicit demo-data transformation. It must run before documents are
reviewed or indexed, never on a live production brand knowledge base.
"""
from __future__ import annotations

import re


_REPLACEMENTS = (
    (r"알볼로피자\s*&\s*목동버거", "동국피자 복합 메뉴"),
    (r"pizzaalvolofc\.co\.kr|pizzaalvolo\.co\.kr", "동국피자 공식 홈페이지"),
    (r"피자알볼로|알볼로피자|알볼로|pizzaalvolo|alvolo", "동국피자"),
    (r"비행기\s*스탬프", "동국피자 스탬프"),
    (r"탑승준비", "일반"),
    (r"이코노미(?:-클래스)?", "SILVER"),
    (r"비즈니스(?:-클래스)?", "GOLD"),
    (r"퍼스트\s*클래스|퍼스트클래스|퍼스트", "VIP"),
    (r"sUPer\s*목동피자(?:\s*치크)?", "피자"),
    (r"스와이시(?:\s*반반)?피자|스와이시\s*피자", "(신메뉴) 피자"),
    (r"FLY\s*DAY", "프로모션 DAY"),
    (r"이륙데이", "기존 프로모션"),
    (r"목동버거", "복합 메뉴"),
)

_MENU_NAMES = re.compile(
    r"어깨피자|쉬림프&핫치킨피자|꿈을피자|팔도피자|목동피자|베이컨체다치즈피자|"
    r"포테이토피자|콤비네이션피자|수퍼디럭스피자|페페로니피자|치즈피자|야채피자|"
    r"고구마피자|단호박피자|옥수수피자|고르곤졸라피자|하와이안피자|전주불백피자|"
    r"불고기피자|핫&스파이시치킨피자|치즈오븐스파게티|로제치즈오븐스파게티|"
    r"슈크림치즈스틱|스트링치즈스틱|웨지포테이토|콘치즈그라탕|버팔로윙&봉|치킨텐더"
)

_FRANCHISE_REWRITES = (
    ("브랜드 개요", "동국피자는 고객에게 친근하고 일관된 품질의 피자를 제공하는 브랜드입니다. 브랜드 운영 원칙과 메뉴 기준은 공식 안내에 따라 관리합니다."),
    ("창업 비용", "창업 비용은 매장 면적, 입지, 설비 상태와 계약 조건에 따라 달라집니다. 상세 견적과 지원 정책은 동국피자 창업 상담을 통해 개별 안내합니다."),
    ("창업 프로모션", "창업 지원 및 프로모션은 운영 시점과 대상에 따라 달라질 수 있습니다. 적용 가능 여부와 세부 조건은 창업 상담을 통해 확인합니다."),
    ("창업 경쟁력", "동국피자는 운영 교육, 매장 지원, 품질 관리 및 마케팅 협력 체계를 바탕으로 가맹 운영을 지원합니다. 실제 지원 범위는 계약 및 운영 정책을 따릅니다."),
    ("점포 개설", "창업 희망자는 상권, 매장 규모, 운영 여건을 상담한 뒤 개설 가능 여부를 확인할 수 있습니다. 개별 점포 사례와 지역별 조건은 상담 과정에서 안내합니다."),
    ("브랜드 발자취", "동국피자는 장기적으로 신뢰받는 피자 브랜드를 지향합니다. 세부 연혁과 외부 수상 정보는 공식 안내가 확인된 경우에만 제공합니다."),
    ("인테리어", "매장은 고객 동선과 조리 효율을 고려한 표준 인테리어 가이드를 적용합니다. 실제 설계와 비용은 점포 조건에 따라 상담으로 확정합니다."),
    ("메뉴 카테고리", "동국피자는 시그니처 피자, 기본 피자, 프리미엄 피자, 사이드 메뉴 등으로 메뉴를 구성합니다. 세부 메뉴와 판매 여부는 매장 및 운영 시점에 따라 달라질 수 있습니다."),
    ("중앙 마케팅", "동국피자는 디지털 홍보와 외부 협업 프로모션을 운영할 수 있습니다. 개별 협업과 혜택은 진행 시점의 공식 안내를 따릅니다."),
    ("사회공헌", "동국피자는 지역사회와의 상생 활동을 지향합니다. 구체 프로그램은 운영 시점의 공식 안내를 따릅니다."),
    ("창업 문의 절차", "창업 문의 접수, 상담, 상권 검토, 계약 검토, 교육, 매장 오픈의 절차로 진행할 수 있습니다. 상세 일정과 필요 서류는 동국피자 창업 상담 채널에서 안내합니다."),
    ("챗봇 Q&A", "창업 비용, 교육, 로열티, 매장 규모, 복합 메뉴 운영과 같은 질문은 일반 원칙만 안내합니다. 계약·견적·가맹 가능 여부처럼 개별 판단이 필요한 내용은 동국피자 창업 상담으로 이관합니다."),
)


def rebrand_text(text: str) -> str:
    """Apply approved terminology replacements to customer-facing text."""
    transformed = text
    for pattern, replacement in _REPLACEMENTS:
        transformed = re.sub(pattern, replacement, transformed, flags=re.IGNORECASE)
    return _MENU_NAMES.sub("메뉴", transformed)


def rebrand_franchise_section(title: str, text: str) -> str:
    """Replace real franchise claims and contacts with safe generic guidance."""
    for marker, replacement in _FRANCHISE_REWRITES:
        if marker in title:
            return replacement
    return "동국피자 창업 안내 문서입니다. 세부 브랜드 정보와 실제 계약 조건은 동국피자 창업 상담을 통해 확인합니다."


def rebrand_user_faq_section(title: str, text: str) -> str:
    """Remove time-sensitive source-brand details from the customer FAQ guide."""
    if "이벤트" in title:
        return (
            "현재 진행 중인 혜택은 동국피자 공식 안내를 통해 확인할 수 있습니다. "
            "예시로 피자 포장 할인, (신메뉴) 피자 세트 할인, 프로모션 DAY, 기존 프로모션이 운영될 수 있으며 "
            "기간·대상 매장·중복 적용 조건은 이벤트별 안내를 따릅니다."
        )
    if "창업" in title:
        return (
            "동국피자 창업 비용, 지원 정책, 교육, 점포 조건은 개별 상황에 따라 달라집니다. "
            "일반 절차만 안내하고, 계약·견적·입지·가맹 가능 여부는 동국피자 창업 상담으로 이관합니다."
        )
    return rebrand_text(text)
