# Deploying

Production runs on the 83RR PowerEdge (repo `MCheli/83rr-poweredge`, `docker-compose.yml`), behind
the host's NGINX with the Cloudflare wildcard certificate. CI publishes `ghcr.io/mcheli/cookbook:latest`
from `main` after tests and an image smoke test (real app and demo) pass; Watchtower deploys it.

## Containers

| Service | What | Notes |
|---|---|---|
| `cookbook` | the app, port 8000 | `env_file: .env`, healthcheck `/api/health` |
| `cookbook-db` | Postgres 16, db/user `cookbook` | volume `cookbook_db_data` |
| `cookbook-demo` | same image, `COOKBOOK_DEMO_MODE=true` | explicit environment only, never `.env`; restarted nightly to reseed |
| `cookbook-demo-db` | Postgres 16 on an `internal` network | volume `cookbook_demo_db_data` |

Migrations run on start (`alembic upgrade head`). On a fresh database the first
`COOKBOOK_OWNER_EMAILS` address gets the 38 bundled recipes.

## Environment (`COOKBOOK_` prefix)

| Variable | Real | Demo | Notes |
|---|---|---|---|
| `ENV` | `production` | `production` | production refuses default secrets |
| `SITE_URL` | `https://cookbook.markcheli.com` | demo URL | used in schema.org URLs |
| `DATABASE_URL` | `postgresql+asyncpg://cookbook:…@cookbook-db:5432/cookbook` | demo db | |
| `JWT_SECRET` | 64 hex | own | `openssl rand -hex 32` |
| `API_KEY_PEPPER` | 64 hex | own | rotating invalidates API keys |
| `SECRETS_KEY` | 64 hex | own | encrypts users' Anthropic keys; rotating forgets them |
| `COOKIE_SECURE` | `true` | `true` | |
| `ALLOWED_ORIGINS` | site URL | demo URL | |
| `GOOGLE_CLIENT_ID` / `_SECRET` | Google OAuth client | **unset** | demo refuses them |
| `GOOGLE_REDIRECT_URI` | `https://cookbook.markcheli.com/api/auth/google/callback` | unset | must be registered on the OAuth client |
| `OWNER_EMAILS` | Mark's Google address | **unset** | who can publish; first one owns the bundled recipes |
| `DEMO_URL` | `https://cookbook-demo.markcheli.com` | unset | login page links to the demo |
| `DEMO_MODE` | unset | `true` | |
| `AI_MODEL` / `AI_MODEL_SMART` | optional | | defaults `claude-sonnet-5-5` / `claude-opus-5-5` |

There is no server Anthropic key: each user adds their own in Settings.

## NGINX

`cookbook.markcheli.com` proxies to `cookbook:8000` with `client_max_body_size 6M` (photo import)
and `proxy_read_timeout 180s` (AI calls). `cookbook-demo.markcheli.com` proxies to
`cookbook-demo:8000`, `client_max_body_size 1M`, rate-limited like the other demos.

## One-time setup

1. Server `.env`: the secrets above (`COOKBOOK_*`, `COOKBOOK_DEMO_*`), DB passwords.
2. Google Cloud console: add the redirect URI to the OAuth client.
3. Cloudflare: proxied A record `cookbook-demo` like the other demos.
4. Crontab: `0 8 * * * docker restart cookbook-demo` (nightly reseed).
5. Backups: include `cookbook-db` in the nightly Postgres dumps to the NAS.
