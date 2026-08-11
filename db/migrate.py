"""Apply schema.sql + rag_schema.sql idempotently.

Usage:
    python -m db.migrate          # apply both
    python -m db.migrate --drop   # DANGER: drops fastvc schemas first
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from db import connect
from utils.config import settings

log = logging.getLogger(__name__)

SCHEMA_FILES = [
    Path(__file__).with_name("schema.sql"),
    Path(__file__).with_name("rag_schema.sql"),
]


def _apply(sql: str) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def _render(path: Path) -> str:
    text = path.read_text()
    return text.replace("{{EMBEDDING_DIM}}", str(settings().embedding_dim))


def migrate(drop: bool = False) -> None:
    if drop:
        print("dropping fastvc + fastvc_rag schemas…")
        _apply("DROP SCHEMA IF EXISTS fastvc_rag CASCADE; DROP SCHEMA IF EXISTS fastvc CASCADE;")

    for f in SCHEMA_FILES:
        print(f"applying {f.name} (embedding_dim={settings().embedding_dim})")
        _apply(_render(f))

    # Incremental column additions (idempotent).
    _apply("""
        ALTER TABLE fastvc.chat_sessions
            ADD COLUMN IF NOT EXISTS share_token TEXT UNIQUE;
    """)

    _apply("""
        ALTER TABLE fastvc.users
            ADD COLUMN IF NOT EXISTS password_hash TEXT;
        ALTER TABLE fastvc.users
            ADD COLUMN IF NOT EXISTS name VARCHAR(200);
        ALTER TABLE fastvc.users
            ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
        ALTER TABLE fastvc.users
            ADD COLUMN IF NOT EXISTS verify_token VARCHAR(64);
        ALTER TABLE fastvc.users
            ADD COLUMN IF NOT EXISTS reset_token VARCHAR(64);
        ALTER TABLE fastvc.users
            ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMPTZ;
    """)

    _apply("""
        CREATE TABLE IF NOT EXISTS fastvc.user_preferences (
            id              SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL UNIQUE REFERENCES fastvc.users(id),
            phone           VARCHAR(30),
            company         VARCHAR(200),
            role            VARCHAR(200),
            country         VARCHAR(5),
            city            VARCHAR(100),
            currency        VARCHAR(3) DEFAULT 'USD',
            language        VARCHAR(5) DEFAULT 'en',
            deal_size_min   NUMERIC(14,2),
            deal_size_max   NUMERIC(14,2),
            revenue_min     NUMERIC(14,2),
            revenue_max     NUMERIC(14,2),
            ebitda_min      NUMERIC(14,2),
            ebitda_max      NUMERIC(14,2),
            preferred_sectors    JSONB DEFAULT '[]',
            preferred_deal_types JSONB DEFAULT '[]',
            preferred_geographies JSONB DEFAULT '[]',
            preferred_stage      VARCHAR(30),
            notify_new_deals     BOOLEAN DEFAULT TRUE,
            notify_deal_updates  BOOLEAN DEFAULT TRUE,
            notify_weekly_digest BOOLEAN DEFAULT TRUE,
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    _apply("""
        ALTER TABLE fastvc.user_preferences
            ADD COLUMN IF NOT EXISTS unsubscribe_token VARCHAR(64) UNIQUE;
        ALTER TABLE fastvc.user_preferences
            ADD COLUMN IF NOT EXISTS news_source_ids JSONB DEFAULT '[]'::jsonb;
    """)

    _apply("""
        ALTER TABLE fastvc.user_integrations
            ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'configured';
        ALTER TABLE fastvc.user_integrations
            ADD COLUMN IF NOT EXISTS last_tested TIMESTAMPTZ;
        ALTER TABLE fastvc.user_integrations
            ADD COLUMN IF NOT EXISTS last_error TEXT;
    """)

    _apply("""
        CREATE TABLE IF NOT EXISTS fastvc.user_credentials (
            id              BIGSERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES fastvc.users(id) ON DELETE CASCADE,
            provider        TEXT NOT NULL,
            label           TEXT NOT NULL,
            login_url       TEXT,
            secret_payload  TEXT NOT NULL,
            metadata        JSONB NOT NULL DEFAULT '{}',
            status          TEXT NOT NULL DEFAULT 'configured',
            last_verified   TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(user_id, provider)
        );
        CREATE INDEX IF NOT EXISTS user_credentials_user_idx
            ON fastvc.user_credentials(user_id);
    """)

    _apply("""
        CREATE TABLE IF NOT EXISTS fastvc.digest_sends (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES fastvc.users(id),
            subject     TEXT,
            message_id  TEXT,
            sent_at     TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # Deal risks and milestones tables.
    _apply("""
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
    """)

    # Triage scoring columns on companies.
    _apply("""
        ALTER TABLE fastvc.companies
            ADD COLUMN IF NOT EXISTS triage_score NUMERIC(4,2);
        ALTER TABLE fastvc.companies
            ADD COLUMN IF NOT EXISTS triage_priority TEXT;
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS startup_stage TEXT;
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS business_model TEXT;
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS arr NUMERIC(14,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS mrr NUMERIC(14,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS gross_margin NUMERIC(5,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS net_burn NUMERIC(14,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS runway_months NUMERIC(6,1);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS burn_multiple NUMERIC(6,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS net_retention NUMERIC(5,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS gross_retention NUMERIC(5,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS total_funding NUMERIC(14,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS last_round_date DATE;
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS last_round_type TEXT;
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS last_round_amount NUMERIC(14,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS pre_money_valuation NUMERIC(14,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS post_money_valuation NUMERIC(14,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS target_check_size NUMERIC(14,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS target_ownership_pct NUMERIC(5,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS fundraising_status TEXT;
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS momentum_score NUMERIC(5,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS thesis_score NUMERIC(5,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS data_source TEXT;
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS source_quality NUMERIC(5,2);
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMPTZ;
        ALTER TABLE fastvc.companies ADD COLUMN IF NOT EXISTS registry_status TEXT;
    """)

    _apply("""
        CREATE TABLE IF NOT EXISTS fastvc.ingestion_runs (
            id BIGSERIAL PRIMARY KEY,
            provider TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'ingest',
            status TEXT NOT NULL DEFAULT 'running',
            requested_limit INTEGER,
            processed INTEGER NOT NULL DEFAULT 0,
            inserted INTEGER NOT NULL DEFAULT 0,
            updated INTEGER NOT NULL DEFAULT 0,
            skipped INTEGER NOT NULL DEFAULT 0,
            errors INTEGER NOT NULL DEFAULT 0,
            credits_used NUMERIC(12,2) NOT NULL DEFAULT 0,
            cursor TEXT,
            error_detail TEXT,
            metadata JSONB NOT NULL DEFAULT '{}',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS ingestion_runs_provider_idx
            ON fastvc.ingestion_runs(provider, started_at DESC);

        CREATE TABLE IF NOT EXISTS fastvc.company_identifiers (
            id BIGSERIAL PRIMARY KEY,
            company_id BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
            source TEXT NOT NULL,
            country_code TEXT NOT NULL,
            identifier_type TEXT NOT NULL,
            identifier_value TEXT NOT NULL,
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            source_url TEXT,
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(source, country_code, identifier_type, identifier_value)
        );
        CREATE INDEX IF NOT EXISTS company_identifiers_company_idx
            ON fastvc.company_identifiers(company_id);
        CREATE INDEX IF NOT EXISTS company_identifiers_lookup_idx
            ON fastvc.company_identifiers(country_code, identifier_type, identifier_value);

        CREATE TABLE IF NOT EXISTS fastvc.company_source_records (
            id BIGSERIAL PRIMARY KEY,
            company_id BIGINT REFERENCES fastvc.companies(id) ON DELETE CASCADE,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            source_url TEXT,
            payload JSONB NOT NULL DEFAULT '{}',
            payload_hash TEXT NOT NULL,
            license TEXT,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(source, external_id, payload_hash)
        );
        CREATE INDEX IF NOT EXISTS company_source_records_company_idx
            ON fastvc.company_source_records(company_id, fetched_at DESC);

        CREATE TABLE IF NOT EXISTS fastvc.company_financial_periods (
            id BIGSERIAL PRIMARY KEY,
            company_id BIGINT NOT NULL REFERENCES fastvc.companies(id) ON DELETE CASCADE,
            period_end DATE NOT NULL,
            period_type TEXT NOT NULL DEFAULT 'annual',
            currency TEXT NOT NULL DEFAULT 'EUR',
            revenue NUMERIC(18,2),
            gross_profit NUMERIC(18,2),
            profit_before_tax NUMERIC(18,2),
            net_profit NUMERIC(18,2),
            total_assets NUMERIC(18,2),
            current_assets NUMERIC(18,2),
            non_current_assets NUMERIC(18,2),
            liabilities NUMERIC(18,2),
            equity NUMERIC(18,2),
            employees INTEGER,
            source TEXT NOT NULL,
            source_external_id TEXT,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(company_id, period_end, period_type, source)
        );
        CREATE INDEX IF NOT EXISTS company_financial_periods_company_idx
            ON fastvc.company_financial_periods(company_id, period_end DESC);
    """)

    # Persons tables for investor prospecting.
    _apply("""
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
    """)

    # Seed existing prompt files as v1 if prompt_versions is empty.
    _seed_prompt_versions()

    print("migration complete")


def _seed_prompt_versions() -> None:
    """Record each changed filesystem prompt as a new auditable version."""
    from pathlib import Path
    prompts_dir = Path(__file__).resolve().parent.parent / "prompts" / "system"
    shared_path = Path(__file__).resolve().parent.parent / "prompts" / "shared" / "vc_context.md"

    with connect() as conn, conn.cursor() as cur:
        seeded = 0
        for md in sorted(prompts_dir.glob("*.md")):
            slug = md.stem
            content = md.read_text()
            cur.execute(
                "SELECT content FROM fastvc.prompt_versions WHERE slug=%s ORDER BY id DESC LIMIT 1",
                (slug,),
            )
            latest = cur.fetchone()
            if not latest or latest[0] != content:
                cur.execute(
                    "INSERT INTO fastvc.prompt_versions (slug, content, changed_by) VALUES (%s, %s, %s)",
                    (slug, content, "migration"),
                )
                seeded += 1

        if shared_path.exists():
            content = shared_path.read_text()
            cur.execute(
                "SELECT content FROM fastvc.prompt_versions WHERE slug='__shared__' ORDER BY id DESC LIMIT 1"
            )
            latest = cur.fetchone()
            if not latest or latest[0] != content:
                cur.execute(
                    "INSERT INTO fastvc.prompt_versions (slug, content, changed_by) VALUES (%s, %s, %s)",
                    ("__shared__", content, "migration"),
                )
                seeded += 1

        conn.commit()
        if seeded:
            print(f"  seeded {seeded} prompt versions")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true", help="drop fastvc schemas first")
    args = ap.parse_args()
    migrate(drop=args.drop)
