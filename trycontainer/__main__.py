from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .service import TryContainerService


class TryContainerHandler(BaseHTTPRequestHandler):
    service = TryContainerService()

    def do_GET(self) -> None:
        self.service.cleanup_expired()
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            return self._json({"status": "ok"})
        if parsed.path == "/apps":
            return self._json({"apps": self.service.list_apps()})
        if parsed.path == "/pricing":
            return self._json({"plans": self.service.list_pricing()})
        if parsed.path.startswith("/sessions/"):
            session_id = parsed.path.rsplit("/", 1)[-1]
            session = self.service.get_session(session_id)
            if session is None:
                return self._json({"error": "Session not found"}, status=HTTPStatus.NOT_FOUND)
            return self._json({"session": session})

        return self._json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        self.service.cleanup_expired()
        parsed = urlparse(self.path)

        if parsed.path == "/sessions":
            body = self._read_body()
            app_slug = body.get("app")
            ttl = body.get("ttl_minutes")
            if not isinstance(app_slug, str) or not app_slug:
                return self._json({"error": "'app' is required"}, status=HTTPStatus.BAD_REQUEST)

            if ttl is not None and not isinstance(ttl, int):
                return self._json({"error": "'ttl_minutes' must be an integer"}, status=HTTPStatus.BAD_REQUEST)

            try:
                session = self.service.launch_session(app_slug=app_slug, ttl_minutes=ttl)
            except ValueError as exc:
                return self._json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

            return self._json({"session": session}, status=HTTPStatus.CREATED)

        if parsed.path == "/cleanup":
            cleaned = self.service.cleanup_expired()
            return self._json({"expired_sessions_destroyed": cleaned})

        return self._json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/sessions/"):
            session_id = parsed.path.rsplit("/", 1)[-1]
            removed = self.service.destroy_session(session_id)
            if not removed:
                return self._json({"error": "Session not found"}, status=HTTPStatus.NOT_FOUND)
            return self._json({}, status=HTTPStatus.NO_CONTENT)

        return self._json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def _read_body(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        raw_body = self.rfile.read(length)
        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        if status != HTTPStatus.NO_CONTENT:
            self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8080), TryContainerHandler)
    print("TryContainer MVP listening on http://127.0.0.1:8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
