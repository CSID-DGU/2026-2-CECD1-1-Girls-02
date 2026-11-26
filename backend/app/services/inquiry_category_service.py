from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InquiryCategory, InquiryType


INQUIRY_TYPE_NAMES: dict[InquiryType, str] = {
    InquiryType.QUESTION: "문의",
    InquiryType.SUGGESTION: "제안",
    InquiryType.COMPLIMENT: "칭찬",
    InquiryType.COMPLAINT: "불만",
}


@dataclass
class CategoryNode:
    category: InquiryCategory
    children: list["CategoryNode"] = field(default_factory=list)


def get_category_tree(
    db: Session,
    *,
    brand_id: int,
) -> list[CategoryNode]:
    """활성 카테고리를 트리로 만든다."""
    categories = db.scalars(
        select(InquiryCategory)
        .where(
            InquiryCategory.brand_id == brand_id,
            InquiryCategory.is_active.is_(True),
        )
        .order_by(
            InquiryCategory.depth,
            InquiryCategory.sort_order,
            InquiryCategory.id,
        )
    )

    nodes: dict[int, CategoryNode] = {}
    roots: list[CategoryNode] = []

    for category in categories:
        node = CategoryNode(category)

        if category.parent_id is None:
            roots.append(node)
        elif category.parent_id in nodes:
            nodes[category.parent_id].children.append(node)
        else:
            continue

        nodes[category.id] = node

    return roots