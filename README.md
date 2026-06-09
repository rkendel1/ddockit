# ddockit

TryContainer is a working MVP for instantly evaluating self-hosted apps without local Docker setup.

## What this app provides

- Curated OSS catalog (OpenWebUI, n8n, Plane, Immich, Supabase, and more)
- One-click disposable sessions with trial URLs (`https://<subdomain>.trycontainer.com`)
- Session lifecycle API (launch, list, usage, destroy, TTL cleanup)
- Metered billing support (`free`, `metered`, `2-hour-pass`, `day-pass`, `subscription`)
- Browser UI at `/` to launch and monitor sessions from anywhere

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
