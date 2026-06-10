from __future__ import annotations

from enum import Enum
from typing import TypedDict


class RuntimeProfile(str, Enum):
    SMALL = "small"
    STANDARD = "standard"
    HEAVY = "heavy"


class ProfileResources(TypedDict):
    cpu: int
    memory: str
    disk: str
    ttl_minutes: int


_PROFILE_RESOURCES: dict[RuntimeProfile, ProfileResources] = {
    RuntimeProfile.SMALL: {"cpu": 1, "memory": "512mb", "disk": "2gb", "ttl_minutes": 30},
    RuntimeProfile.STANDARD: {"cpu": 2, "memory": "2gb", "disk": "10gb", "ttl_minutes": 60},
    RuntimeProfile.HEAVY: {"cpu": 4, "memory": "8gb", "disk": "25gb", "ttl_minutes": 120},
}


def profile_resources(profile: RuntimeProfile) -> ProfileResources:
    return dict(_PROFILE_RESOURCES[profile])
