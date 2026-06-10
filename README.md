# ddockit

TryContainer is a working MVP for instantly evaluating self-hosted apps without local Docker setup.

## What this service is

TryContainer is an evaluation sandbox for open-source software (OSS) projects. It lets you launch a short-lived hosted trial, click into a live URL, and decide whether the project is worth deeper adoption.

This is an **evaluation environment product** first. Containers are just the delivery mechanism.

## The core value proposition

Users are not buying a container runtime. They are buying:

- Safety
- Speed
- Zero setup
- Zero commitment
- Isolation
- Curiosity

Traditional flow:

```text
Find project
↓
Read README
↓
Install Docker
↓
Configure environment variables
↓
Pull images
↓
Wait
↓
Break something
↓
Decide maybe it's not worth it
```

TryContainer flow:

```text
Find project
↓
Click Try
↓
Use immediately
↓
Destroy
```

## What this app provides

- Curated OSS catalog (OpenWebUI, n8n, Plane, Immich, Supabase, and more)
- One-click disposable sessions with trial URLs (`https://<subdomain>.trycontainer.com`)
- Session lifecycle API (launch, list, usage, destroy, TTL cleanup)
- Real execution API for repository-backed sessions (`/api/execution/*`)
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

## Who this is for

- **Self-hosting hobbyists** evaluating projects such as Immich, Jellyfin, AppFlowy, Plane, OpenProject, NocoDB, and Open WebUI
- **IT teams** that need disposable evaluation instances before approval decisions
- **Consultants** that evaluate software repeatedly and need fast resettable environments
- **OSS maintainers** that want a reliable "Try it now" experience for contributors and evaluators

## MVP roadmap

### Phase 1 (must-have)

Input: GitHub URL

TryContainer should:

1. Detect Dockerfile or docker-compose
2. Build
3. Generate URL
4. Auto-destroy after N minutes

For the first strict version, require a Dockerfile and reject unsupported repositories quickly.

### Phase 2

Curated one-click templates (WordPress, Immich, Plane, Open WebUI, AppFlowy, NocoDB, and similar) for rapid adoption.

### Phase 3

Snapshots and conversion to longer-lived deployments:

```text
Try
↓
Love it
↓
Keep it
```

## Hard problems to handle from day one

- **Cost control**: enforce CPU limits, memory limits, runtime limits, and automatic shutdowns
- **Arbitrary repositories**: start narrow (Dockerfile required), then expand support over time
- **Security**: strict isolation, no privileged containers, egress controls, resource quotas, and abuse detection

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

# launch a repository execution session
curl -X POST http://127.0.0.1:8080/api/execution/launch \
  -H 'content-type: application/json' \
  -d '{"repoUrl":"https://github.com/org/project"}'

# check execution session status
curl http://127.0.0.1:8080/api/execution/<session_id>

# destroy execution session
curl -X DELETE http://127.0.0.1:8080/api/execution/<session_id>

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
