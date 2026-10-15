"""SPEC-192 F3: close the SSE connection after the first event, then retry the same action_id via POST.

Expectation: exactly one turn applied (turn_count +1), never +2.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from uuid import uuid4

import httpx

from scripts.staging import s192
from scripts.staging.e2e_session import _h

WAIT_SECONDS = 90


def exactly_one_turn(base_turn: int, after_disconnect: int, after_retry: int) -> bool:
    return after_retry == base_turn + 1 and after_disconnect in (base_turn, base_turn + 1)


def run(base: str, env: dict) -> dict:
    admin = s192.Admin(env)
    out: dict = {"base": base, "at": s192.now_iso()}
    user = admin.create_user()
    game_ids: list[str] = []
    c = httpx.Client(timeout=60, follow_redirects=False, transport=httpx.HTTPTransport(retries=3))
    try:
        creds = {"email": user["email"], "password": user["password"], "captcha_token": s192.CAPTCHA_TEST}
        r = c.post(f"{base}/auth/login", headers=_h(base), json=creds)
        csrf = (r.json() if r.status_code == 200 else {}).get("csrf_token") or c.cookies.get("rpg_csrf") or ""
        origins = json.loads((s192.common.ROOT / "data" / "origins.json").read_text(encoding="utf-8"))
        r = c.post(f"{base}/game/new", headers=_h(base, csrf), timeout=180, json={
            "name": "Spec192 Desconexao", "race": origins["races"][0]["name"], "class_name": "Devoto do Abismo",
            "region": origins["regions"][0]["name"], "level": 1, "action_id": str(uuid4())})
        gj = r.json() if r.status_code == 200 else {}
        gid = gj.get("game_id", "")
        if not gid:
            raise RuntimeError(f"new game failed: {r.status_code}")
        game_ids.append(gid)
        base_turn = (gj.get("world") or {}).get("turn_count", 0)
        action_id = str(uuid4())
        payload = {"input_text": "Observo ao redor com cuidado.", "game_id": gid, "action_id": action_id}
        first_event = None
        with c.stream("POST", f"{base}/game/action/stream", headers=_h(base, csrf), json=payload, timeout=180) as s:
            for line in s.iter_lines():
                if line:
                    first_event = line[:40]
                    break
        # leaving the with-block closes the connection mid-turn
        t0 = time.monotonic()
        after_disconnect = base_turn
        while time.monotonic() - t0 < WAIT_SECONDS:
            time.sleep(5)
            st = c.get(f"{base}/game/state", params={"game_id": gid})
            if st.status_code == 200:
                after_disconnect = (st.json().get("world") or {}).get("turn_count", base_turn)
                if after_disconnect > base_turn:
                    break
        waited = round(time.monotonic() - t0, 1)
        retry = c.post(f"{base}/game/action", headers=_h(base, csrf), json=payload, timeout=180)
        st = c.get(f"{base}/game/state", params={"game_id": gid})
        after_retry = (st.json().get("world") or {}).get("turn_count") if st.status_code == 200 else None
        out.update({
            "first_event_prefix": first_event, "base_turn": base_turn, "waited_s": waited,
            "turn_after_disconnect": after_disconnect, "retry_status": retry.status_code,
            "turn_after_retry": after_retry,
            "ok": retry.status_code == 200 and after_retry is not None
            and exactly_one_turn(base_turn, after_disconnect, after_retry)})
    finally:
        cleanup: dict = {}
        try:
            with s192.db(env) as conn:
                for gid in game_ids:
                    cleanup["games_deleted"] = cleanup.get("games_deleted", 0) + conn.execute(
                        "delete from app.games where id::text=%s", (gid,)).rowcount
        except Exception as exc:  # noqa: BLE001
            cleanup["games_error"] = type(exc).__name__
        cleanup["user_delete_status"] = admin.delete_user(user["id"])
        out["cleanup"] = cleanup
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    a = ap.parse_args(argv)
    res = run(a.base, s192.load_env())
    s192.evidence("sse_disconnect", res)
    print(json.dumps({k: res.get(k) for k in ("ok", "base_turn", "turn_after_disconnect", "turn_after_retry", "retry_status")}))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
