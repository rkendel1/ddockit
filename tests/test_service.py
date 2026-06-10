from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from trycontainer.service import (
    DockerExecutionRuntime,
    ExecutionRuntimeError,
    MAX_TTL_MINUTES,
    TryContainerService,
    _utc_now,
)
from trycontainer.runtime import RuntimeProfile


class FakeExecutionRuntime:
    def __init__(self) -> None:
        self.terminated: list[tuple[str | None, str]] = []
        self.last_launch: dict[str, object] | None = None

    def launch(
        self,
        repo_url: str,
        session_id: str,
        image_name: str,
        environment_variables: dict[str, str] | None = None,
        cpu_limit: str | None = None,
        memory_limit: str | None = None,
    ) -> dict[str, object]:
        if "bad" in repo_url:
            raise ExecutionRuntimeError("Unsafe configuration detected")
        self.last_launch = {
            "repo_url": repo_url,
            "session_id": session_id,
            "image_name": image_name,
            "environment_variables": environment_variables or {},
            "cpu_limit": cpu_limit,
            "memory_limit": memory_limit,
        }
        return {
            "container_id": f"exec-{session_id}",
            "container_port": 3000,
            "public_url": f"https://{session_id}.trycontainer.test",
        }

    def terminate(self, container_id: str | None, image_name: str) -> None:
        self.terminated.append((container_id, image_name))


