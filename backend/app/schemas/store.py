from app.db.models import Store
from app.schemas.common import CamelModel


class StoreItem(CamelModel):
    store_code: str
    store_name: str
    address: str | None
    is_active: bool

    @classmethod
    def from_model(cls, store: Store) -> "StoreItem":
        return cls(
            store_code=store.code,
            store_name=store.name,
            address=store.address,
            is_active=store.is_active,
        )