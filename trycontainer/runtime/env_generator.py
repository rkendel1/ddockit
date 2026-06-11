from __future__ import annotations

from .capabilities import RuntimeCapability


def capability_environment_variables(session_id: str, capability: RuntimeCapability) -> dict[str, str]:
    if capability == RuntimeCapability.POSTGRES:
        return {"DATABASE_URL": f"postgres://postgres.ddockit.internal:5432/{session_id}"}
    if capability == RuntimeCapability.REDIS:
        return {"REDIS_URL": f"redis://redis.ddockit.internal:6379/0?namespace={session_id}"}
    if capability == RuntimeCapability.OBJECT_STORAGE:
        return {
            "S3_ENDPOINT": "http://minio.ddockit.internal:9000",
            "S3_BUCKET": f"session-{session_id}",
        }
    if capability == RuntimeCapability.EMAIL_SANDBOX:
        return {"SMTP_HOST": "mailhog.ddockit.internal", "SMTP_PORT": "1025"}
    if capability == RuntimeCapability.OPENAI_PROXY:
        return {"OPENAI_API_KEY": "demo", "OPENAI_BASE_URL": "https://api.ddockit.io/openai"}
    return {}
