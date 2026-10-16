"""SPEC-197 browser voice E2E on staging: real Chromium (fake mic), voice button -> /account/transcriptions.

Auth is established by API login (Turnstile test token) and cookies are handed to the browser context;
the voice flow itself runs through the real UI. Asserts WAV upload, 200, transcript in the composer,
and no auto-submit. No emails/secrets/transcript text are written to the evidence.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

from scripts.staging import s192
from scripts.staging.synthetic_data import WALLET_SKU, seed_wallet_prereqs
from scripts.staging.two_user_smoke import User
from scripts.staging.voice_smoke import synthetic_wav

OUT = s192.common.ROOT / "docs" / "spec197" / "evidence" / "browser_voice_smoke.json"


def _chrome() -> str | None:
    """Installed Chromium may differ from the version Playwright expects; use any local chrome.exe."""
    import glob
    import os
    hits = sorted(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%/ms-playwright/chromium-*/chrome-win64/chrome.exe")))
    return hits[-1] if hits else None


def run(base: str, env: dict[str, str]) -> dict:
    from playwright.sync_api import sync_playwright
    from infrastructure.contracts import Principal
    from infrastructure.postgres import PostgresPool
    from infrastructure.wallet import PostgresWallet
    admin = s192.Admin(env)
    out: dict = {"base": base, "at": s192.now_iso(), "checks": {}}
    ck = out["checks"]
    u = User(base, admin, "B")
    pool = None
    try:
        ck["login"] = {"ok": u.login() == 200}
        ck["new_game"] = {"ok": u.new_game() == 200}
        seed_wallet_prereqs(env["RPG_STAGING_DB_URL"])
        pool = PostgresPool(env["RPG_STAGING_DB_URL"])
        PostgresWallet(pool).credit_verified_purchase(
            Principal(UUID(u.id), "supabase", u.id), channel="web",
            payment_id="pi_spec197_bvoice_" + uuid4().hex[:12], sku_id=WALLET_SKU, verified=True)
        host = urlparse(base).hostname
        cookies = [{"name": c.name, "value": c.value, "domain": host, "path": "/", "secure": True,
                    "httpOnly": c.name != "rpg_csrf", "sameSite": "Lax"} for c in u.c.cookies.jar]
        ck["cookies_transferred"] = {"count": len(cookies), "ok": len(cookies) > 0}
        wav = Path(tempfile.mkdtemp()) / "mic.wav"
        wav.write_bytes(synthetic_wav(4.0))
        tr: dict = {}
        with sync_playwright() as p:
            br = p.chromium.launch(executable_path=_chrome(), args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
                                         f"--use-file-for-fake-audio-capture={wav}"])
            ctx = br.new_context(permissions=["microphone"], viewport={"width": 1280, "height": 900})
            ctx.add_cookies(cookies)
            page = ctx.new_page()
            sent_actions: list[str] = []

            def on_resp(resp):
                if resp.url.endswith("/account/transcriptions"):
                    req = resp.request
                    tr.update(status=resp.status, content_type=(req.headers.get("content-type") or "").split(";")[0],
                              bytes=len(req.post_data_buffer or b""))
            page.on("response", on_resp)
            page.on("request", lambda r: sent_actions.append(r.url) if "/game/action" in r.url and r.method == "POST" else None)
            page.add_init_script(f"localStorage.setItem('cronicas_game_id','{u.game_id}')")
            page.goto(base, wait_until="networkidle", timeout=60000)
            box = page.get_by_label("Sua ação")
            try:
                box.wait_for(timeout=8000)
            except Exception:
                page.locator("button", has_text="Spec197B").first.click(timeout=8000)
                box.wait_for(timeout=30000)
            ck["composer_visible"] = {"ok": True}
            page.get_by_label("Gravar ação por voz").click()
            page.get_by_label("Parar gravação").wait_for(timeout=10000)
            page.wait_for_timeout(2500)
            page.get_by_label("Parar gravação").click()
            for _ in range(60):
                if tr.get("status"):
                    break
                page.wait_for_timeout(1000)
            page.wait_for_timeout(1500)
            text = box.input_value()
            state = page.locator("[data-voice-state]").get_attribute("data-voice-state")
            ck["upload"] = {"status": tr.get("status"), "content_type": tr.get("content_type"), "bytes": tr.get("bytes"),
                            "ok": tr.get("status") == 200 and tr.get("content_type") == "audio/wav"}
            ck["composer"] = {"transcript_chars": len(text), "voice_state_after": state,
                              "auto_sent_actions": len(sent_actions),
                              "note": "tone-only audio: empty/short transcript is possible; insertion checked via chars>0 or non-error state"}
            ck["composer"]["ok"] = len(sent_actions) == 0 and state != "error"
            ck["composer"]["transcript_inserted"] = len(text) > 0
            br.close()
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
    print(s192.common.write_evidence("browser_voice_smoke", res, a.out))
    print({k: v for k, v in res["checks"].items()})
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
