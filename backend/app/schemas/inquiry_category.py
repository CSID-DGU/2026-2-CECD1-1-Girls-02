from __future__ import annotations

from app.schemas.common import CamelModel
from app.services.inquiry_category_service import CategoryNode


class InquiryTypeItem(CamelModel):
    code: str
    name: str


class CategoryItem(CamelModel):
    category_id: str
    name: str
    depth: int
    children: list[CategoryItem] | None = None

    @classmethod
    def from_node(cls, node: CategoryNode) -> CategoryItem:
        return cls(
            category_id=node.category.code,
            name=node.category.name,
            depth=node.category.depth,
            children=[
                cls.from_node(child)
                for child in node.children
            ] or None,
        )


class InquiryCategoriesData(CamelModel):
    inquiry_types: list[InquiryTypeItem]
    categories: list[CategoryItem]