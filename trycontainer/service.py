from __future__ import annotations

import json
import math
import secrets
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_BASE_DOMAIN = "trycontainer.com"
MAX_TTL_MINUTES = 1440
MIN_TTL_MINUTES = 1
SUBDOMAIN_TOKEN_BYTES = 3


@dataclass(frozen=True)
class AppTemplate:
    slug: str
    name: str
    category: str
    image: str
    memory: str
    default_ttl_minutes: int = 30


CATALOG: tuple[AppTemplate, ...] = (
    AppTemplate("openwebui", "OpenWebUI", "AI", "ghcr.io/open-webui/open-webui:main", "1gb"),
    AppTemplate("n8n", "n8n", "Workflow Automation", "docker.n8n.io/n8nio/n8n", "1gb"),
    AppTemplate("plane", "Plane", "Project Management", "ghcr.io/makeplane/plane:latest", "2gb"),
    AppTemplate("appflowy", "AppFlowy", "Knowledge Management", "appflowyinc/appflowy_cloud", "2gb"),
    AppTemplate("outline", "Outline", "Knowledge Management", "docker.getoutline.com/outlinewiki/outline", "2gb"),
    AppTemplate("immich", "Immich", "Media", "ghcr.io/immich-app/immich-server:release", "2gb"),
    AppTemplate("calcom", "Cal.com", "Scheduling", "calcom/cal.com", "2gb"),
    AppTemplate("budibase", "Budibase", "Internal Tools", "budibase/budibase", "2gb"),
    AppTemplate("supabase", "Supabase", "Databases", "supabase/postgres", "2gb"),
    AppTemplate("flowise", "Flowise", "AI", "flowiseai/flowise", "1gb"),
    AppTemplate("twenty", "Twenty CRM", "CRM", "twentycrm/twenty", "2gb"),
)

