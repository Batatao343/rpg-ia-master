"""SPEC-236 §6.3 on staging: Groq STT rate-limited (real 429) -> paid OpenAI fallback, reservation back to 0.

The Groq limit is exhausted with the SAME staging key by a bounded burst of tiny direct requests (Groq is free
tier; nothing is billed), then ONE transcription goes through the app like the web client. Expected:
ordinal 0 groq = 429 `definitive_no_charge` (cost 0), ordinal 1 openai = success, reservation settled and
``reserved_milli == 0``. Evidence carries statuses/counts only (no audio, transcript, emails or keys).
"""

from __future__ import annotations

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

import httpx

from scripts.staging import s192
from scripts.staging.e2e_session import _h
from scripts.staging.synthetic_data import WALLET_SKU, seed_wallet_prereqs
from scripts.staging.two_user_smoke import User
from scripts.staging.voice_smoke import synthetic_wav

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
OUT = (
    s192.common.ROOT
    / "docs"
    / "staging-wave-2026-10-17"
    / "evidence"
    / "spec236_s63_stt_fallback.json"
)


class GroqBurst:
    """Bounded burst against Groq STT until it answers 429 (and keeps it saturated while the app call runs)."""

    def __init__(self, key: str, max_requests: int):
        self.key, self.max = key, max_requests
        self.codes: list[int] = []
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.audio = synthetic_wav(0.3)

    def one(self) -> int:
        with self.lock:
            if len(self.codes) >= self.max or self.stop.is_set():
                return 0
        try:
            r = httpx.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {self.key}"},
                timeout=30,
                data={"model": "whisper-large-v3-turbo"},
                files={"file": ("t.wav", self.audio, "audio/wav")},
            )
            code = r.status_code
        except httpx.HTTPError:
            code = -1
        with self.lock:
            self.codes.append(code)
        return code

    def until_429(self, workers: int = 8) -> bool:
        with ThreadPoolExecutor(workers) as ex:
            while not self.stop.is_set() and len(self.codes) < self.max:
                if 429 in list(ex.map(lambda _: self.one(), range(workers))):
                    return True
        return 429 in self.codes

    def keep_saturated(self, seconds: float) -> threading.Thread:
        def loop():
            end = time.monotonic() + seconds
            while time.monotonic() < end and not self.stop.is_set() and len(self.codes) < self.max:
                self.one()

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        return t


def run(base: str, env: dict[str, str], wav: bytes, max_burst: int) -> dict:
    from infrastructure.contracts import Principal
    from infrastructure.postgres import PostgresPool
    from infrastructure.wallet import PostgresWallet

    admin = s192.Admin(env)
    out: dict = {
        "base": base,
        "at": s192.now_iso(),
        "checks": {},
        "deployed_git_sha": httpx.get(f"{base}/health", timeout=30).json().get("git_sha"),
    }
    ck = out["checks"]
    u = User(base, admin, "S")
    pool = None
    burst = GroqBurst(env["GROQ_API_KEY"], max_burst)
    try:
        ck["login"] = {"status": u.login()}
        ck["login"]["ok"] = ck["login"]["status"] == 200
        seed_wallet_prereqs(env["RPG_STAGING_DB_URL"])
        pool = PostgresPool(env["RPG_STAGING_DB_URL"])
        PostgresWallet(pool).credit_verified_purchase(
            Principal(UUID(u.id), "supabase", u.id),
            channel="web",
            payment_id="pi_spec236_s63_" + uuid4().hex[:12],
            sku_id=WALLET_SKU,
            verified=True,
        )
        before = u.get("/account/balance").json()
        limited = burst.until_429()
        keeper = burst.keep_saturated(20)
        op = str(uuid4())
        r = u.c.post(
            f"{base}/account/transcriptions",
            headers={**_h(base, u.csrf), "Content-Type": "audio/wav", "X-Operation-Id": op},
            content=wav,
        )
        burst.stop.set()
        keeper.join(35)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        ck["groq_burst"] = {
            "requests": len(burst.codes),
            "status_counts": {str(c): burst.codes.count(c) for c in set(burst.codes)},
            "reached_429": limited,
            "ok": limited,
        }
        ck["transcription"] = {
            "status": r.status_code,
            "billing_status": body.get("billing_status"),
            "detail": body.get("detail"),
            "transcript_chars": len(body.get("text") or ""),
        }
        ck["transcription"]["ok"] = r.status_code == 200 and body.get("billing_status") == "settled"
        after = u.get("/account/balance").json()
        with s192.db(env) as conn:
            rows = conn.execute(
                "select attempt_ordinal, provider, outcome, cost_basis, cost_usd::text as cost_usd, counts_as_spend "
                "from app.usage_events where owner_id::text=%s and operation_id::text=%s order by attempt_ordinal",
                (u.id, op),
            ).fetchall()
            res = conn.execute(
                "select status from app.wallet_reservations where owner_id::text=%s and reference_id=%s",
                (u.id, op),
            ).fetchone()
        ck["usage_events"] = {"rows": [dict(x) for x in rows]}
        first = rows[0] if rows else {}
        ck["usage_events"]["ok"] = (
            len(rows) >= 2
            and first.get("provider") == "groq"
            and first.get("counts_as_spend") is False
            and float(first.get("cost_usd") or 0) == 0
            and rows[-1]["provider"] == "openai"
            and rows[-1]["outcome"] == "success"
        )
        ck["wallet"] = {
            "available_before": before.get("available_milli"),
            "available_after": after.get("available_milli"),
            "reserved_after": after.get("reserved_milli"),
            "reservation_status": res["status"] if res else None,
        }
        ck["wallet"]["ok"] = (
            int(after.get("reserved_milli", -1)) == 0
            and res is not None
            and res["status"] == "settled"
        )
    finally:
        burst.stop.set()
        if pool:
            pool.close()
        out["cleanup"] = {"user_delete_status": admin.delete_user(u.id)}
    out["ok"] = all(v.get("ok", True) for v in ck.values())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument(
        "--wav", required=True, help="short WAV with speech (a pure tone may transcribe empty)"
    )
    ap.add_argument("--max-burst", type=int, default=60)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    res = run(a.base, s192.load_env(), Path(a.wav).read_bytes(), a.max_burst)
    print(s192.common.write_evidence("spec236_s63_stt_fallback", res, a.out))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
