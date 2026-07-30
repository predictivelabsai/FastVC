# FastVC

FastVC is an AI workspace for venture investment teams. It adapts the proven
PEHero workflow to a narrower startup-investing domain: thesis-led discovery,
founder and fundraising signals, screening, round construction, diligence,
investment committee, LP relations and portfolio support.

## Product surface

- Startup discovery by thesis, sector, geography, stage and momentum
- Saved searches, alert cadence, company signals, founder profiles and warm paths
- Pipeline from discovered through Series C/growth investment and exit
- 25 venture-native agents across sourcing, ownership, diligence, IC/LP and portfolio
- Round, option-pool, dilution, pro-rata and probability-weighted outcome modelling
- Data-room upload and retrieval with cited source evidence
- LP/family-office CRM and LP-update workflows, without tax functionality
- BYOK adapter stubs for Affinity, Attio, Pipedrive and Brevo
- English plus the PEHero multilingual UI framework

The app uses the `fastvc` OLTP schema and `fastvc_rag` vector schema. Both are
separate from PEHero while using the same PostgreSQL database configured by
`DB_URL`.

## Run locally

```bash
cp .env.example .env
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m db.migrate
.venv/bin/python -m synthetic.generate --seed 42 --skip-rag
.venv/bin/python main.py
```

Open `http://localhost:5059`. The debug health check is
`http://localhost:5059/app/_debug/ping`.
The container and reverse-proxy health endpoint is
`http://localhost:5059/healthz`.

Required configuration:

- `DB_URL`
- `XAI_API_KEY` for live agent responses
- `APP_SECRET` for sessions and per-user integration-key encryption

Optional configuration includes Tavily or Exa search, Google OAuth, Postmark,
and global Affinity/Attio/Pipedrive/Brevo credentials. Users may instead add
their own integration keys in `/app/integrations`; the current provider
adapters validate and store configuration but do not initiate live sync.

## Repository map

```text
agents/       25 specialist agent definitions and intent routing
chat/         app workspaces: discovery, signals, pipeline, models, LPs
db/           idempotent fastvc and fastvc_rag schema migrations
prompts/      venture vocabulary plus specialist operating instructions
synthetic/    deterministic startup, founder, round and signal corpus
tools/        startup, round, diligence, LP and integration tools
landing/      public product pages
tests/        routing, agent construction, tools and UI smoke coverage
```

## Production deployment

FastVC deploys from `main` to Coolify using the repository `Dockerfile`. The
canonical production origin is `https://vc.fastsme.com`, the exposed container
port is `5059`, and the health path is `/healthz`. Set the variables listed in
`.env.coolify.sample`; `docker-entrypoint.sh` runs the idempotent schema
migration before starting the application. An authenticated GitHub Actions
job automatically deploys updates to `main` after CI passes.

## Safety and data boundaries

- Always schema-qualify SQL with `fastvc.*` or `fastvc_rag.*`.
- Treat generated screens and synthetic signals as research leads, not verified facts.
- Keep evidence and assumptions separate in investment outputs.
- Round and outcome models are illustrative and require legal, tax and fund-model review.
- Provider API keys are encrypted at rest and are never rendered back to the browser.
