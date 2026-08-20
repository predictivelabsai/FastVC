"""FastVC — FastHTML app.

Single process, two route groups:
  - /                 marketing landing (landing/routes.py)
  - /app/*            3-pane chat product (chat/routes.py)
"""

from __future__ import annotations

from fasthtml.common import fast_app, serve
from starlette.responses import JSONResponse

from utils.config import settings

app, rt = fast_app(
    live=False,
    static_path=".",
    pico=False,
    secret_key=settings().app_secret,
    htmx=True,
)


@rt("/healthz")
def healthz():
    """Lightweight container and reverse-proxy health check."""
    return JSONResponse({"status": "ok", "service": "fastvc"})


# Route modules register their handlers against `rt`. Importing for side effects.
from landing import routes as _landing_routes  # noqa: E402,F401
from chat import routes as _chat_routes  # noqa: E402,F401
from chat import pipeline as _pipeline_routes  # noqa: E402,F401
from chat import instructions as _instructions_routes  # noqa: E402,F401
from chat import analytics as _analytics_routes  # noqa: E402,F401
from chat import companies as _companies_routes  # noqa: E402,F401
from chat import memo_pdf as _memo_pdf_routes  # noqa: E402,F401
from chat import exports as _export_routes  # noqa: E402,F401
from chat import dataroom as _dataroom_routes  # noqa: E402,F401
from chat import help as _help_routes  # noqa: E402,F401
from chat import valuation as _valuation_routes  # noqa: E402,F401
from chat import webhooks as _webhook_routes  # noqa: E402,F401
from chat import integrations as _integrations_routes  # noqa: E402,F401
from chat import news_sources as _news_sources_routes  # noqa: E402,F401
from chat import training as _training_routes  # noqa: E402,F401
from chat import investors as _investors_routes  # noqa: E402,F401
from chat import portfolio as _portfolio_routes  # noqa: E402,F401
from chat import discovery as _discovery_routes  # noqa: E402,F401
from auth import routes as _auth_routes  # noqa: E402,F401

# Voice mode — /ws/voice WebSocket proxy to the x.ai realtime agent.
# Inserted at the front of the router so the static catch-all can't shadow it.
from voice import register_voice_routes  # noqa: E402

register_voice_routes(app)


def _serve_default():
    serve(port=settings().port)


if __name__ == "__main__":
    _serve_default()
