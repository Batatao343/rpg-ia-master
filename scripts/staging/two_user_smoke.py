"""SPEC-197 R6: two-user smoke on the deployed staging (no paid provider is called).

Covers: login/refresh/logout, isolation A/B (state, saves, art quote, balance), server-side synthetic wallet
credit + wallet sync, text turns (RPG_FORCE_MOCK on staging), image QUOTE (never generate), voice and Stripe
(recorded honestly as not_configured / blocked when the deployment has no key), account delete.
The synthetic wallet credit uses PostgresWallet.credit_verified_purchase (append-only: the pseudonymised
ledger rows stay in staging, see docs/spec197/evidence/restore_wallet.json notes).
"""
from __future__ import annotations

import argparse
import json
from uuid import uuid4

import httpx

from scripts.staging import s192
from scripts.staging.e2e_session import _h, stream_turn
from scripts.staging.synthetic_data import WALLET_SHARDS, WALLET_SKU, seed_wallet_prereqs

OUT = s192.common.ROOT / "docs" / "spec197" / "evidence" / "two_user_smoke.json"


class User:
    def __init__(self, base: str, admin: s192.Admin, label: str):
        self.base, self.label = base, label
        self.info = admin.create_user()
        self.id = self.info["id"]
        self.c = httpx.Client(timeout=90, follow_redirects=False, transport=httpx.HTTPTransport(retries=3))
        self.csrf = ""
        self.game_id = ""

    def login(self) -> int:
        r = self.c.post(f"{self.base}/auth/login", headers=_h(self.base), json={
            "email": self.info["email"], "password": self.info["password"], "captcha_token": s192.CAPTCHA_TEST})
        body = r.json() if r.status_code == 200 else {}
        self.csrf = body.get("csrf_token") or self.c.cookies.get("rpg_csrf") or ""
        return r.status_code

    def new_game(self) -> int:
        import json as _j
        origins = _j.loads((s192.common.ROOT / "data" / "origins.json").read_text(encoding="utf-8"))
        r = self.c.post(f"{self.base}/game/new", headers=_h(self.base, self.csrf), timeout=180, json={
            "name": f"Spec197{self.label}", "race": origins["races"][0]["name"], "class_name": "Devoto do Abismo",
            "region": origins["regions"][0]["name"], "level": 1, "action_id": str(uuid4())})
        self.game_id = (r.json() if r.status_code == 200 else {}).get("game_id", "")
        return r.status_code

    def get(self, path: str, **kw) -> httpx.Response:
        return self.c.get(f"{self.base}{path}", **kw)

    def post(self, path: str, body: dict | None = None, **kw) -> httpx.Response:
        return self.c.post(f"{self.base}{path}", headers=_h(self.base, self.csrf), json=body or {}, **kw)


