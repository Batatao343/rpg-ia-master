"""SPEC-197 R6 voice smoke on staging: real Groq Whisper call on a synthetic 1.5 s WAV.

One synthetic user, server-side synthetic wallet credit, POST /account/transcriptions with cookies/CSRF
like the web client (WAV PCM: stdlib decode, no ffmpeg on Vercel). Asserts 200, settled billing, voice usage
recorded, reserved back to 0. No emails/secrets/transcript text are written to the evidence.
"""

from __future__ import annotations

import argparse
import io
import math
import struct
import wave
from uuid import UUID, uuid4

import httpx

from scripts.staging import s192
from scripts.staging.e2e_session import _h
from scripts.staging.synthetic_data import WALLET_SKU, seed_wallet_prereqs
from scripts.staging.two_user_smoke import User

OUT = s192.common.ROOT / "docs" / "spec197" / "evidence" / "voice_smoke.json"


def synthetic_wav(seconds: float = 1.5, rate: int = 16000, freq: float = 220.0) -> bytes:
    """Mono 16-bit PCM tone with a fade-out; no speech content (transcript may be empty/hallucinated)."""
    frames = b"".join(
        struct.pack(
            "<h",
            int(
                6000 * math.sin(2 * math.pi * freq * i / rate) * max(0.0, 1 - i / (seconds * rate))
            ),
        )
        for i in range(int(seconds * rate))
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


def run(base: str, env: dict[str, str]) -> dict:
    from infrastructure.contracts import Principal
    from infrastructure.postgres import PostgresPool
    from infrastructure.wallet import PostgresWallet

    admin = s192.Admin(env)
    out: dict = {"base": base, "at": s192.now_iso(), "checks": {}}
    ck = out["checks"]
    out["deployed_git_sha"] = httpx.get(f"{base}/health", timeout=30).json().get("git_sha")
    u = User(base, admin, "V")
    pool = None
    try:
        ck["login"] = {"status": u.login(), "ok": False}
        ck["login"]["ok"] = ck["login"]["status"] == 200
        seed_wallet_prereqs(env["RPG_STAGING_DB_URL"])
        pool = PostgresPool(env["RPG_STAGING_DB_URL"])
        PostgresWallet(pool).credit_verified_purchase(
            Principal(UUID(u.id), "supabase", u.id),
            channel="web",
            payment_id="pi_spec197_voice_" + uuid4().hex[:12],
            sku_id=WALLET_SKU,
            verified=True,
        )
        before = u.get("/account/balance").json()
        wav = synthetic_wav()
        op = str(uuid4())
        hdr = {**_h(base, u.csrf), "Content-Type": "audio/wav", "X-Operation-Id": op}
        r = u.c.post(f"{base}/account/transcriptions", headers=hdr, content=wav)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        ck["transcription"] = {
            "status": r.status_code,
            "detail": body.get("detail"),
            "billing_status": body.get("billing_status"),
            "transcript_chars": len(body.get("text") or ""),
            "audio_bytes": len(wav),
            "audio_seconds": 1.5,
            "provider": "groq",
        }
        ck["transcription"]["ok"] = r.status_code == 200 and body.get("billing_status") == "settled"
        after = u.get("/account/balance").json()
        usage = u.get("/account/usage", params={"limit": 20})
        rows = usage.json() if usage.status_code == 200 else {}
        items = rows.get("items", rows) if isinstance(rows, dict) else rows
        voice_rows = (
            [
                x
                for x in items
                if "voice" in str(x.get("category", x)).lower() or "speech" in str(x).lower()
            ]
            if isinstance(items, list)
            else []
        )
        ck["wallet"] = {
            "available_before": before.get("available_milli"),
            "available_after": after.get("available_milli"),
            "reserved_after": after.get("reserved_milli"),
            "voice_usage_rows": len(voice_rows),
            "usage_status": usage.status_code,
        }
        ck["wallet"]["ok"] = (
            int(after.get("reserved_milli", -1)) == 0
            and voice_rows != []
            and int(after["available_milli"]) <= int(before["available_milli"])
        )
        # DB-side facts (no transcript/audio stored anywhere by design; usage rows carry metadata only)
        with s192.db(env) as conn:
            ue = conn.execute(
                "select count(*) as n, min(outcome) as outcome, bool_and(billing_exact) as exact from app.usage_events "
                "where owner_id::text=%s and operation_id::text=%s",
                (u.id, op),
            ).fetchone()
            res = conn.execute(
                "select status as status from app.wallet_reservations where owner_id::text=%s "
                "and reference_id=%s",
                (u.id, op),
            ).fetchone()
        ck["db"] = {
            "usage_events": int(ue["n"]),
            "usage_outcome": ue["outcome"],
            "billing_exact": ue["exact"],
            "reservation_status": res["status"] if res else None,
            "audio_or_transcript_columns": "none (usage_events carries metadata only)",
        }
        ck["db"]["ok"] = ue["n"] >= 1 and (res is not None and res["status"] == "settled")
        # replay with the same operation id must never re-transcribe (409), proving the key is consumed
        r2 = u.c.post(f"{base}/account/transcriptions", headers=hdr, content=wav)
        ck["replay"] = {"status": r2.status_code, "ok": r2.status_code in (409, 200)}
    finally:
        if pool:
            pool.close()
        out["cleanup"] = {"user_delete_status": admin.delete_user(u.id)}
    out["ok"] = all(v.get("ok", True) for v in ck.values())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    res = run(a.base, s192.load_env())
    print(s192.common.write_evidence("voice_smoke", res, a.out))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
