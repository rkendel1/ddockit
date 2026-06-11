from __future__ import annotations

import json
import math
import os
import secrets
import sqlite3
import subprocess
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from shutil import rmtree
from typing import Any
from urllib.parse import urlparse

from .runtime import (
    RuntimeProfile,
    assemble_environment,
    normalize_capabilities,
    profile_resources,
)

DEFAULT_BASE_DOMAIN = "localhost"
MAX_TTL_MINUTES = 1440
MIN_TTL_MINUTES = 1
SUBDOMAIN_TOKEN_BYTES = 3
DEFAULT_EXECUTION_TTL_MINUTES = 30
DEFAULT_TENANT_ID = "public"
PREFERRED_CONTAINER_PORTS = (3000, 8080, 8000, 5000, 80)
PROHIBITED_CONTAINER_PATTERNS = (
    "privileged: true",
    "network_mode: host",
    "/var/run/docker.sock",
    "docker.sock",
    "type: bind",
)


def _is_local_base_domain(base_domain: str) -> bool:
    return base_domain in {"localhost", "127.0.0.1"} or base_domain.endswith(".localhost")


def _build_subdomain_url(subdomain: str, base_domain: str) -> str:
    scheme = "http" if _is_local_base_domain(base_domain) else "https"
    return f"{scheme}://{subdomain}.{base_domain}"


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


class ExecutionRuntimeError(RuntimeError):
    pass


class DockerExecutionRuntime:
    def __init__(
        self,
        base_domain: str = DEFAULT_BASE_DOMAIN,
        docker_network: str = "ddockit",
        workspace_root: str | Path = "/tmp/ddockit",
        memory_limit: str = "512m",
        cpu_limit: str = "1",
        command_timeout_seconds: int = 300,
    ) -> None:
        self.base_domain = base_domain
        self.docker_network = docker_network
        self.workspace_root = Path(workspace_root)
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.command_timeout_seconds = max(1, command_timeout_seconds)
        self.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def launch(
        self,
        repo_url: str,
        session_id: str,
        image_name: str,
        environment_variables: dict[str, str] | None = None,
        cpu_limit: str | None = None,
        memory_limit: str | None = None,
    ) -> dict[str, Any]:
        workspace = self.workspace_root / session_id
        self._ensure_workspace_path(workspace)
        if workspace.exists():
            if workspace.is_symlink():
                raise ExecutionRuntimeError("Invalid workspace path generated for session.")
            rmtree(workspace)
        workspace.parent.mkdir(parents=True, exist_ok=True)

        self._validate_repo_url(repo_url)
        self._run(
            "git",
            "clone",
            "--depth",
            "1",
            "--single-branch",
            repo_url,
            str(workspace),
            error_context="Failed to clone repository",
        )
        dockerfile = workspace / "Dockerfile"
        if not dockerfile.exists():
            raise ExecutionRuntimeError("Repository must include a Dockerfile at project root.")
        self._scan_for_prohibited_config(workspace)

        self._run(
            "docker",
            "build",
            "-t",
            image_name,
            str(workspace),
            error_context="Failed to build Docker image",
        )
        env_args: list[str] = []
        for key, value in sorted((environment_variables or {}).items()):
            env_args.extend(["-e", f"{key}={value}"])

        container_id = self._run(
            "docker",
            "run",
            "-d",
            "-P",
            f"--memory={memory_limit or self.memory_limit}",
            f"--cpus={cpu_limit or self.cpu_limit}",
            "--network",
            self.docker_network,
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=100m",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--pids-limit",
            "256",
            "--label",
            f"session={session_id}",
            *env_args,
            image_name,
            error_context="Failed to start Docker container",
        )
        container_port = self._discover_container_port(container_id)
        host_port = self._discover_host_port(container_id, container_port)
        public_url = (
            f"http://127.0.0.1:{host_port}"
            if host_port is not None
            else _build_subdomain_url(session_id, self.base_domain)
        )
        return {
            "container_id": container_id,
            "container_port": container_port,
            "public_url": public_url,
        }

    def terminate(self, container_id: str | None, image_name: str) -> None:
        if container_id:
            self._run("docker", "stop", container_id, check=False)
            self._run("docker", "rm", container_id, check=False)
        self._run("docker", "image", "rm", image_name, check=False)

    def _scan_for_prohibited_config(self, workspace: Path) -> None:
        candidates = [workspace / "Dockerfile"]
        for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            file_path = workspace / name
            if file_path.exists():
                candidates.append(file_path)

        for file_path in candidates:
            try:
                content = file_path.read_text(encoding="utf-8", errors="strict").lower()
            except UnicodeDecodeError as exc:
                raise ExecutionRuntimeError(f"Unable to parse {file_path.name}; file must be UTF-8 text.") from exc
            for pattern in PROHIBITED_CONTAINER_PATTERNS:
                if pattern in content:
                    raise ExecutionRuntimeError(f"Unsafe configuration detected in {file_path.name}: {pattern}")

    def _discover_container_port(self, container_id: str) -> int:
        inspect_output = self._run(
            "docker",
            "inspect",
            container_id,
            error_context="Failed to inspect Docker container",
        )
        try:
            data = json.loads(inspect_output)
            exposed = data[0].get("Config", {}).get("ExposedPorts", {}) or {}
        except (json.JSONDecodeError, IndexError, AttributeError) as exc:
            raise ExecutionRuntimeError("Unable to parse exposed ports from docker inspect output.") from exc

        ports: list[int] = []
        for key in exposed.keys():
            try:
                ports.append(int(str(key).split("/", 1)[0]))
            except ValueError:
                continue
        for preferred in PREFERRED_CONTAINER_PORTS:
            if preferred in ports:
                return preferred
        if ports:
            return ports[0]
        return 80

    def _discover_host_port(self, container_id: str, container_port: int) -> int | None:
        output = self._run("docker", "port", container_id, f"{container_port}/tcp", check=False)
        if not output:
            return None
        for line in output.splitlines():
            candidate = line.strip().rsplit(":", 1)[-1]
            if candidate.isdigit():
                return int(candidate)
        return None

    def _validate_repo_url(self, repo_url: str) -> None:
        parsed = urlparse(repo_url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or not hostname:
            raise ExecutionRuntimeError("repoUrl must be a valid http(s) URL.")
        if hostname not in {"github.com", "www.github.com"}:
            raise ExecutionRuntimeError("repoUrl must point to GitHub.")
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) < 2 or any(part in {".", ".."} for part in path_parts[:2]):
            raise ExecutionRuntimeError("repoUrl must include a valid GitHub repository path.")

    def _run(
        self,
        *command: str,
        check: bool = True,
        error_context: str | None = None,
    ) -> str:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.command_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            context = f"{error_context}: " if error_context else ""
            raise ExecutionRuntimeError(f"{context}Command timed out: {' '.join(command)}") from exc
        output = (completed.stdout or "").strip()
        if check and completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            message = stderr or output or "Unknown command failure."
            context = f"{error_context}: " if error_context else ""
            raise ExecutionRuntimeError(f"{context}{message}")
        return output

    def _ensure_workspace_path(self, workspace: Path) -> None:
        root = self.workspace_root.resolve()
        candidate = workspace.resolve(strict=False)
        if candidate.parent != root:
            raise ExecutionRuntimeError("Invalid workspace path generated for session.")
        try:
            in_root = os.path.commonpath([str(root), str(candidate)]) == str(root)
        except ValueError as exc:
            raise ExecutionRuntimeError("Invalid workspace path generated for session.") from exc
        if not in_root:
            raise ExecutionRuntimeError("Invalid workspace path generated for session.")


