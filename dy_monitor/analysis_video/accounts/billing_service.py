import uuid
from typing import Dict

from analysis_video.storage.repositories_json import JsonBillingRepository
from analysis_video.storage.json_store import JsonStore
from analysis_video.storage.models import BillingRecord


class BillingService:
    def __init__(self, store_path: str):
        """初始化计费存储与计费仓储。"""
        self.store = JsonStore(store_path)
        self.billing_repo = JsonBillingRepository(self.store)

    def record(self, user_id: str, action: str, units: int, meta: Dict[str, str]) -> None:
        """记录一条计费流水。"""
        rec = BillingRecord(id=str(uuid.uuid4()), user_id=user_id, action=action, units=units, ts=self.store.now(), meta=meta)
        self.billing_repo.add(rec)

    def total_units(self, user_id: str) -> int:
        """统计用户累计计费单位。"""
        return self.billing_repo.total_units_by_user(user_id)