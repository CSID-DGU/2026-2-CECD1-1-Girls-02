import math
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """API JSON은 camelCase, 파이썬 코드는 snake_case로 쓴다."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class Page(CamelModel, Generic[T]):
    """고객 API용. page는 0부터 시작한다."""

    items: list[T]
    page: int
    size: int
    total_elements: int
    total_pages: int

    @classmethod
    def of(
        cls,
        items: list[T],
        *,
        page: int,
        size: int,
        total: int,
    ) -> "Page[T]":
        return cls(
            items=items,
            page=page,
            size=size,
            total_elements=total,
            total_pages=math.ceil(total / size) if size else 0,
        )


class AdminPage(CamelModel, Generic[T]):
    """관리자 문의 목록용. page는 1부터 시작한다."""

    items: list[T]
    page: int
    page_size: int
    total: int