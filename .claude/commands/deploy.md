# Deploy

Deploy FastVC to production via Coolify (Docker).

## Local Docker test

```bash
docker compose up --build
```

## Production (Coolify)

FastVC runs on Coolify with these environment variables:

- `DB_URL` — PostgreSQL connection string
- `XAI_API_KEY` — xAI Grok API key
- `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` — Google OAuth
- `SERVICE_URL` — public URL (`https://vc.fastsme.com`)
- `POSTMARK_API_TOKEN` — email delivery
- `DIGEST_ENABLED` — 1/0, daily deals email
- `DIGEST_HOUR` — hour in EET (default 7)

Domain: `vc.fastsme.com`, port `5059`, health path `/healthz`.

## Deployment steps

1. Push to `main` — Coolify auto-deploys
2. `docker-entrypoint.sh` runs `db.migrate` on start
3. Synthetic seed is manual: `docker compose exec web python -m synthetic.generate --seed 42`

After CI passes, GitHub Actions calls the FastSME Coolify deployment API using
the encrypted `COOLIFY_WEBHOOK_URL` and `COOLIFY_TOKEN` repository secrets.

## Pre-push checklist

```bash
# Dependency check
.venv/bin/python -c "..." # (see CLAUDE.md)

# Smoke tests
pytest -q tests/test_agents_smoke.py

# Boot check
.venv/bin/python -c "from app import app; ..."

# Push
git push origin main
```