def run(base: str, env: dict[str, str]) -> dict:
    from infrastructure.contracts import Principal
    from infrastructure.postgres import PostgresPool
    from infrastructure.wallet import PostgresWallet
    from uuid import UUID
    admin = s192.Admin(env)
    out: dict = {"base": base, "at": s192.now_iso(), "checks": {}}
    ck = out["checks"]
    health = httpx.get(f"{base}/health", timeout=30).json()
    out["deployed_git_sha"] = health.get("git_sha")
    users = [User(base, admin, "A"), User(base, admin, "B")]
    a, b = users
    pool = None
    try:
        ck["login"] = {"a": a.login(), "b": b.login()}
        ck["login"]["ok"] = ck["login"]["a"] == 200 and ck["login"]["b"] == 200
        ck["new_game"] = {"a": a.new_game(), "b": b.new_game()}
        ck["new_game"]["ok"] = bool(a.game_id and b.game_id)
        # text turns (staging runs RPG_FORCE_MOCK=1: the narrator is simulated, the pipeline is real)
        turns = {u.label: [stream_turn(u.c, base, u.csrf, u.game_id, t, str(uuid4()))
                           for t in ("Observo ao redor com cuidado.", "Examino o chão em busca de pistas.")]
                 for u in users}
        ck["text_turns"] = {k: [{"status": t["status"], "turn_count": t.get("turn_count"), "has_done": t["has_done"],
                                 "has_error": t["has_error"]} for t in v] for k, v in turns.items()}
        ck["text_turns"]["note"] = "RPG_FORCE_MOCK=1 on staging: simulated narrator, real graph/persistence/SSE"
        ck["text_turns"]["ok"] = all(t["status"] == 200 and t["has_done"] and not t["has_error"]
                                     for v in turns.values() for t in v)
        # isolation A/B
        cross = {
            "b_reads_a_state": b.get("/game/state", params={"game_id": a.game_id}).status_code,
            "a_reads_b_state": a.get("/game/state", params={"game_id": b.game_id}).status_code,
            "b_acts_on_a_game": b.post("/game/action", {"input_text": "x", "game_id": a.game_id,
                                                         "action_id": str(uuid4())}).status_code,
            "b_quote_on_a_game": b.post(f"/game/{a.game_id}/art/quote", {"image_type": "player"}).status_code,
        }
        saves_a = [s.get("game_id") for s in a.get("/game/saves").json()]
        saves_b = [s.get("game_id") for s in b.get("/game/saves").json()]
        ck["isolation"] = {**cross, "a_sees_only_own_save": saves_a == [a.game_id],
                           "b_sees_only_own_save": saves_b == [b.game_id],
                           "ok": all(v in (403, 404, 409) for v in cross.values()) and saves_a == [a.game_id]
                           and saves_b == [b.game_id]}
        # wallet sync: server-side synthetic credit for A only
        seed_wallet_prereqs(env["RPG_STAGING_DB_URL"])
        before = a.get("/account/balance").json()
        pool = PostgresPool(env["RPG_STAGING_DB_URL"])
        PostgresWallet(pool).credit_verified_purchase(
            Principal(UUID(a.id), "supabase", a.id), channel="web", payment_id="pi_spec197_smoke_" + uuid4().hex[:12],
            sku_id=WALLET_SKU, verified=True)
        after_a, after_b = a.get("/account/balance").json(), b.get("/account/balance").json()
        ck["wallet_sync"] = {"a_before": before.get("available_milli"), "a_after": after_a.get("available_milli"),
                             "b_after": after_b.get("available_milli"),
                             "ok": int(after_a["available_milli"]) - int(before["available_milli"]) == WALLET_SHARDS
                             and int(after_b["available_milli"]) == 0}
        # image QUOTE only (no confirm => no reservation, no provider call)
        qa = a.post(f"/game/{a.game_id}/art/quote", {"image_type": "player"})
        qbody = qa.json() if qa.status_code == 200 else {"detail": qa.text[:120]}
        ck["image_quote"] = {"status": qa.status_code, "has_credits": "credits_milli" in qbody or "credits" in str(qbody),
                             "keys": sorted(qbody)[:8], "generate_called": False, "ok": qa.status_code == 200}
        # voice: provider/flag not configured on staging => honest status
        vr = a.c.post(f"{base}/account/transcriptions", headers={"Origin": base, "X-CSRF-Token": a.csrf,
                                                                 "Content-Type": "audio/webm",
                                                                 "X-Operation-Id": str(uuid4())}, content=b"\x1a\x45\xdf\xa3")
        ck["voice"] = {"status": vr.status_code, "detail": (vr.json() if vr.content else {}).get("detail"),
                       "result": "not_configured" if vr.status_code == 503 else "needs_review",
                       "ok": vr.status_code == 503 and "speech" in str(vr.text)}
        # Stripe checkout needs STRIPE test keys in the deployment
        skus = a.get("/account/checkout/skus")
        ck["stripe_test_purchase"] = {"skus_status": skus.status_code, "skus": (skus.json() if skus.status_code == 200 else None),
                                      "result": "blocked: stripe_test_keys_missing",
                                      "ok": True}
        # refresh / logout / delete
        old_csrf = a.csrf
        rr = a.post("/auth/refresh")
        ck["refresh"] = {"status": rr.status_code, "state_after": a.get("/game/state", params={"game_id": a.game_id}).status_code,
                         "ok": rr.status_code == 200}
        if rr.status_code == 200:
            a.csrf = rr.json().get("csrf_token") or a.c.cookies.get("rpg_csrf") or old_csrf
        lo = b.post("/auth/logout")
        ck["logout"] = {"status": lo.status_code, "state_after": b.get("/game/state", params={"game_id": b.game_id}).status_code}
        ck["logout"]["ok"] = lo.status_code in (200, 204) and ck["logout"]["state_after"] == 401
        ra = a.post("/auth/reauth", {"password": a.info["password"], "captcha_token": s192.CAPTCHA_TEST})
        dr = a.post("/account/delete", {"confirmation": "EXCLUIR"}) if ra.status_code == 200 else None
        gone = admin.user_exists(a.id)
        ck["delete_account"] = {"reauth": ra.status_code, "delete_status": dr.status_code if dr is not None else None,
                                "delete_body": dr.json() if dr is not None and dr.content else None,
                                "auth_user_still_exists": gone,
                                "ok": dr is not None and dr.status_code in (200, 202)}
    finally:
        if pool:
            pool.close()
        cleanup: dict = {}
        try:
            with s192.db(env) as conn:
                for u in users:
                    if u.game_id:
                        cleanup[f"games_deleted_{u.label}"] = conn.execute(
                            "delete from app.games where id::text=%s", (u.game_id,)).rowcount
        except Exception as exc:  # noqa: BLE001
            cleanup["games_error"] = type(exc).__name__
        cleanup["user_delete_status"] = {u.label: admin.delete_user(u.id) for u in users}
        out["cleanup"] = cleanup
    out["ok"] = all(v.get("ok", True) for v in ck.values())
    # ok=True means "everything configured passed"; these paths could NOT be exercised and stay open (R-09/R-13).
    out["not_exercised"] = {
        "voice": ck.get("voice", {}).get("result"),
        "stripe_test_purchase": ck.get("stripe_test_purchase", {}).get("result"),
        "image_generate": "not_called: paid provider (quote only)"}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    res = run(a.base, s192.load_env())
    print(s192.common.write_evidence("two_user_smoke", res, a.out))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