PRICING_PLANS: tuple[dict[str, Any], ...] = (
    {
        "name": "free",
        "duration_minutes": 30,
        "price_usd": 0.0,
        "included_minutes": 30,
        "metered_rate_per_minute": 0.0,
    },
    {
        "name": "2-hour-pass",
        "duration_minutes": 120,
        "price_usd": 1.0,
        "included_minutes": 120,
        "metered_rate_per_minute": 0.0,
    },
    {
        "name": "day-pass",
        "duration_minutes": MAX_TTL_MINUTES,
        "price_usd": 5.0,
        "included_minutes": MAX_TTL_MINUTES,
        "metered_rate_per_minute": 0.0,
    },
    {
        "name": "metered",
        "duration_minutes": MAX_TTL_MINUTES,
        "price_usd": 0.0,
        "included_minutes": 30,
        "metered_rate_per_minute": 0.02,
    },
    {
        "name": "subscription",
        "duration_minutes": None,
        "price_usd": 15.0,
        "interval": "month",
        "included_minutes": None,
        "metered_rate_per_minute": 0.0,
    },
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


class RuntimeAdapter:
    def create_container(self, app: AppTemplate, session_id: str) -> str:
        return f"ctr-{session_id}"

    def destroy_container(self, container_id: str) -> None:
        _ = container_id


class TryContainerService:
    def __init__(
        self,
        db_path: str | Path = "trycontainer.db",
        runtime: RuntimeAdapter | None = None,
        base_domain: str = DEFAULT_BASE_DOMAIN,
    ):
        self.db_path = str(db_path)
        self.runtime = runtime or RuntimeAdapter()
        self.base_domain = base_domain
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    app_slug TEXT NOT NULL,
                    container_id TEXT NOT NULL,
                    subdomain TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.commit()

    def list_apps(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in CATALOG]

    def list_pricing(self) -> list[dict[str, Any]]:
        return [dict(plan) for plan in PRICING_PLANS]

    def list_sessions(self, limit: int = 25, include_usage: bool = False) -> list[dict[str, Any]]:
        self.cleanup_expired()
        safe_limit = max(1, min(limit, 200))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        sessions = [self._public_session(dict(row)) for row in rows]
        if not include_usage:
            return sessions

        now = _utc_now()
        for session in sessions:
            usage = self.get_session_usage(session["id"], now=now)
            session["usage"] = usage
        return sessions

    def launch_session(self, app_slug: str, ttl_minutes: int | None = None, plan_name: str = "free") -> dict[str, Any]:
        app = self._find_app(app_slug)
        plan = self._find_plan(plan_name)
        session_id = uuid.uuid4().hex

        default_ttl = plan["duration_minutes"] if plan["duration_minutes"] is not None else app.default_ttl_minutes
        ttl = ttl_minutes if ttl_minutes is not None else default_ttl
        ttl = max(MIN_TTL_MINUTES, min(ttl, MAX_TTL_MINUTES))

        created_at = _utc_now()
        expires_at = created_at + timedelta(minutes=ttl)
        subdomain = secrets.token_hex(SUBDOMAIN_TOKEN_BYTES)
        container_id = self.runtime.create_container(app, session_id)

        metadata = {
            "ttl_minutes": ttl,
            "plan": plan["name"],
            "included_minutes": plan.get("included_minutes"),
            "fixed_price_usd": plan.get("price_usd", 0.0),
            "metered_rate_per_minute": plan.get("metered_rate_per_minute", 0.0),
            "ended_at": None,
            "ended_reason": None,
        }

        payload = {
            "id": session_id,
            "app_slug": app.slug,
            "container_id": container_id,
            "subdomain": subdomain,
            "status": "running",
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "metadata": json.dumps(metadata),
        }

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, app_slug, container_id, subdomain, status, created_at, expires_at, metadata)
                VALUES (:id, :app_slug, :container_id, :subdomain, :status, :created_at, :expires_at, :metadata)
                """,
                payload,
            )
            conn.commit()

        return self._public_session(payload)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        self.cleanup_expired()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return self._public_session(dict(row))

    def get_session_usage(self, session_id: str, now: datetime | None = None) -> dict[str, Any] | None:
        self.cleanup_expired(now=now)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None

        raw = dict(row)
        metadata = json.loads(raw["metadata"])
        created_at = _parse_iso(raw["created_at"])
        expires_at = _parse_iso(raw["expires_at"])

        reference_now = now or _utc_now()
        ended_at = _parse_iso(metadata["ended_at"]) if metadata.get("ended_at") else None
        end_time = ended_at or min(expires_at, reference_now)
        elapsed_seconds = max(0.0, (end_time - created_at).total_seconds())
        elapsed_minutes = math.ceil(elapsed_seconds / 60)

        included_minutes = metadata.get("included_minutes")
        if included_minutes is None:
            billable_minutes = 0
        else:
            billable_minutes = max(0, elapsed_minutes - int(included_minutes))

        fixed_price = float(metadata.get("fixed_price_usd", 0.0))
        metered_rate = float(metadata.get("metered_rate_per_minute", 0.0))
        estimated_charge = round(fixed_price + (billable_minutes * metered_rate), 2)

        return {
            "session_id": raw["id"],
            "status": raw["status"],
            "plan": metadata.get("plan", "free"),
            "elapsed_minutes": elapsed_minutes,
            "billable_minutes": billable_minutes,
            "metered_rate_per_minute": metered_rate,
            "fixed_price_usd": fixed_price,
            "estimated_charge_usd": estimated_charge,
        }

    def destroy_session(self, session_id: str, reason: str = "manual", ended_at: datetime | None = None) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                return False
            if row["status"] != "running":
                return True
            self.runtime.destroy_container(row["container_id"])
            metadata = json.loads(row["metadata"])
            metadata["ended_reason"] = reason
            metadata["ended_at"] = (ended_at or _utc_now()).isoformat()
            conn.execute(
                "UPDATE sessions SET status = ?, metadata = ? WHERE id = ?",
                ("destroyed", json.dumps(metadata), session_id),
            )
            conn.commit()
            return True

    def cleanup_expired(self, now: datetime | None = None) -> int:
        now = now or _utc_now()
        now_iso = now.isoformat()

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM sessions WHERE status = 'running' AND expires_at <= ?",
                (now_iso,),
            ).fetchall()
            expired_ids = [row["id"] for row in rows]

        for session_id in expired_ids:
            self.destroy_session(session_id, reason="ttl-expired", ended_at=now)

        return len(expired_ids)

    def _find_app(self, app_slug: str) -> AppTemplate:
        for app in CATALOG:
            if app.slug == app_slug:
                return app
        raise ValueError(f"Unsupported app '{app_slug}'.")

    def _find_plan(self, plan_name: str) -> dict[str, Any]:
        for plan in PRICING_PLANS:
            if plan["name"] == plan_name:
                return plan
        raise ValueError(f"Unsupported plan '{plan_name}'.")

    def _public_session(self, row: dict[str, Any]) -> dict[str, Any]:
        metadata = json.loads(row["metadata"])
        return {
            "id": row["id"],
            "app": row["app_slug"],
            "status": row["status"],
            "url": f"https://{row['subdomain']}.{self.base_domain}",
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "ttl_minutes": metadata.get("ttl_minutes"),
            "plan": metadata.get("plan", "free"),
            "ended_reason": metadata.get("ended_reason"),
        }
