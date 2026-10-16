"""SPEC-229 R7 — telemetria `rpg.intent_guard` de recusas/decisões pré-LLM (sem texto cru)."""
import hashlib
import logging

_LOG = logging.getLogger("rpg.intent_guard")


def log_intent_guard(kind: str, matched: str, text: str) -> None:
    digest = hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:12]
    _LOG.info("rpg.intent_guard", extra={"kind": kind, "matched": str(matched)[:60],
                                         "text_hash": digest})
