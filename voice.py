"""Voice mode — a WebSocket proxy between the browser and x.ai's realtime agent.

The browser can't hold the API key, so /ws/voice bridges browser audio ↔ the x.ai
realtime WebSocket (the manually-created voice agent). Audio is PCM16 mono base64;
server-side VAD handles turn-taking, so the browser just streams mic audio and plays
back the agent's audio + transcript.

Config comes through utils.config.settings() (never os.environ in route code):
XAI_API_KEY authenticates; XAI_VOICE_AGENT_ID selects the voice agent. When either
is missing the proxy reports "voice not configured" and closes — the mic button is
hidden in that case, so this is only a defensive guard.
"""

from __future__ import annotations

import asyncio
import json
import logging

import websockets as wslib
from starlette.websockets import WebSocket, WebSocketDisconnect

from utils.config import settings

log = logging.getLogger(__name__)

SESSION_UPDATE = {
    "type": "session.update",
    "session": {
        "modalities": ["audio", "text"],
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "turn_detection": {"type": "server_vad"},
    },
}


async def _voice_ws(ws: WebSocket):
    await ws.accept()
    s = settings()
    key = s.xai_api_key
    agent_id = s.xai_voice_agent_id
    if not key or not agent_id:
        await ws.send_json({
            "type": "error",
            "message": "voice not configured (set XAI_API_KEY + XAI_VOICE_AGENT_ID)",
        })
        await ws.close()
        return

    xai_url = f"wss://api.x.ai/v1/realtime?agent_id={agent_id}"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with wslib.connect(xai_url, additional_headers=headers, max_size=None) as xai:
            await xai.send(json.dumps(SESSION_UPDATE))
            await ws.send_json({"type": "ready"})

            async def browser_to_xai():
                while True:
                    msg = json.loads(await ws.receive_text())
                    mt = msg.get("type")
                    if mt == "audio":
                        await xai.send(json.dumps(
                            {"type": "input_audio_buffer.append", "audio": msg["audio"]}))
                    elif mt == "commit":  # push-to-talk fallback (server VAD is default)
                        await xai.send(json.dumps({"type": "input_audio_buffer.commit"}))
                        await xai.send(json.dumps({"type": "response.create"}))
                    elif mt == "cancel":
                        await xai.send(json.dumps({"type": "response.cancel"}))

            async def xai_to_browser():
                async for raw in xai:
                    e = json.loads(raw)
                    t = e.get("type")
                    if t == "response.output_audio.delta":
                        await ws.send_json({"type": "audio", "audio": e.get("delta", "")})
                    elif t == "response.output_audio_transcript.delta":
                        await ws.send_json({"type": "assistant_delta", "text": e.get("delta", "")})
                    elif t == "response.output_audio_transcript.done":
                        await ws.send_json({"type": "assistant_done", "text": e.get("transcript", "")})
                    elif t == "input_audio_buffer.input_audio_transcription.completed":
                        await ws.send_json({"type": "user_transcript", "text": e.get("transcript", "")})
                    elif t == "input_audio_buffer.input_audio_transcription.updated":
                        await ws.send_json({"type": "user_partial", "text": e.get("transcript", "")})
                    elif t == "input_audio_buffer.speech_started":
                        await ws.send_json({"type": "speech_started"})
                    elif t == "input_audio_buffer.speech_stopped":
                        await ws.send_json({"type": "speech_stopped"})
                    elif t == "response.done":
                        await ws.send_json({"type": "done"})
                    elif t == "error":
                        await ws.send_json({"type": "error",
                                            "message": json.dumps(e.get("error", e))[:300]})

            _, pending = await asyncio.wait(
                [asyncio.create_task(browser_to_xai()), asyncio.create_task(xai_to_browser())],
                return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()
    except WebSocketDisconnect:
        pass
    except Exception as ex:  # noqa: BLE001
        log.warning("voice proxy error: %s", ex)
        try:
            await ws.send_json({"type": "error", "message": str(ex)[:200]})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


def register_voice_routes(app):
    """Attach the /ws/voice WebSocket proxy to the FastHTML (Starlette) app.

    Inserted at the front of the router so FastHTML's catch-all static route can't
    shadow the WebSocket handshake.
    """
    from starlette.routing import WebSocketRoute
    app.router.routes.insert(0, WebSocketRoute("/ws/voice", _voice_ws))
