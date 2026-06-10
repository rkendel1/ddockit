from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .service import TryContainerService

HTML_INDEX = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>TryContainer</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
    main { max-width: 980px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0 0 8px; }
    .muted { color: #94a3b8; margin: 0 0 20px; }
    .card { background: #111827; border: 1px solid #1f2937; border-radius: 10px; padding: 16px; margin-bottom: 14px; }
    label { display: inline-block; min-width: 110px; }
    select,input,button { border-radius: 6px; border: 1px solid #374151; background: #0b1220; color: #e2e8f0; padding: 8px; }
    button { cursor: pointer; background: #2563eb; border-color: #2563eb; }
    code { background: #030712; border-radius: 6px; padding: 2px 6px; }
    table { width: 100%; border-collapse: collapse; }
    td,th { padding: 8px; border-bottom: 1px solid #1f2937; text-align: left; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(270px,1fr)); gap: 12px; }
  </style>
</head>
<body>
  <main>
    <h1>TryContainer</h1>
    <p class=\"muted\">Launch disposable OSS app trials from anywhere. No local Docker required.</p>

    <section class=\"card\">
      <h3>How one-click works</h3>
      <p>Choose an app, plan, and TTL, click <strong>Try now</strong>, then open the generated live URL to evaluate the OSS project.</p>
      <p class=\"muted\">This page is the UI for launching and monitoring sessions. Use the table below to track usage and estimated charges.</p>
    </section>

    <section class=\"card\">
      <h3>Launch trial</h3>
      <p>Click once, receive a live URL, then usage is metered automatically.</p>
      <form id=\"launchForm\">
        <p><label>App</label><select id=\"app\"></select></p>
        <p><label>Plan</label><select id=\"plan\"></select></p>
        <p><label>TTL (minutes)</label><input id=\"ttl\" type=\"number\" min=\"1\" max=\"1440\" value=\"30\" /></p>
        <button type=\"submit\">Try now</button>
      </form>
      <div id=\"launchResult\"></div>
    </section>

    <section class=\"card\">
      <h3>Catalog</h3>
      <div id=\"catalog\" class=\"grid\"></div>
    </section>

    <section class=\"card\">
      <h3>Active & recent sessions</h3>
      <table>
        <thead><tr><th>ID</th><th>App</th><th>Status</th><th>Plan</th><th>Usage</th><th>Charge</th></tr></thead>
        <tbody id=\"sessions\"></tbody>
      </table>
    </section>
  </main>

<script>
let launchedId = null;

async function api(path, options) {
  const response = await fetch(path, options || {});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || 'Request failed');
  }
  return data;
}

function renderCatalog(apps) {
  const root = document.getElementById('catalog');
  root.innerHTML = apps.map(app => `
    <div class="card">
      <strong>${app.name}</strong><br/>
      <span class="muted">${app.category}</span><br/>
      <code>${app.image}</code>
    </div>
  `).join('');

  const appSelect = document.getElementById('app');
  appSelect.innerHTML = apps.map(app => `<option value="${app.slug}">${app.name}</option>`).join('');
}

function renderPlans(plans) {
  const planSelect = document.getElementById('plan');
  planSelect.innerHTML = plans.map(plan => {
    const price = plan.interval ? `$${plan.price_usd}/${plan.interval}` : `$${plan.price_usd}`;
    return `<option value="${plan.name}">${plan.name} (${price})</option>`;
  }).join('');
}

async function refreshSessions() {
  const body = await api('/sessions?include_usage=1');
  const sessions = body.sessions || [];

  const table = document.getElementById('sessions');
  table.innerHTML = sessions.map((s) => `
    <tr>
      <td><code>${s.id.slice(0, 8)}</code></td>
      <td>${s.app}</td>
      <td>${s.status}</td>
      <td>${s.plan}</td>
      <td>${s.usage ? `${s.usage.elapsed_minutes}m (${s.usage.billable_minutes} billable)` : '-'}</td>
      <td>${s.usage ? `$${s.usage.estimated_charge_usd.toFixed(2)}` : '-'}</td>
    </tr>
  `).join('');
}

async function bootstrap() {
  const [apps, pricing] = await Promise.all([api('/apps'), api('/pricing')]);
  renderCatalog(apps.apps || []);
  renderPlans(pricing.plans || []);
  await refreshSessions();
}

document.getElementById('launchForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const app = document.getElementById('app').value;
  const plan = document.getElementById('plan').value;
  const ttl = Number(document.getElementById('ttl').value || '30');
  const result = document.getElementById('launchResult');

  try {
    const response = await api('/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app, plan, ttl_minutes: ttl })
    });
    launchedId = response.session.id;
    result.innerHTML = `Live session ready: <a target="_blank" href="${response.session.url}">${response.session.url}</a>`;
    await refreshSessions();
  } catch (err) {
    result.textContent = err.message;
  }
});

setInterval(refreshSessions, 5000);
bootstrap().catch((err) => {
  document.getElementById('launchResult').textContent = err.message;
});
</script>
</body>
</html>
"""


class TryContainerHandler(BaseHTTPRequestHandler):
    service = TryContainerService(base_domain=os.getenv("TRYCONTAINER_BASE_DOMAIN", "trycontainer.com"))
    allowed_origin = os.getenv("TRYCONTAINER_ALLOWED_ORIGIN", "")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        self.service.cleanup_expired()
        parsed = urlparse(self.path)

        if parsed.path == "/":
            return self._html(HTML_INDEX)
        if parsed.path == "/health":
            return self._json({"status": "ok"})
        if parsed.path == "/apps":
            return self._json({"apps": self.service.list_apps()})
        if parsed.path == "/pricing":
            return self._json({"plans": self.service.list_pricing()})
        if parsed.path == "/sessions":
            query = parse_qs(parsed.query)
            limit_raw = query.get("limit", ["25"])[0]
            limit = int(limit_raw) if limit_raw.isdigit() else 25
            include_usage = query.get("include_usage", ["0"])[0] in {"1", "true", "True"}
            return self._json({"sessions": self.service.list_sessions(limit=limit, include_usage=include_usage)})
        if parsed.path.startswith("/sessions/") and parsed.path.endswith("/usage"):
            session_id = parsed.path.split("/")[2]
            usage = self.service.get_session_usage(session_id)
            if usage is None:
                return self._json({"error": "Session not found"}, status=HTTPStatus.NOT_FOUND)
            return self._json({"usage": usage})
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
            try:
                body = self._read_body()
            except ValueError as exc:
                return self._json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

            app_slug = body.get("app")
            ttl = body.get("ttl_minutes")
            plan = body.get("plan", "free")
            if not isinstance(app_slug, str) or not app_slug:
                return self._json({"error": "'app' is required"}, status=HTTPStatus.BAD_REQUEST)
            if not isinstance(plan, str) or not plan:
                return self._json({"error": "'plan' must be a string"}, status=HTTPStatus.BAD_REQUEST)

            if ttl is not None and not isinstance(ttl, int):
                return self._json({"error": "'ttl_minutes' must be an integer"}, status=HTTPStatus.BAD_REQUEST)

            try:
                session = self.service.launch_session(app_slug=app_slug, ttl_minutes=ttl, plan_name=plan)
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
        raw_length = self.headers.get("content-length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Invalid Content-Length header") from exc

        if length <= 0:
            return {}
        raw_body = self.rfile.read(length)
        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Malformed JSON body") from exc

    def _send_cors_headers(self) -> None:
        if self.allowed_origin:
            self.send_header("Access-Control-Allow-Origin", self.allowed_origin)
            self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        if status != HTTPStatus.NO_CONTENT:
            self.wfile.write(encoded)

    def _html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    host = os.getenv("TRYCONTAINER_HOST", "0.0.0.0")
    port = int(os.getenv("TRYCONTAINER_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), TryContainerHandler)
    print(f"TryContainer MVP listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
