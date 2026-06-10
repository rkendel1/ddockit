from __future__ import annotations

from enum import Enum


class RuntimeCapability(str, Enum):
    POSTGRES = "postgres"
    REDIS = "redis"
    OBJECT_STORAGE = "objectStorage"
    EMAIL_SANDBOX = "emailSandbox"
    OPENAI_PROXY = "openaiProxy"


def normalize_capabilities(raw_capabilities: list[str] | None) -> list[RuntimeCapability]:
    if not raw_capabilities:
        return []

    normalized: list[RuntimeCapability] = []
    seen: set[RuntimeCapability] = set()
    for raw in raw_capabilities:
        capability = RuntimeCapability(raw)
        if capability not in seen:
            seen.add(capability)
            normalized.append(capability)
    return normalized