class ServiceTests(TestCase):
    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        db_path = Path(self.tmpdir.name) / "test.db"
        self.execution_runtime = FakeExecutionRuntime()
        self.service = TryContainerService(db_path=db_path, execution_runtime=self.execution_runtime)

    def test_catalog_has_multiple_apps(self) -> None:
        apps = self.service.list_apps()
        slugs = {app["slug"] for app in apps}
        self.assertTrue({"openwebui", "n8n", "immich", "supabase"}.issubset(slugs))

    def test_launch_session_returns_url(self) -> None:
        session = self.service.launch_session("openwebui")
        self.assertEqual(session["status"], "running")
        self.assertTrue(session["url"].endswith(".trycontainer.com"))
        self.assertEqual(session["ttl_minutes"], 30)

    def test_ttl_is_capped_to_day(self) -> None:
        session = self.service.launch_session("n8n", ttl_minutes=10_000)
        self.assertEqual(session["ttl_minutes"], MAX_TTL_MINUTES)

    def test_ttl_has_minimum_floor(self) -> None:
        session = self.service.launch_session("n8n", ttl_minutes=0)
        self.assertEqual(session["ttl_minutes"], 1)

    def test_cleanup_expires_running_sessions(self) -> None:
        session = self.service.launch_session("flowise", ttl_minutes=1)
        future = _utc_now() + timedelta(minutes=2)
        cleaned = self.service.cleanup_expired(now=future)
        self.assertEqual(cleaned, 1)

        refreshed = self.service.get_session(session["id"])
        assert refreshed is not None
        self.assertEqual(refreshed["status"], "destroyed")
        self.assertEqual(refreshed["ended_reason"], "ttl-expired")

    def test_destroy_session_is_idempotent(self) -> None:
        session = self.service.launch_session("plane")
        self.assertTrue(self.service.destroy_session(session["id"]))
        self.assertTrue(self.service.destroy_session(session["id"]))

    def test_metered_plan_bills_after_free_window(self) -> None:
        session = self.service.launch_session("openwebui", ttl_minutes=60, plan_name="metered")
        created_at = datetime.fromisoformat(session["created_at"])
        now = created_at + timedelta(minutes=45)
        usage = self.service.get_session_usage(session["id"], now=now)
        assert usage is not None
        self.assertEqual(usage["elapsed_minutes"], 45)
        self.assertEqual(usage["billable_minutes"], 15)
        self.assertEqual(usage["estimated_charge_usd"], 0.3)

    def test_fixed_price_plan_remains_fixed(self) -> None:
        session = self.service.launch_session("openwebui", ttl_minutes=90, plan_name="2-hour-pass")
        created_at = datetime.fromisoformat(session["created_at"])
        now = created_at + timedelta(minutes=90)
        usage = self.service.get_session_usage(session["id"], now=now)
        assert usage is not None
        self.assertEqual(usage["billable_minutes"], 0)
        self.assertEqual(usage["estimated_charge_usd"], 1.0)

    def test_unsupported_plan_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.service.launch_session("openwebui", plan_name="enterprise")

    def test_list_sessions_can_include_usage(self) -> None:
        self.service.launch_session("openwebui", plan_name="metered", ttl_minutes=60)
        sessions = self.service.list_sessions(include_usage=True)
        self.assertEqual(len(sessions), 1)
        self.assertIn("usage", sessions[0])

    def test_execution_launch_returns_running_and_stores_running_session(self) -> None:
        result = self.service.launch_execution("https://github.com/acme/project")
        self.assertEqual(result["status"], "running")
        session = self.service.get_execution_session(result["sessionId"])
        assert session is not None
        self.assertEqual(session["status"], "running")
        self.assertEqual(session["profile"], "standard")
        self.assertEqual(session["capabilities"], "[]")
        self.assertEqual(session["environment_id"], f"env_{result['sessionId']}")
        self.assertEqual(session["container_port"], 3000)
        self.assertTrue(session["public_url"].endswith(".trycontainer.test"))

    def test_execution_launch_with_capabilities_injects_environment(self) -> None:
        result = self.service.launch_execution(
            "https://github.com/acme/project",
            capability_names=["postgres", "redis", "openaiProxy"],
        )
        assert self.execution_runtime.last_launch is not None
        self.assertEqual(self.execution_runtime.last_launch["cpu_limit"], "2")
        self.assertEqual(self.execution_runtime.last_launch["memory_limit"], "2gb")
        env = self.execution_runtime.last_launch["environment_variables"]
        assert isinstance(env, dict)
        self.assertIn("DATABASE_URL", env)
        self.assertIn("REDIS_URL", env)
        self.assertEqual(env["OPENAI_API_KEY"], "demo")

        environment = self.service.get_execution_environment(result["sessionId"])
        assert environment is not None
        self.assertEqual(environment["profile"], "standard")
        self.assertEqual(environment["capabilities"], ["postgres", "redis", "openaiProxy"])
        self.assertEqual(environment["environmentId"], f"env_{result['sessionId']}")

    def test_execution_launch_uses_profile_resources(self) -> None:
        self.service.launch_execution("https://github.com/acme/project", profile=RuntimeProfile.HEAVY)
        assert self.execution_runtime.last_launch is not None
        self.assertEqual(self.execution_runtime.last_launch["cpu_limit"], "4")
        self.assertEqual(self.execution_runtime.last_launch["memory_limit"], "8gb")

    def test_execution_launch_failure_marks_session_failed(self) -> None:
        with self.assertRaises(ExecutionRuntimeError):
            self.service.launch_execution("https://github.com/acme/bad-repo")

        sessions = self.service.list_execution_sessions(limit=5)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["status"], "failed")

    def test_execution_destroy_is_idempotent(self) -> None:
        result = self.service.launch_execution("https://github.com/acme/project")
        session_id = result["sessionId"]
        self.assertTrue(self.service.destroy_execution_session(session_id))
        self.assertTrue(self.service.destroy_execution_session(session_id))
        self.assertEqual(len(self.execution_runtime.terminated), 1)

    def test_runtime_rejects_privileged_compose(self) -> None:
        runtime = DockerExecutionRuntime(workspace_root=self.tmpdir.name, base_domain="trycontainer.test")
        workspace = Path(self.tmpdir.name) / "scan"
        workspace.mkdir()
        (workspace / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
        (workspace / "docker-compose.yml").write_text(
            "services:\n  app:\n    privileged: true\n",
            encoding="utf-8",
        )

        with self.assertRaises(ExecutionRuntimeError):
            runtime._scan_for_prohibited_config(workspace)

    def test_runtime_rejects_host_networking_compose(self) -> None:
        runtime = DockerExecutionRuntime(workspace_root=self.tmpdir.name, base_domain="trycontainer.test")
        workspace = Path(self.tmpdir.name) / "scan-host-network"
        workspace.mkdir()
        (workspace / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
        (workspace / "docker-compose.yml").write_text(
            "services:\n  app:\n    network_mode: host\n",
            encoding="utf-8",
        )

        with self.assertRaises(ExecutionRuntimeError):
            runtime._scan_for_prohibited_config(workspace)

    def test_runtime_rejects_non_github_repo_urls(self) -> None:
        runtime = DockerExecutionRuntime(workspace_root=self.tmpdir.name, base_domain="trycontainer.test")
        with self.assertRaises(ExecutionRuntimeError):
            runtime._validate_repo_url("https://example.com/private/repo")
