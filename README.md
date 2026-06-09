# ddockit

TryContainer MVP for instantly evaluating self-hosted apps without local Docker setup.

## What this MVP provides

- Curated OSS app catalog (AI, CRM, workflow, database, etc.)
- Disposable app sessions with generated `https://<subdomain>.trycontainer.com` URLs
- TTL-based auto-destruction (default `30m`)
- Lightweight control-plane API (`/apps`, `/sessions`, `/pricing`)

## Run locally

```bash
python -m trycontainer
```

Server starts on `http://127.0.0.1:8080`.

## Quick API usage

```bash
# list available apps
curl http://127.0.0.1:8080/apps

# launch a 30 minute trial
curl -X POST http://127.0.0.1:8080/sessions \
  -H 'content-type: application/json' \
  -d '{"app":"openwebui","ttl_minutes":30}'

# fetch session status
curl http://127.0.0.1:8080/sessions/<session_id>

# end a session early
curl -X DELETE http://127.0.0.1:8080/sessions/<session_id>
```

## Run tests

```bash
python -m unittest discover -s tests -v
```
