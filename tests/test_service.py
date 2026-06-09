from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from trycontainer.service import TryContainerService, _utc_now


class ServiceTests(TestCase):
    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        db_path = Path(self.tmpdir.name) / "test.db"
        self.service = TryContainerService(db_path=db_path)

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
        self.assertEqual(session["ttl_minutes"], 1440)

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
