"""SPEC-221 R6/R7: teto de body ASGI puro (nao bufferiza respostas, nao quebra SSE) e filename seguro."""

from __future__ import annotations

import json
from typing import Mapping



class BodyLimitMiddleware:
    def __init__(self, app, default_limit: int = 256 * 1024,
                 per_path: Mapping[str, int] | None = None) -> None:
        self.app = app
        self.default_limit = int(default_limit)
        self.per_path = dict(per_path or {})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") in {"GET", "HEAD", "OPTIONS"}:
            return await self.app(scope, receive, send)
        limit = self.per_path.get(scope.get("path", ""), self.default_limit)
        declared = None
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = None
                break
        started = False

        async def reject():
            nonlocal started
            if started:
                return
            started = True
            from observability.telemetry import correlation
            rid = correlation().get("request_id")   # SPEC-242: envelope unico
            payload = {"detail": "payload_too_large", "code": "payload_too_large"}
            if rid:
                payload["request_id"] = rid
            body = json.dumps(payload).encode()
            await send({"type": "http.response.start", "status": 413, "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ]})
            await send({"type": "http.response.body", "body": body})

        if declared is not None and declared > limit:
            return await reject()

        seen = 0
        exceeded = False

        async def limited_receive():
            nonlocal seen, exceeded
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    exceeded = True
                    # Fim do corpo para o parser abortar sem ler mais.
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def guarded_send(message):
            if started:
                return None  # 413 ja enviado; descarta a resposta da aplicacao
            if exceeded and message["type"] == "http.response.start":
                return await reject()
            return await send(message)

        await self.app(scope, limited_receive, guarded_send)
        if exceeded and not started:
            await reject()


def safe_attachment_filename(name: str, fallback: str = "cronica") -> tuple[str, str]:
    """(ascii seguro p/ filename=, utf8 percent-encoded p/ filename*=). Nunca levanta."""
    import unicodedata
    from urllib.parse import quote

    text = unicodedata.normalize("NFKC", str(name or ""))
    original = "".join(c for c in text if c.isalnum() or c in "_-")[:80]
    folded = unicodedata.normalize("NFKD", text)
    ascii_name = "".join(c for c in folded if c.isascii() and (c.isalnum() or c in "_-"))[:40]
    return ascii_name or fallback, quote(original or fallback, safe="")
