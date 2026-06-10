# ddockit

TryContainer is a working MVP for instantly evaluating self-hosted apps without local Docker setup.

## What this service is

TryContainer is an evaluation sandbox for open-source software (OSS) projects. It lets you launch a short-lived hosted trial, click into a live URL, and decide whether the project is worth deeper adoption.

## What this app provides

- Curated OSS catalog (OpenWebUI, n8n, Plane, Immich, Supabase, and more)
- One-click disposable sessions with trial URLs (`https://<subdomain>.trycontainer.com`)
- Session lifecycle API (launch, list, usage, destroy, TTL cleanup)
- Metered billing support (`free`, `metered`, `2-hour-pass`, `day-pass`, `subscription`)
- Browser UI at `/` to launch and monitor sessions from anywhere

## How one-click evaluation works

1. Start the service (`python -m trycontainer`)
2. Open `http://127.0.0.1:8080/` in your browser
3. Pick an app + plan + TTL and click **Try now**
4. Receive a live URL for that OSS app
5. Explore the app, then track usage/charge in the same UI or via `/sessions?include_usage=1`
6. End the session when done (`DELETE /sessions/<session_id>`) or wait for TTL cleanup

## Run locally

```bash
python -m trycontainer
```

By default it binds to `0.0.0.0:8080` so it can be reached from other hosts in your network.

Environment overrides:

- `TRYCONTAINER_HOST` (default: `0.0.0.0`)
- `TRYCONTAINER_PORT` (default: `8080`)
- `TRYCONTAINER_BASE_DOMAIN` (default: `trycontainer.com`)
- `TRYCONTAINER_ALLOWED_ORIGIN` (default: unset/no CORS)

## Real evaluation examples

- **Evaluate OpenWebUI for AI chat workflows**: launch `openwebui` on `metered`, share the generated URL with teammates, and review usage cost before longer tests.
- **Evaluate n8n for automation**: launch `n8n` with `2-hour-pass` for a fixed-price deep dive and destroy the session when finished.
- **Evaluate Supabase for quick schema testing**: launch `supabase` with a short TTL (`30-60` minutes), validate setup speed, then compare with other catalog apps.

## Quick API usage

```bash
# health check
curl http://127.0.0.1:8080/health

# list available apps
curl http://127.0.0.1:8080/apps

# list pricing plans
curl http://127.0.0.1:8080/pricing

# launch a trial session
curl -X POST http://127.0.0.1:8080/sessions \
  -H 'content-type: application/json' \
  -d '{"app":"openwebui","plan":"metered","ttl_minutes":60}'

# list recent sessions
curl http://127.0.0.1:8080/sessions

# list sessions with embedded usage/metering
curl http://127.0.0.1:8080/sessions?include_usage=1

# inspect metering for a session
curl http://127.0.0.1:8080/sessions/<session_id>/usage

# end a session early
curl -X DELETE http://127.0.0.1:8080/sessions/<session_id>
```

Metering rounds elapsed time up to the next minute (`ceil`) so billing is minute-based.

## Run tests

```bash
python -m unittest discover -s tests -v
```
