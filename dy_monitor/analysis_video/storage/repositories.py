from abc import ABC, abstractmethod
from typing import List, Optional

from .models import User, Creator, Follow, BillingRecord, UserProfile


class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> None:
        ...

    @abstractmethod
    def get(self, user_id: str) -> Optional[User]:
        ...

    @abstractmethod
    def list(self) -> List[User]:
        ...

    @abstractmethod
    def deactivate(self, user_id: str) -> None:
        ...


class CreatorRepository(ABC):
    @abstractmethod
    def add(self, creator: Creator) -> None:
        ...

    @abstractmethod
    def get(self, creator_id: str) -> Optional[Creator]:
        ...

    @abstractmethod
    def list(self) -> List[Creator]:
        ...


class FollowRepository(ABC):
    @abstractmethod
    def add(self, follow: Follow) -> None:
        ...

    @abstractmethod
    def remove(self, user_id: str, creator_id: str) -> None:
        ...

    @abstractmethod
    def list_by_user(self, user_id: str) -> List[Follow]:
        ...


class BillingRepository(ABC):
    @abstractmethod
    def add(self, record: BillingRecord) -> None:
        ...

    @abstractmethod
    def list_by_user(self, user_id: str) -> List[BillingRecord]:
        ...

    @abstractmethod
    def total_units_by_user(self, user_id: str) -> int:
        ...


class ProfileRepository(ABC):
    @abstractmethod
    def get(self, user_id: str) -> Optional[UserProfile]:
        ...

    @abstractmethod
    def upsert(self, profile: UserProfile) -> None:
        ...