import uuid
from typing import List

import os
import time
from analysis_video.storage.json_store import JsonStore
from analysis_video.storage.repositories_json import (
    JsonUserRepository,
    JsonCreatorRepository,
    JsonFollowRepository,
)
from analysis_video.storage.models import User, Creator, Follow


class UserService:
    def __init__(self, store_path: str):
        """初始化用户、创作者、关注关系仓储。"""
        base = store_path if os.path.isdir(store_path) else os.path.dirname(store_path)
        os.makedirs(base, exist_ok=True)
        self.users = JsonUserRepository(os.path.join(base, "users.json"))
        self.creators = JsonCreatorRepository(os.path.join(base, "creators.json"))
        self.follows = JsonFollowRepository(os.path.join(base, "follows.json"))

    def add_user(self, user_id: str, phone: str, email: str) -> None:
        """新增用户。"""
        self.users.add(User(id=user_id, phone=phone, email=email))

    def add_creator(self, creator_id: str, platform: str, display_name: str = "") -> None:
        """新增创作者。"""
        self.creators.add(Creator(id=creator_id, platform=platform, display_name=display_name))

    def follow(self, user_id: str, creator_id: str, notes: str = "") -> None:
        """建立用户与创作者的关注关系。"""
        self.follows.add(Follow(user_id=user_id, creator_id=creator_id, created_at=int(time.time()), notes=notes))

    def unfollow(self, user_id: str, creator_id: str) -> None:
        """取消用户对创作者的关注。"""
        self.follows.remove(user_id, creator_id)

    def list_users(self) -> List[User]:
        """列出全部用户。"""
        return self.users.list()

    def list_follows(self, user_id: str) -> List[Follow]:
        """查询指定用户的关注列表。"""
        return self.follows.list_by_user(user_id)

    def get_creator(self, creator_id: str) -> Creator:
        """按创作者 ID 获取创作者，不存在时返回空对象。"""
        c = self.creators.get(creator_id)
        if not c:
            return Creator(id=creator_id, platform="", display_name="")
        return c

    def get_user_by_phone(self, phone: str) -> User:
        """按手机号获取用户，不存在时返回 inactive 的空对象。"""
        u = self.users.get_by_phone(phone)
        if not u:
            return User(id="", phone=phone, email="", active=False)
        return u

    def adjust_balance(self, user_id: str, delta_cents: int) -> int:
        """按增量调整用户余额，返回调整后的余额（分）。"""
        return self.users.adjust_balance(user_id, delta_cents)