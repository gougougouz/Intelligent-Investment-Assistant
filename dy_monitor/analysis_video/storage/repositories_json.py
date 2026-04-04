from typing import List, Optional

from analysis_video.storage.models import User, Creator, Follow, BillingRecord, UserProfile
from analysis_video.storage.repositories import (
    UserRepository,
    CreatorRepository,
    FollowRepository,
    BillingRepository,
    ProfileRepository,
)
from .json_store import JsonStore


class JsonUserRepository(UserRepository):
    def __init__(self, path_users: str):
        """初始化用户仓储，底层使用 users.json。"""
        self.store = JsonStore(path_users)
        self.store.data.setdefault("users", {})

    def _find_by_phone(self, phone: str) -> Optional[dict]:
        """按手机号在内存数据中查找原始用户字典。"""
        users = self.store.data.get("users", {})
        for _, v in users.items():
            if v.get("phone") == phone:
                return v
        return None

    def add(self, user: User) -> None:
        """新增或覆盖一个用户记录。"""
        users = self.store.data.setdefault("users", {})
        key = user.phone
        users[key] = {
            "id": user.id,
            "phone": user.phone,
            "email": user.email,
            "active": user.active,
            "balance_cents": int(getattr(user, "balance_cents", 0)),
        }
        self.store.save()

    def get(self, user_id: str) -> Optional[User]:
        """按 user_id（兼容手机号）获取用户对象。"""
        v = self._find_by_phone(user_id)
        if not v:
            v = self.store.data.get("users", {}).get(user_id)
        if not v:
            return None
        return User(
            id=v.get("id", ""),
            phone=v.get("phone", ""),
            email=v.get("email", ""),
            active=bool(v.get("active", True)),
            balance_cents=int(v.get("balance_cents", 0)),
        )

    def list(self) -> List[User]:
        """返回全部用户列表。"""
        res = []
        for v in self.store.data.get("users", {}).values():
            res.append(User(
                id=v.get("id", ""),
                phone=v.get("phone", ""),
                email=v.get("email", ""),
                active=bool(v.get("active", True)),
                balance_cents=int(v.get("balance_cents", 0)),
            ))
        return res

    def deactivate(self, user_id: str) -> None:
        """按 user_id（兼容手机号）停用用户。"""
        v = self._find_by_phone(user_id)
        if not v:
            v = self.store.data.get("users", {}).get(user_id)
        if v:
            v["active"] = False
            self.store.save()

    def get_by_phone(self, phone: str) -> Optional[User]:
        """按手机号获取用户。"""
        v = self._find_by_phone(phone)
        if not v:
            return None
        return User(
            id=v.get("id", ""),
            phone=v.get("phone", ""),
            email=v.get("email", ""),
            active=bool(v.get("active", True)),
            balance_cents=int(v.get("balance_cents", 0)),
        )

    def deactivate_by_phone(self, phone: str) -> None:
        """按手机号停用用户。"""
        v = self._find_by_phone(phone)
        if v:
            v["active"] = False
            self.store.save()

    def set_balance(self, user_id: str, balance_cents: int) -> None:
        """直接设置用户余额（分）。"""
        v = self._find_by_phone(user_id)
        if not v:
            v = self.store.data.get("users", {}).get(user_id)
        if not v:
            return
        v["balance_cents"] = int(balance_cents)
        self.store.save()

    def adjust_balance(self, user_id: str, delta_cents: int) -> int:
        """增量调整用户余额并返回新余额（分）。"""
        v = self._find_by_phone(user_id)
        if not v:
            v = self.store.data.get("users", {}).get(user_id)
        if not v:
            return 0
        new_balance = int(v.get("balance_cents", 0)) + int(delta_cents)
        v["balance_cents"] = new_balance
        self.store.save()
        return new_balance


