"""Encrypted BYOK configuration and provider-neutral integration stubs.

The adapters deliberately stop at credential/configuration boundaries. They
make provider choice explicit without making FastVC depend on any CRM.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken

from db import execute, fetch_all, fetch_one
from utils.config import settings


PROVIDERS = {
    "affinity": {
        "name": "Affinity",
        "kind": "VC relationship CRM",
        "description": "Sync startups, people, interaction history, warm paths and deal stages.",
        "domain_label": "Workspace or tenant (optional)",
        "capabilities": ["companies", "people", "interactions", "warm paths", "pipeline"],
    },
    "attio": {
        "name": "Attio",
        "kind": "Flexible CRM",
        "description": "Map startup, founder, LP and activity objects into a configurable workspace.",
        "domain_label": "Workspace ID (optional)",
        "capabilities": ["companies", "people", "lists", "notes", "pipeline"],
    },
    "pipedrive": {
        "name": "Pipedrive",
        "kind": "Pipeline CRM",
        "description": "Reuse FastVC's mature company, contact, activity and LP pipeline sync.",
        "domain_label": "Company domain",
        "capabilities": ["companies", "people", "deals", "activities", "LP pipeline"],
    },
    "brevo": {
        "name": "Brevo",
        "kind": "Outreach delivery",
        "description": "Hand approved founder and LP sequences to lists, campaigns and transactional email.",
        "domain_label": "Sender identity (optional)",
        "capabilities": ["contacts", "lists", "campaigns", "transactional email", "delivery events"],
    },
}


def _fernet() -> Fernet:
    secret = settings().app_secret
    if not secret or secret == "change-me":
        # Deterministic local-development encryption. Production startup checks
        # and documentation require a unique APP_SECRET.
        secret = "fastvc-local-development-only"
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return "fernet:" + _fernet().encrypt(value.strip().encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    if not value.startswith("fernet:"):
        # Backward-compatible read of a PEHero-era Pipedrive token. Saving it
        # again immediately upgrades it to encrypted storage.
        return value
    try:
        return _fernet().decrypt(value[7:].encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return ("•" * 8) + value[-4:] if len(value) >= 4 else "•" * 8


def mask_identity(value: str) -> str:
    """Mask a login identity while leaving enough context to distinguish it."""
    if not value:
        return ""
    if "@" in value:
        local, domain = value.split("@", 1)
        shown = local[:2] if len(local) > 1 else local[:1]
        return f"{shown}{'•' * max(2, len(local) - len(shown))}@{domain}"
    return f"{value[:2]}{'•' * max(4, len(value) - 2)}"


def save_credential(user_id: int, provider: str, label: str, login_url: str = "",
                    username: str = "", email: str = "", password: str = "",
                    api_key: str = "", metadata: dict | None = None) -> None:
    """Encrypt and upsert a portal credential owned by one FastVC user."""
    if not provider.strip() or not label.strip():
        raise ValueError("provider and label are required")
    if not any((username, email, password, api_key)):
        raise ValueError("at least one credential field is required")
    payload = json.dumps({
        "username": username.strip(),
        "email": email.strip(),
        "password": password,
        "api_key": api_key.strip(),
    })
    execute(
        """INSERT INTO fastvc.user_credentials
           (user_id, provider, label, login_url, secret_payload, metadata,
            status, last_verified)
           VALUES (%s,%s,%s,%s,%s,%s::jsonb,'configured',now())
           ON CONFLICT (user_id, provider) DO UPDATE SET
             label=EXCLUDED.label, login_url=EXCLUDED.login_url,
             secret_payload=EXCLUDED.secret_payload, metadata=EXCLUDED.metadata,
             status='configured', last_verified=now(), updated_at=now()""",
        (user_id, provider.strip().lower(), label.strip(), login_url.strip(),
         encrypt_secret(payload), json.dumps(metadata or {})),
    )


def _credential_view(row: dict) -> dict:
    try:
        payload = json.loads(decrypt_secret(row["secret_payload"]) or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    identity = payload.get("email") or payload.get("username") or ""
    return {
        **row,
        "secret_payload": "",
        "masked_identity": mask_identity(identity),
        "has_password": bool(payload.get("password")),
        "masked_api_key": mask_secret(payload.get("api_key", "")),
    }


def list_credentials(user_id: int) -> list[dict]:
    """Return display-safe credential metadata; plaintext is never returned."""
    rows = fetch_all(
        """SELECT provider,label,login_url,secret_payload,metadata,status,
                  last_verified,created_at,updated_at
           FROM fastvc.user_credentials WHERE user_id=%s ORDER BY label""",
        (user_id,),
    )
    return [_credential_view(row) for row in rows]


def load_credential(user_id: int, provider: str, *, reveal: bool = False) -> dict | None:
    """Load one credential; plaintext is opt-in for server-side provider calls only."""
    row = fetch_one(
        """SELECT provider,label,login_url,secret_payload,metadata,status,
                  last_verified,created_at,updated_at
           FROM fastvc.user_credentials WHERE user_id=%s AND provider=%s""",
        (user_id, provider.strip().lower()),
    )
    if not row:
        return None
    if not reveal:
        return _credential_view(row)
    try:
        payload = json.loads(decrypt_secret(row["secret_payload"]) or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return {**row, "secret_payload": "", **payload}


def save_connection(user_id: int, provider: str, api_key: str,
                    domain: str = "", metadata: dict | None = None) -> None:
    if provider not in PROVIDERS:
        raise ValueError(f"unsupported provider: {provider}")
    if not api_key.strip():
        raise ValueError("API key is required")
    execute(
        """INSERT INTO fastvc.user_integrations
           (user_id, provider, api_token, domain, metadata, status, last_tested, last_error)
           VALUES (%s,%s,%s,%s,%s::jsonb,'configured',now(),NULL)
           ON CONFLICT (user_id, provider) DO UPDATE SET
             api_token=EXCLUDED.api_token, domain=EXCLUDED.domain,
             metadata=EXCLUDED.metadata, status='configured',
             last_tested=now(), last_error=NULL, updated_at=now()""",
        (user_id, provider, encrypt_secret(api_key), domain.strip(),
         json.dumps(metadata or {})),
    )


def delete_connection(user_id: int, provider: str) -> None:
    execute("DELETE FROM fastvc.user_integrations WHERE user_id=%s AND provider=%s",
            (user_id, provider))


def load_connection(user_id: int, provider: str, reveal: bool = False) -> dict | None:
    row = fetch_one(
        """SELECT provider, api_token, domain, metadata, status, last_tested, last_error
           FROM fastvc.user_integrations WHERE user_id=%s AND provider=%s""",
        (user_id, provider),
    )
    if not row:
        return None
    plain = decrypt_secret(row["api_token"])
    return {
        **row,
        "api_key": plain if reveal else "",
        "masked_key": mask_secret(plain),
        "connected": bool(plain),
    }


def list_connections(user_id: int) -> dict[str, dict]:
    rows = fetch_all(
        """SELECT provider, api_token, domain, metadata, status, last_tested, last_error
           FROM fastvc.user_integrations WHERE user_id=%s ORDER BY provider""",
        (user_id,),
    )
    result = {}
    for row in rows:
        plain = decrypt_secret(row["api_token"])
        result[row["provider"]] = {
            **row,
            "api_key": "",
            "masked_key": mask_secret(plain),
            "connected": bool(plain),
        }
    return result


def test_stub(provider: str, api_key: str, domain: str = "") -> dict:
    """Validate configuration without calling an external provider."""
    if provider not in PROVIDERS:
        return {"ok": False, "message": "Unsupported provider"}
    key = api_key.strip()
    if len(key) < 8:
        return {"ok": False, "message": "The API key appears too short"}
    if provider == "pipedrive" and not domain.strip():
        return {"ok": False, "message": "Pipedrive company domain is required"}
    return {
        "ok": True,
        "stub": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "message": f"{PROVIDERS[provider]['name']} adapter configured; live sync remains opt-in.",
    }
