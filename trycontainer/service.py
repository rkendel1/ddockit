from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DOMAIN = "trycontainer.com"


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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RuntimeAdapter:
    def create_container(self, app: AppTemplate, session_id: str) -> str:
        return f"ctr-{session_id}"

    def destroy_container(self, container_id: str) -> None:
        _ = container_id


class TryContainerService:
    def __init__(self, db_path: str | Path = "trycontainer.db", runtime: RuntimeAdapter | None = None):
        self.db_path = str(db_path)
        self.runtime = runtime or RuntimeAdapter()
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
        return [
            {"name": "free", "duration_minutes": 30, "price_usd": 0},
            {"name": "2-hour-pass", "duration_minutes": 120, "price_usd": 1},
            {"name": "day-pass", "duration_minutes": 1440, "price_usd": 5},
            {"name": "subscription", "duration_minutes": None, "price_usd": 15, "interval": "month"},
        ]

    def launch_session(self, app_slug: str, ttl_minutes: int | None = None) -> dict[str, Any]:
        app = self._find_app(app_slug)
        session_id = uuid.uuid4().hex
        ttl = ttl_minutes if ttl_minutes is not None else app.default_ttl_minutes
        ttl = max(1, min(ttl, 1440))
        created_at = _utc_now()
        expires_at = created_at + timedelta(minutes=ttl)
        subdomain = secrets.token_hex(3)
        container_id = self.runtime.create_container(app, session_id)

        payload = {
            "id": session_id,
            "app_slug": app.slug,
            "container_id": container_id,
            "subdomain": subdomain,
            "status": "running",
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "metadata": json.dumps({"ttl_minutes": ttl}),
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

    def destroy_session(self, session_id: str, reason: str = "manual") -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                return False
            if row["status"] != "running":
                return True
            self.runtime.destroy_container(row["container_id"])
            metadata = json.loads(row["metadata"])
            metadata["ended_reason"] = reason
            conn.execute(
                "UPDATE sessions SET status = ?, metadata = ? WHERE id = ?",
                ("destroyed", json.dumps(metadata), session_id),
            )
            conn.commit()
            return True

    def cleanup_expired(self, now: datetime | None = None) -> int:
        now = now or _utc_now()
        now_iso = now.isoformat()
        expired_ids: list[str] = []

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM sessions WHERE status = 'running' AND expires_at <= ?",
                (now_iso,),
            ).fetchall()
            expired_ids = [row["id"] for row in rows]

        for session_id in expired_ids:
            self.destroy_session(session_id, reason="ttl-expired")

        return len(expired_ids)

    def _find_app(self, app_slug: str) -> AppTemplate:
        for app in CATALOG:
            if app.slug == app_slug:
                return app
        raise ValueError(f"Unsupported app '{app_slug}'.")

    @staticmethod
    def _public_session(row: dict[str, Any]) -> dict[str, Any]:
        metadata = json.loads(row["metadata"])
        return {
            "id": row["id"],
            "app": row["app_slug"],
            "status": row["status"],
            "url": f"https://{row['subdomain']}.{BASE_DOMAIN}",
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "ttl_minutes": metadata.get("ttl_minutes"),
            "ended_reason": metadata.get("ended_reason"),
        }
