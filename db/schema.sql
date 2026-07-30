-- FastVC OLTP schema. Idempotent. Always qualify with `fastvc.` —
-- never rely on `search_path`.

CREATE SCHEMA IF NOT EXISTS fastvc;

-- ── users + sessions ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT        NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fastvc.chat_sessions (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES fastvc.users(id) ON DELETE CASCADE,
    agent_slug   TEXT,
    title        TEXT,
    share_token  TEXT        UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_sessions_user_idx ON fastvc.chat_sessions(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS fastvc.chat_messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  BIGINT NOT NULL REFERENCES fastvc.chat_sessions(id) ON DELETE CASCADE,
    role        TEXT   NOT NULL,   -- user | assistant | tool | system
    content     TEXT   NOT NULL,
    tool_calls  JSONB,
    agent_slug  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_messages_session_idx ON fastvc.chat_messages(session_id, id);

-- ── portfolio companies (deal universe) ───────────────────────────────
-- Each row is either a target in the pipeline or a held portfolio company.
CREATE TABLE IF NOT EXISTS fastvc.companies (
    id             BIGSERIAL PRIMARY KEY,
    slug           TEXT UNIQUE NOT NULL,
    name           TEXT NOT NULL,
    hq_city        TEXT,
    hq_state       TEXT,
    country        TEXT,
    sector         TEXT NOT NULL,    -- enterprise_ai | fintech | healthtech | climate | devtools | consumer | deeptech
    sub_sector     TEXT,
    startup_stage  TEXT,             -- stealth | pre_seed | seed | series_a | series_b | series_c | growth
    business_model TEXT,             -- b2b_saas | marketplace | usage_based | fintech | consumer | hardware
    website        TEXT,
    founded_year   INTEGER,
    employees      INTEGER,
    revenue_ltm    NUMERIC(14,2),       -- latest 12 months revenue, USD
    ebitda_ltm     NUMERIC(14,2),
    ebitda_margin  NUMERIC(5,2),
    growth_rate    NUMERIC(5,2),        -- LTM YoY revenue growth, pct
    arr            NUMERIC(14,2),
    mrr            NUMERIC(14,2),
    gross_margin   NUMERIC(5,2),
    net_burn       NUMERIC(14,2),
    runway_months  NUMERIC(6,1),
    burn_multiple  NUMERIC(6,2),
    net_retention  NUMERIC(5,2),
    gross_retention NUMERIC(5,2),
    total_funding  NUMERIC(14,2),
    last_round_date DATE,
    last_round_type TEXT,
    last_round_amount NUMERIC(14,2),
    pre_money_valuation NUMERIC(14,2),
    post_money_valuation NUMERIC(14,2),
    target_check_size NUMERIC(14,2),
    target_ownership_pct NUMERIC(5,2),
    fundraising_status TEXT,            -- not_raising | preparing | raising | closing | recently_funded
    momentum_score NUMERIC(5,2),
    thesis_score   NUMERIC(5,2),
    ownership      TEXT,                -- founder_owned | angel_backed | vc_backed | accelerator | corporate
    deal_stage     TEXT,                -- discovered | screened | first_meeting | partner_meeting | diligence | ic | term_sheet | invested | follow_on | exited | passed
    deal_type      TEXT,                -- primary | secondary | safe | convertible_note | priced_round
    enterprise_value NUMERIC(14,2),     -- compatibility field; generally post-money valuation
    ask_multiple   NUMERIC(6,2),        -- compatibility field; generally EV / ARR
    fund_id        BIGINT,              -- soft ref: fastvc.funds(id)
    description    TEXT,
    seller_intent  TEXT,                -- compatibility field; cold | warm | hot fundraising signal
    triage_score   NUMERIC(4,2),        -- weighted 1.0–5.0 priority score
    triage_priority TEXT,               -- High (≥4) | Medium (≥3) | Low (<3)
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS companies_sector_idx  ON fastvc.companies(sector);
CREATE INDEX IF NOT EXISTS companies_stage_idx   ON fastvc.companies(deal_stage);
CREATE INDEX IF NOT EXISTS companies_geo_idx     ON fastvc.companies(country, hq_state);
CREATE INDEX IF NOT EXISTS companies_triage_idx  ON fastvc.companies(triage_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS companies_startup_stage_idx ON fastvc.companies(startup_stage);
CREATE INDEX IF NOT EXISTS companies_momentum_idx ON fastvc.companies(momentum_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS companies_fundraising_idx ON fastvc.companies(fundraising_status);

-- ── funds (GP side: what's deploying) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.funds (
    id             BIGSERIAL PRIMARY KEY,
    slug           TEXT UNIQUE NOT NULL,
    name           TEXT NOT NULL,
    vintage        INTEGER,
    size_usd       NUMERIC(14,2),
    strategy       TEXT,              -- pre_seed | seed | early_stage | multi_stage | growth
    dry_powder     NUMERIC(14,2),
    called_pct     NUMERIC(5,2),
    invested_pct   NUMERIC(5,2),
    net_irr        NUMERIC(5,2),
    net_moic       NUMERIC(5,2),
    dpi            NUMERIC(5,2),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── cap tables (equity ownership snapshots) ───────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.cap_tables (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT      NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    as_of_date   DATE        NOT NULL,
    holders      JSONB       NOT NULL,    -- [{holder, class, shares, fd_pct, capital_in, liquidation_pref, last_round}]
    total_shares BIGINT,
    post_money   NUMERIC(14,2),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, as_of_date)
);

-- ── venture funding history ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.funding_rounds (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    announced_date  DATE,
    round_type      TEXT NOT NULL,     -- pre_seed | seed | series_a | series_b | series_c | growth | safe | note
    amount_raised   NUMERIC(14,2),
    pre_money       NUMERIC(14,2),
    post_money      NUMERIC(14,2),
    lead_investor   TEXT,
    participating_investors TEXT[],
    instrument      TEXT,              -- preferred_equity | safe | convertible_note | common
    source          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(company_id, announced_date, round_type)
);
CREATE INDEX IF NOT EXISTS funding_rounds_company_idx
    ON fastvc.funding_rounds(company_id, announced_date DESC);

-- ── founders, operators and warm-network paths ──────────────────────
CREATE TABLE IF NOT EXISTS fastvc.founders (
    id              BIGSERIAL PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    title           TEXT,
    email           TEXT,
    linkedin_url    TEXT,
    location        TEXT,
    education       JSONB NOT NULL DEFAULT '[]',
    prior_companies JSONB NOT NULL DEFAULT '[]',
    repeat_founder  BOOLEAN NOT NULL DEFAULT FALSE,
    technical       BOOLEAN NOT NULL DEFAULT FALSE,
    founder_score   NUMERIC(5,2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fastvc.founder_company_links (
    founder_id      BIGINT NOT NULL REFERENCES fastvc.founders(id) ON DELETE CASCADE,
    company_id      BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    role            TEXT NOT NULL DEFAULT 'co_founder',
    started_at      DATE,
    ended_at        DATE,
    ownership_pct   NUMERIC(5,2),
    PRIMARY KEY(founder_id, company_id)
);
CREATE INDEX IF NOT EXISTS founder_company_company_idx
    ON fastvc.founder_company_links(company_id);

CREATE TABLE IF NOT EXISTS fastvc.team_connections (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES fastvc.users(id) ON DELETE CASCADE,
    founder_id      BIGINT REFERENCES fastvc.founders(id) ON DELETE CASCADE,
    company_id      BIGINT REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    connector_name  TEXT NOT NULL,
    connector_email TEXT,
    relationship    TEXT,              -- emailed | met | linkedin | portfolio | lp | colleague
    strength        INTEGER CHECK (strength BETWEEN 1 AND 5),
    last_interaction DATE,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS team_connections_company_idx
    ON fastvc.team_connections(company_id, strength DESC);

-- ── historical financials (monthly, LTM-building block) ───────────────
CREATE TABLE IF NOT EXISTS fastvc.financials (
    id             BIGSERIAL PRIMARY KEY,
    company_id     BIGINT      NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    month          DATE        NOT NULL,   -- first-of-month
    revenue        NUMERIC(14,2),
    cogs           NUMERIC(14,2),
    gross_profit   NUMERIC(14,2),
    opex           JSONB,                  -- {sales, marketing, rnd, ga, other}
    ebitda         NUMERIC(14,2),
    adjustments    JSONB,                  -- non-recurring items, owner add-backs
    adj_ebitda     NUMERIC(14,2),
    arr            NUMERIC(14,2),          -- for SaaS/recurring
    gross_retention NUMERIC(5,2),
    net_retention  NUMERIC(5,2),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, month)
);
CREATE INDEX IF NOT EXISTS financials_company_month_idx ON fastvc.financials(company_id, month DESC);

-- ── material contracts (customers, suppliers, key employees) ──────────
CREATE TABLE IF NOT EXISTS fastvc.contracts (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    counterparty TEXT,
    contract_type TEXT,     -- customer_msa | supplier | employment | license | lease | loan | other
    start_date   DATE,
    end_date     DATE,
    annual_value NUMERIC(14,2),
    auto_renew   BOOLEAN,
    change_of_control_trigger BOOLEAN,
    termination_notice_days INTEGER,
    exclusivity  BOOLEAN,
    status       TEXT,         -- active | expired | pending | terminated
    doc_path     TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS contracts_company_idx      ON fastvc.contracts(company_id);
CREATE INDEX IF NOT EXISTS contracts_counterparty_idx ON fastvc.contracts(counterparty);

-- ── transaction comps (M&A deal comparables) ──────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.transaction_comps (
    id             BIGSERIAL PRIMARY KEY,
    company_id     BIGINT REFERENCES fastvc.companies(id) ON DELETE SET NULL,
    target_name    TEXT,
    acquirer       TEXT,
    sector         TEXT,
    sub_sector     TEXT,
    country        TEXT,
    announce_date  DATE,
    close_date     DATE,
    enterprise_value NUMERIC(14,2),
    revenue        NUMERIC(14,2),
    ebitda         NUMERIC(14,2),
    ev_revenue     NUMERIC(6,2),
    ev_ebitda      NUMERIC(6,2),
    deal_type      TEXT,             -- pe_buyout | strategic | ipo | growth
    source         TEXT
);
CREATE INDEX IF NOT EXISTS txn_comps_sector_idx ON fastvc.transaction_comps(sector, announce_date DESC);

-- ── trading comps (public company multiples) ──────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.trading_comps (
    id             BIGSERIAL PRIMARY KEY,
    company_id     BIGINT REFERENCES fastvc.companies(id) ON DELETE SET NULL,
    ticker         TEXT,
    peer_name      TEXT,
    sector         TEXT,
    market_cap     NUMERIC(14,2),
    ev             NUMERIC(14,2),
    revenue_ltm    NUMERIC(14,2),
    ebitda_ltm     NUMERIC(14,2),
    ev_revenue     NUMERIC(6,2),
    ev_ebitda      NUMERIC(6,2),
    rev_growth     NUMERIC(5,2),
    ebitda_margin  NUMERIC(5,2),
    as_of_date     DATE,
    source         TEXT
);
CREATE INDEX IF NOT EXISTS trading_comps_sector_idx ON fastvc.trading_comps(sector);

-- ── LBO models + sensitivity ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.lbo_models (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    name         TEXT,
    assumptions  JSONB NOT NULL,  -- {hold_years, entry_multiple, entry_ev, ebitda_growth, margin_exp, capex_pct, wc_days, exit_multiple, tax_rate}
    projections  JSONB NOT NULL,  -- [{year, revenue, ebitda, capex, fcf, debt_paydown, net_debt}]
    returns      JSONB NOT NULL,  -- {irr, moic, levered_irr, unlevered_irr, equity_multiple, dscr_min}
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Venture-native round construction and ownership/outcome scenarios.
CREATE TABLE IF NOT EXISTS fastvc.round_models (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    name            TEXT,
    round_type      TEXT NOT NULL,
    pre_money       NUMERIC(14,2) NOT NULL,
    raise_amount    NUMERIC(14,2) NOT NULL,
    new_money       JSONB NOT NULL DEFAULT '[]',
    option_pool_pre_pct NUMERIC(5,2),
    option_pool_post_pct NUMERIC(5,2),
    pro_rata        JSONB NOT NULL DEFAULT '[]',
    ownership       JSONB NOT NULL DEFAULT '[]',
    dilution        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fastvc.outcome_models (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    round_model_id  BIGINT REFERENCES fastvc.round_models(id) ON DELETE SET NULL,
    scenarios       JSONB NOT NULL,     -- exit values, probabilities, future dilution
    fund_returns    JSONB NOT NULL,     -- proceeds, MOIC, IRR, ownership bridge
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── debt stacks for LBO capital structure ─────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.debt_stacks (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    name         TEXT,
    tranches     JSONB NOT NULL,  -- [{name, lender, type, amount, rate, amort_years, term_years, io_years, covenants}]
    total_debt   NUMERIC(14,2),
    total_leverage NUMERIC(5,2),     -- debt / EBITDA turns
    dscr         NUMERIC(5,2),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── LP CRM ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.investor_crm (
    id            BIGSERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    firm          TEXT,
    lp_type       TEXT,          -- pension | endowment | fof | family_office | sovereign | insurance | hnw
    email         TEXT,
    commitment_size NUMERIC(14,2),
    stage         TEXT,          -- cold | qualified | meeting | dd | committed | closed | passed
    focus         TEXT,          -- venture | seed | early_stage | multi_stage | growth
    geography     TEXT,
    aum           NUMERIC(14,2),
    last_touch    DATE,
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS crm_stage_idx ON fastvc.investor_crm(stage);

-- ── market signals (sector heat, multiples, fundraising env) ──────────
CREATE TABLE IF NOT EXISTS fastvc.market_signals (
    id           BIGSERIAL PRIMARY KEY,
    sector       TEXT NOT NULL,
    sub_sector   TEXT,
    metric       TEXT NOT NULL,   -- ev_ebitda_median | ev_revenue_median | deal_volume | fundraising_close_time | exit_multiples | hold_period
    value        NUMERIC(14,4),
    as_of_date   DATE NOT NULL,
    source       TEXT,
    UNIQUE (sector, sub_sector, metric, as_of_date)
);
CREATE INDEX IF NOT EXISTS market_signals_lookup_idx ON fastvc.market_signals(sector, metric, as_of_date DESC);

-- ── thesis discovery, saved searches and company-level signals ──────
CREATE TABLE IF NOT EXISTS fastvc.saved_searches (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES fastvc.users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    thesis          TEXT NOT NULL,
    filters         JSONB NOT NULL DEFAULT '{}',
    alert_frequency TEXT NOT NULL DEFAULT 'weekly', -- realtime | daily | weekly | off
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS saved_searches_user_idx ON fastvc.saved_searches(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS fastvc.startup_signals (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    signal_type     TEXT NOT NULL,      -- formation | founder_move | key_hire | headcount | funding | launch | traction
    title           TEXT NOT NULL,
    detail          TEXT,
    signal_date     DATE NOT NULL,
    strength        NUMERIC(5,2),
    source          TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(company_id, signal_type, title, signal_date)
);
CREATE INDEX IF NOT EXISTS startup_signals_recent_idx
    ON fastvc.startup_signals(signal_date DESC, strength DESC);

CREATE TABLE IF NOT EXISTS fastvc.market_maps (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES fastvc.users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    thesis          TEXT,
    axes            JSONB NOT NULL DEFAULT '{}',
    company_ids     BIGINT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── diligence findings ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.dd_findings (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    agent_slug   TEXT NOT NULL,
    category     TEXT NOT NULL,   -- legal | tax | commercial | financial | operational | esg | it | hr
    severity     TEXT NOT NULL,   -- info | low | medium | high | critical
    summary      TEXT NOT NULL,
    detail       TEXT,
    source_doc   TEXT,
    source_page  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dd_company_idx ON fastvc.dd_findings(company_id, severity);

-- ── deal risks (P×I scoring) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.deal_risks (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    probability     INTEGER CHECK (probability BETWEEN 1 AND 5),
    impact          INTEGER CHECK (impact BETWEEN 1 AND 5),
    category        TEXT,
    mitigation      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS deal_risks_company_idx ON fastvc.deal_risks(company_id);

-- ── deal milestones (progress tracking) ─────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.deal_milestones (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    due_date        DATE,
    owner           TEXT,
    pct_complete    INTEGER DEFAULT 0 CHECK (pct_complete BETWEEN 0 AND 100),
    status          TEXT DEFAULT 'open',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS deal_milestones_company_idx ON fastvc.deal_milestones(company_id);

-- ── board / portfolio KPIs (post-close operational data) ──────────────
CREATE TABLE IF NOT EXISTS fastvc.portfolio_kpis (
    id           BIGSERIAL PRIMARY KEY,
    company_id   BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    month        DATE NOT NULL,
    kpi          TEXT NOT NULL,        -- arr | churn | cac | ltv | headcount | nps | gross_margin | ebitda_budget_variance
    value        NUMERIC(14,4),
    budget       NUMERIC(14,4),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, month, kpi)
);
CREATE INDEX IF NOT EXISTS portfolio_kpis_company_idx ON fastvc.portfolio_kpis(company_id, month DESC);

-- ── prompt versions (audit trail for system prompts) ──────────────────
CREATE TABLE IF NOT EXISTS fastvc.prompt_versions (
    id          BIGSERIAL PRIMARY KEY,
    slug        TEXT        NOT NULL,
    content     TEXT        NOT NULL,
    changed_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS prompt_versions_slug_idx ON fastvc.prompt_versions(slug, id DESC);

-- ── data room (document uploads) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.data_room (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT      REFERENCES fastvc.users(id) ON DELETE CASCADE,
    company_slug TEXT,
    filename     TEXT        NOT NULL,
    content_type TEXT        NOT NULL DEFAULT 'application/octet-stream',
    size_bytes   INTEGER,
    data         BYTEA       NOT NULL,
    uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS data_room_user_idx ON fastvc.data_room(user_id, uploaded_at DESC);

-- ── agent invocation log ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.agent_invocations (
    id           BIGSERIAL PRIMARY KEY,
    session_id   BIGINT REFERENCES fastvc.chat_sessions(id) ON DELETE CASCADE,
    agent_slug   TEXT NOT NULL,
    input        TEXT,
    tools_used   TEXT[],
    duration_ms  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_invocations_session_idx ON fastvc.agent_invocations(session_id, created_at DESC);

-- ── Pipedrive CRM sync ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.pipedrive_sync (
    id             BIGSERIAL PRIMARY KEY,
    entity_type    TEXT NOT NULL,          -- company | investor | deal | contact
    fastvc_id      BIGINT NOT NULL,
    pipedrive_id   BIGINT NOT NULL,
    pipedrive_type TEXT NOT NULL,          -- organization | person | deal | activity
    last_synced    TIMESTAMPTZ NOT NULL DEFAULT now(),
    sync_hash      TEXT,
    UNIQUE(entity_type, fastvc_id)
);
CREATE INDEX IF NOT EXISTS pd_sync_pd_idx ON fastvc.pipedrive_sync(pipedrive_id, pipedrive_type);

CREATE TABLE IF NOT EXISTS fastvc.outreach_sequences (
    id             BIGSERIAL PRIMARY KEY,
    company_id     BIGINT REFERENCES fastvc.companies(id) ON DELETE CASCADE,
    investor_id    BIGINT REFERENCES fastvc.investor_crm(id) ON DELETE CASCADE,
    sequence_type  TEXT NOT NULL,          -- deal_sourcing | lp_fundraising
    status         TEXT NOT NULL DEFAULT 'active',  -- active | paused | completed
    touches        JSONB NOT NULL DEFAULT '[]',     -- [{day, subject, body, framework, sent, sent_at}]
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS outreach_seq_company_idx ON fastvc.outreach_sequences(company_id);
CREATE INDEX IF NOT EXISTS outreach_seq_investor_idx ON fastvc.outreach_sequences(investor_id);

-- ── User integrations (per-user API tokens) ─────────────────────────
CREATE TABLE IF NOT EXISTS fastvc.user_integrations (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES fastvc.users(id) ON DELETE CASCADE,
    provider    TEXT        NOT NULL,     -- pipedrive | hubspot | salesforce | ...
    api_token   TEXT        NOT NULL,     -- encrypted at rest by tools.integrations
    domain      TEXT,                     -- e.g. "predictivelabsltd" for Pipedrive
    metadata    JSONB       DEFAULT '{}', -- extra provider-specific config
    status      TEXT        NOT NULL DEFAULT 'configured',
    last_tested TIMESTAMPTZ,
    last_error  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, provider)
);

-- ── Persons (investor prospecting — owners, directors, HNW) ─────────
CREATE TABLE IF NOT EXISTS fastvc.persons (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    slug            TEXT UNIQUE NOT NULL,
    country         TEXT DEFAULT 'EE',
    wealth_eur      NUMERIC(14,2),
    wealth_rank     INTEGER,
    wealth_source   TEXT,
    sector_exposure TEXT[],
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS persons_slug_idx ON fastvc.persons(slug);
CREATE INDEX IF NOT EXISTS persons_wealth_idx ON fastvc.persons(wealth_eur DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS fastvc.person_company_links (
    id              BIGSERIAL PRIMARY KEY,
    person_id       BIGINT NOT NULL REFERENCES fastvc.persons(id) ON DELETE CASCADE,
    company_id      BIGINT REFERENCES fastvc.companies(id) ON DELETE SET NULL,
    company_name    TEXT NOT NULL,
    reg_code        TEXT,
    role            TEXT NOT NULL,
    stake_pct       NUMERIC(5,2),
    control_desc    TEXT,
    UNIQUE(person_id, company_name, role)
);
CREATE INDEX IF NOT EXISTS pcl_person_idx ON fastvc.person_company_links(person_id);
CREATE INDEX IF NOT EXISTS pcl_company_idx ON fastvc.person_company_links(company_id);