class JsonCreatorRepository(CreatorRepository):
    def __init__(self, path_creators: str):
        """初始化创作者仓储，底层使用 creators.json。"""
        self.store = JsonStore(path_creators)
        self.store.data.setdefault("creators", {})

    def add(self, creator: Creator) -> None:
        """新增或覆盖创作者记录。"""
        self.store.data["creators"][creator.display_name] = {
            "id": creator.id,
            "platform": creator.platform,
            "display_name": creator.display_name,
            "meta": creator.meta,
        }
        self.store.save()

    def get(self, creator_id: str) -> Optional[Creator]:
        """按创作者键获取创作者对象。"""
        v = self.store.data.get("creators", {}).get(creator_id)
        if not v:
            return None
        return Creator(id=v["id"], platform=v["platform"], display_name=v.get("display_name"), meta=v.get("meta", {}))

    def list(self) -> List[Creator]:
        """返回全部创作者列表。"""
        return [Creator(id=v["id"], platform=v["platform"], display_name=v.get("display_name"), meta=v.get("meta", {})) for v in self.store.data.get("creators", {}).values()]


class JsonFollowRepository(FollowRepository):
    def __init__(self, path_follows: str):
        """初始化关注关系仓储，底层使用 follows.json。"""
        self.store = JsonStore(path_follows)
        self.store.data.setdefault("follows", [])

    def add(self, follow: Follow) -> None:
        """新增关注关系；若已存在则跳过。"""
        exists = any(f["user_id"] == follow.user_id and f["creator_id"] == follow.creator_id for f in self.store.data["follows"])
        if not exists:
            self.store.data["follows"].append({
                "user_id": follow.user_id,
                "creator_id": follow.creator_id,
                "created_at": follow.created_at,
                "notes": follow.notes,
            })
            self.store.save()

    def remove(self, user_id: str, creator_id: str) -> None:
        """删除指定用户与创作者的关注关系。"""
        self.store.data["follows"] = [f for f in self.store.data["follows"] if not (f["user_id"] == user_id and f["creator_id"] == creator_id)]
        self.store.save()

    def list_by_user(self, user_id: str) -> List[Follow]:
        """列出指定用户的全部关注关系。"""
        return [Follow(user_id=f["user_id"], creator_id=f["creator_id"], created_at=int(f.get("created_at", 0)), notes=f.get("notes")) for f in self.store.data.get("follows", []) if f["user_id"] == user_id]


class JsonBillingRepository(BillingRepository):
    def __init__(self, store: JsonStore):
        """初始化计费仓储，复用外部 JsonStore。"""
        self.store = store
        self.store.data.setdefault("billing", [])

    def add(self, record: BillingRecord) -> None:
        """新增一条计费记录。"""
        self.store.data["billing"].append({
            "id": record.id,
            "user_id": record.user_id,
            "action": record.action,
            "units": record.units,
            "ts": record.ts,
            "meta": record.meta,
        })
        self.store.save()

    def list_by_user(self, user_id: str) -> List[BillingRecord]:
        """按用户查询计费流水。"""
        return [BillingRecord(id=b["id"], user_id=b["user_id"], action=b["action"], units=int(b["units"]), ts=int(b["ts"]), meta=b.get("meta", {})) for b in self.store.data.get("billing", []) if b["user_id"] == user_id]

    def total_units_by_user(self, user_id: str) -> int:
        """统计用户累计计费单位。"""
        return sum(int(b["units"]) for b in self.store.data.get("billing", []) if b["user_id"] == user_id)


class JsonProfileRepository(ProfileRepository):
    def __init__(self, user_repo: JsonUserRepository, follow_repo: JsonFollowRepository):
        """初始化用户画像仓储（用户信息 + 关注关系聚合）。"""
        self.user_repo = user_repo
        self.follow_repo = follow_repo

    def get(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像，不存在返回 None。"""
        u = self.user_repo.get(user_id)
        if not u:
            return None
        follows = self.follow_repo.list_by_user(user_id)
        return UserProfile(user=u, follows=follows)

    def upsert(self, profile: UserProfile) -> None:
        """写入用户画像（用户 + 关注关系）。"""
        self.user_repo.add(profile.user)
        for f in profile.follows:
            self.follow_repo.add(f)