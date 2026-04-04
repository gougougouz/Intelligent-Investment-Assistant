from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class User:
    id: str
    phone: str
    email: str
    active: bool = True
    balance_cents: int = 0


@dataclass
class Creator:
    id: str
    platform: str
    display_name: Optional[str] = None
    meta: Dict[str, str] = field(default_factory=dict)


@dataclass
class Follow:
    user_id: str
    creator_id: str
    created_at: int
    notes: Optional[str] = None


@dataclass
class BillingRecord:
    id: str
    user_id: str
    action: str
    units: int
    ts: int
    meta: Dict[str, str] = field(default_factory=dict)


@dataclass
class UserProfile:
    user: User
    follows: List[Follow] = field(default_factory=list)
    balance_cents: int = 0