class TryContainerService:
    def __init__(
        self,
        db_path: str | Path = "trycontainer.db",
        runtime: RuntimeAdapter | None = None,
        execution_runtime: DockerExecutionRuntime | None = None,
        base_domain: str = DEFAULT_BASE_DOMAIN,
    ):
        self.db_path = str(db_path)
        self.runtime = runtime or RuntimeAdapter()
        self.execution_runtime = execution_runtime or DockerExecutionRuntime(base_domain=base_domain)
        self.base_domain = base_domain
        self._cleanup_worker_thread: threading.Thread | None = None
        self._cleanup_worker_lock = threading.Lock()
        self._cleanup_worker_stop = threading.Event()
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_sessions (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    repo_url TEXT NOT NULL,
                    image_name TEXT NOT NULL,
                    container_id TEXT,
                    container_port INTEGER,
                    status TEXT NOT NULL,
                    public_url TEXT,
                    profile TEXT NOT NULL DEFAULT 'standard',
                    capabilities TEXT NOT NULL DEFAULT '[]',
                    environment_id TEXT,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(execution_sessions)").fetchall()
            }
            if "profile" not in columns:
                conn.execute("ALTER TABLE execution_sessions ADD COLUMN profile TEXT NOT NULL DEFAULT 'standard'")
            if "capabilities" not in columns:
                conn.execute("ALTER TABLE execution_sessions ADD COLUMN capabilities TEXT NOT NULL DEFAULT '[]'")
            if "environment_id" not in columns:
                conn.execute("ALTER TABLE execution_sessions ADD COLUMN environment_id TEXT")
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

    def launch_execution(
        self,
        repo_url: str,
        tenant_id: str = DEFAULT_TENANT_ID,
        profile: RuntimeProfile = RuntimeProfile.STANDARD,
        capability_names: list[str] | None = None,
    ) -> dict[str, Any]:
        created_at = _utc_now()
        profile_limits = profile_resources(profile)
        expires_at = created_at + timedelta(minutes=profile_limits["ttl_minutes"])
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        image_name = f"ddockit-session-{session_id}"
        capabilities = normalize_capabilities(capability_names)
        environment = assemble_environment(session_id=session_id, profile=profile, capabilities=capabilities)
        payload = {
            "id": session_id,
            "tenant_id": tenant_id,
            "repo_url": repo_url,
            "image_name": image_name,
            "container_id": None,
            "container_port": None,
            "status": "building",
            "public_url": None,
            "profile": profile.value,
            "capabilities": json.dumps([capability.value for capability in capabilities]),
            "environment_id": environment.id,
            "expires_at": expires_at.isoformat(),
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
        self._upsert_execution_session(payload)
        self._emit_execution_event("ExecutionRequested", session_id)
        self._emit_execution_event("ExecutionBuildStarted", session_id)

        try:
            details = self.execution_runtime.launch(
                repo_url=repo_url,
                session_id=session_id,
                image_name=image_name,
                environment_variables=environment.environment_variables,
                cpu_limit=str(profile_limits["cpu"]),
                memory_limit=profile_limits["memory"],
            )
            now_iso = _utc_now().isoformat()
            payload.update(
                {
                    "container_id": details.get("container_id"),
                    "container_port": details.get("container_port"),
                    "public_url": details.get("public_url"),
                    "status": "running",
                    "updated_at": now_iso,
                }
            )
            self._upsert_execution_session(payload)
            self._emit_execution_event("ExecutionBuildSucceeded", session_id)
            self._emit_execution_event("ExecutionStarted", session_id)
        except ExecutionRuntimeError as exc:
            payload.update({"status": "failed", "updated_at": _utc_now().isoformat()})
            self._upsert_execution_session(payload)
            self._emit_execution_event("ExecutionBuildFailed", session_id, detail=str(exc))
            raise

        return {"sessionId": session_id, "status": "running"}

    def get_execution_environment(self, session_id: str) -> dict[str, Any] | None:
        session = self.get_execution_session(session_id)
        if session is None:
            return None
        return {
            "profile": session["profile"],
            "capabilities": json.loads(session["capabilities"]),
            "environmentId": session["environment_id"],
        }

    def get_execution_session(self, session_id: str) -> dict[str, Any] | None:
        self.cleanup_expired()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM execution_sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_execution_sessions(self, limit: int = 25) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM execution_sessions ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def destroy_execution_session(self, session_id: str, reason: str = "manual") -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM execution_sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                return False
            raw = dict(row)
            if raw["status"] in {"destroyed", "failed"}:
                return True
            self.execution_runtime.terminate(raw.get("container_id"), raw["image_name"])
            now_iso = _utc_now().isoformat()
            conn.execute(
                """
                UPDATE execution_sessions
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                ("destroyed", now_iso, session_id),
            )
            conn.commit()
        event_name = "ExecutionExpired" if reason == "ttl-expired" else "ExecutionDestroyed"
        self._emit_execution_event(event_name, session_id)
        return True

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

        with self._connect() as conn:
            execution_rows = conn.execute(
                """
                SELECT id
                FROM execution_sessions
                WHERE status IN ('building', 'starting', 'running')
                AND expires_at <= ?
                """,
                (now_iso,),
            ).fetchall()
            execution_ids = [row["id"] for row in execution_rows]

        for session_id in execution_ids:
            self.destroy_execution_session(session_id, reason="ttl-expired")

        return len(expired_ids) + len(execution_ids)

    def start_cleanup_worker(self, interval_seconds: int = 60) -> None:
        with self._cleanup_worker_lock:
            if self._cleanup_worker_thread and self._cleanup_worker_thread.is_alive():
                return
            self._cleanup_worker_stop.clear()
            self._cleanup_worker_thread = threading.Thread(
                target=self._cleanup_worker_loop,
                args=(max(1, interval_seconds),),
                daemon=True,
            )
            self._cleanup_worker_thread.start()

    def stop_cleanup_worker(self) -> None:
        self._cleanup_worker_stop.set()

    def _cleanup_worker_loop(self, interval_seconds: int) -> None:
        while not self._cleanup_worker_stop.wait(interval_seconds):
            try:
                self.cleanup_expired()
            except Exception as exc:
                self._emit_execution_event("ExecutionCleanupFailed", "cleanup-worker", detail=str(exc))

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
            "url": _build_subdomain_url(row["subdomain"], self.base_domain),
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "ttl_minutes": metadata.get("ttl_minutes"),
            "plan": metadata.get("plan", "free"),
            "ended_reason": metadata.get("ended_reason"),
        }

    def _upsert_execution_session(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO execution_sessions
                (id, tenant_id, repo_url, image_name, container_id, container_port, status, public_url, profile, capabilities, environment_id, expires_at, created_at, updated_at)
                VALUES (:id, :tenant_id, :repo_url, :image_name, :container_id, :container_port, :status, :public_url, :profile, :capabilities, :environment_id, :expires_at, :created_at, :updated_at)
                """,
                payload,
            )
            conn.commit()

    def _emit_execution_event(self, event_name: str, session_id: str, detail: str | None = None) -> None:
        payload = {"event": event_name, "session_id": session_id}
        if detail:
            payload["detail"] = detail
        print(json.dumps(payload))
