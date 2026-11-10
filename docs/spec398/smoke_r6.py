"""SPEC-398 R6 (staging): driver corrigido do smoke + purga do retrato `unico` (SPEC-352 R14).

Rodar do checkout principal: `bash scripts/dev/py.sh docs/spec398/smoke_r6.py <saida> [presagio|purga|tudo]`.
Contas sinteticas; jogos e contas apagados no fim. Nao imprime segredos.

Driver (diagnostico da 369, correcao 1):
- alvo so de `valid_targets` (lista vazia = jogar sem alvo ou nao jogar);
- `409 invalid_target` chega como evento SSE `error`: tira a jogada de `play_index` e reenvia;
- para depois de MAX_REFUSALS recusas na mesma rodada.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from scripts.staging import s192  # noqa: E402
from scripts.staging.e2e_session import _h  # noqa: E402
from scripts.staging.two_user_smoke import User  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
MODE = sys.argv[2] if len(sys.argv) > 2 else "tudo"
BASE = s192.BASE
ENV = s192.load_env()
MAX_REFUSALS = 3
MAX_CONFLICTS = 6
MAX_ROUNDS = 8
DEFENSE = "bas_med_guarda"
HEALS = ("med_torniquete", "med_sutura")
OPEN_PHRASES = (
    "Saco a arma e ataco a criatura hostil mais próxima",
    "Ataco a primeira criatura hostil que surgir",
    "Parto para cima do inimigo à frente",
)
UNICO_REGIONS = (
    ("Skallgard", "o Urso-Titã"),
    ("Pântano da Melancolia", "a Borda que Anda"),
    ("Floresta dos Sussurros", "o Toldo das Clareiras"),
    ("Deserto de Zhur", "o Eclipse Caminhante"),
    ("Costa Negra", "o Hóspede do Estômago"),
    ("Nova Arcádia", "a Víbora"),
)
RES: dict = {"refusals_409": 0, "hand_contract_violations": []}


def note(kind: str, **data) -> None:
    row = {"t": s192.now_iso(), "kind": kind, **data}
    print(json.dumps(row, ensure_ascii=False)[:600], flush=True)
    with (OUT / "log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def retry(fn, *a, **k):
    last = None
    for i in range(4):
        try:
            return fn(*a, **k)
        except Exception as exc:  # noqa: BLE001
            last = exc
            note("retry", fn=getattr(fn, "__name__", "?"), err=type(exc).__name__, i=i)
            time.sleep(4)
    raise last


def _idem(u: User) -> dict:
    return {**_h(BASE, u.csrf), "Idempotency-Key": str(uuid4())}


def stream(u: User, gid: str, body: dict) -> dict:
    lines: list[str] = []
    body = {"game_id": gid, "action_id": str(uuid4()), **body}
    with u.c.stream(
        "POST", f"{BASE}/game/action/stream", headers=_h(BASE, u.csrf), json=body, timeout=240
    ) as r:
        status = r.status_code
        lines.extend(r.iter_lines())
    ev = s192.parse_sse(lines + [""])
    narr = "".join(
        e["data"].get("chunk", "")
        for e in ev
        if e["event"] == "narrative" and isinstance(e["data"], dict)
    )
    return {
        "status": status,
        "narr": narr[:1500],
        "error": [e["data"] for e in ev if e["event"] == "error"],
    }


def state(u: User, gid: str) -> dict:
    r = u.get("/game/state", params={"game_id": gid})
    return r.json() if r.status_code == 200 else {"_status": r.status_code}


def db_rows(sql: str, args: tuple) -> list[dict]:
    with s192.db(ENV) as conn:
        return [
            {k: (str(v) if v is not None else None) for k, v in r.items()}
            for r in conn.execute(sql, args).fetchall()
        ]


def family(enemy: dict) -> str:
    """Arquétipo pelo id (`enemy_necromante_renegado_2` -> `necromante_renegado`): o saber do Presságio é por arquétipo."""
    stem = re.sub(r"^(enemy|mon|bst)_", "", str(enemy.get("id") or ""))
    return re.sub(r"_(r?\d+)$", "", stem)


def view(st: dict) -> dict:
    c = st.get("combat") or {}
    return {
        "active": c.get("active"),
        "round": c.get("round"),
        "outcome": c.get("outcome"),
        "outcome_reason": (st.get("combat_result") or {}).get("outcome_reason"),
        "combat_result": {
            k: (st.get("combat_result") or {}).get(k) for k in ("outcome", "outcome_reason")
        },
        "player_vit": (st.get("player_stats") or {}).get("vitalidade"),
        "death_pending": st.get("death_pending"),
        "enemies": [
            {"id": e.get("id"), "name": e.get("name"), "vit": e.get("vitalidade"), "fam": family(e)}
            for e in c.get("enemies") or []
        ],
        "hand": [
            {
                k: x.get(k)
                for k in (
                    "id",
                    "name",
                    "tipo",
                    "custo_folego",
                    "jogavel",
                    "alvo",
                    "valid_targets",
                    "invalid_reason",
                )
            }
            for x in ((c.get("pilhas") or {}).get("mao") or [])
        ],
        "folego": (c.get("pilhas") or {}).get("folego"),
        "mech": c.get("mech_log") or [],
        "pressagios": c.get("pressagios_publicos") or [],
    }


def check_hand(v: dict) -> None:
    """R1/R2 ao vivo: reacao/passiva nao jogavel com motivo; Carta jogavel de alvo inimigo tem alvo valido."""
    for h in v["hand"]:
        bad = None
        if h.get("tipo") in ("reacao", "passiva") and (
            h.get("jogavel") or h.get("invalid_reason") != "not_playable_from_hand"
        ):
            bad = "reacao_ou_passiva_jogavel"
        elif h.get("jogavel") and h.get("alvo") == "inimigo" and not h.get("valid_targets"):
            bad = "inimigo_sem_alvo_mas_jogavel"
        if bad:
            RES["hand_contract_violations"].append(
                {"card": h.get("id"), "why": bad, "round": v["round"]}
            )


def plan(v: dict, want_defense: bool) -> list[dict]:
    hand = [h for h in v["hand"] if h.get("jogavel")]
    low = int(v.get("player_vit") or 0) <= 5
    order = sorted(
        hand,
        key=lambda h: (
            0 if want_defense and h["id"] == DEFENSE else 1,
            0 if low and h["id"] in HEALS else 1,
            0 if h.get("alvo") == "inimigo" else 1,
        ),
    )
    plays, spent = [], 0
    for h in order:
        cost = int(h.get("custo_folego") or 1)
        if spent + cost > int(v.get("folego") or 2) or len(plays) >= 2:
            continue
        if h.get("alvo") == "inimigo":
            vt = h.get("valid_targets") or []
            if not vt:
                continue
            plays.append({"card_id": h["id"], "target_id": vt[0], "name": h.get("name")})
        else:
            plays.append({"card_id": h["id"], "name": h.get("name")})
        spent += cost
    return plays


def play_round(u: User, gid: str, plays: list[dict]) -> dict:
    """Envia; em 409 `invalid_target` tira a jogada recusada e reenvia (SPEC-363 R21), ate MAX_REFUSALS."""
    refusals = []
    while True:
        names = ", ".join(p["name"] or p["card_id"] for p in plays) or "nada"
        jog = [{k: p[k] for k in ("card_id", "target_id") if k in p} for p in plays]
        res = retry(stream, u, gid, {"input_text": f"Encerro a rodada: {names}.", "jogadas": jog})
        err = next(
            (e for e in res["error"] if isinstance(e, dict) and "invalid_target" in json.dumps(e)),
            None,
        )
        if not err:
            return {
                "res": {"status": res["status"], "error": res["error"]},
                "narr": res["narr"],
                "refusals": refusals,
                "sent": jog,
            }
        RES["refusals_409"] += 1
        idx = err.get(
            "play_index",
            (err.get("detail") or {}).get("play_index")
            if isinstance(err.get("detail"), dict)
            else None,
        )
        refusals.append({"err": json.dumps(err, ensure_ascii=False)[:300], "play_index": idx})
        if len(refusals) >= MAX_REFUSALS or idx is None or not (0 <= int(idx) < len(plays)):
            return {
                "res": {"status": res["status"], "error": res["error"]},
                "refusals": refusals,
                "stopped": True,
                "sent": jog,
            }
        plays = plays[: int(idx)] + plays[int(idx) + 1 :]


def open_combat(u: User, gid: str, phrases=OPEN_PHRASES) -> dict:
    st: dict = {}
    for phrase in phrases:
        retry(stream, u, gid, {"input_text": phrase})
        time.sleep(3)
        st = retry(state, u, gid)
        if (st.get("combat") or {}).get("active"):
            break
    return st


def conflict(u: User, gid: str, n: int, seen: set[str]) -> dict:
    st = open_combat(u, gid)
    v = view(st)
    if not v["active"]:
        note("sem_combate", conflict=n)
        return {"opened": False}
    fams = sorted({e["fam"] for e in v["enemies"]})
    known = bool(set(fams) & seen)
    out = {
        "opened": True,
        "fams": fams,
        "known_family": known,
        "opening_pressagios": v["pressagios"],
        "rounds": [],
    }
    note("abertura", conflict=n, fams=fams, known=known, pressagios=v["pressagios"])
    for rd in range(1, MAX_ROUNDS + 1):
        check_hand(v)
        attack_on_hero = any(
            p.get("tipo") == "ataque" and p.get("alvo_id") in (None, "player")
            for p in v["pressagios"]
        )
        plays = plan(v, want_defense=known and attack_on_hero)
        r = play_round(u, gid, plays)
        time.sleep(3)
        st = retry(state, u, gid)
        v2 = view(st)
        new_mech = v2["mech"]
        row = {
            "rd": rd,
            "pressagios_before": v["pressagios"],
            "plays": r.get("sent"),
            "refusals": r["refusals"],
            "mech": new_mech,
            "defense_played": any(p.get("card_id") == DEFENSE for p in r.get("sent") or []),
            "outcome": v2["outcome"],
            "outcome_reason": v2["outcome_reason"],
            "combat_result": v2["combat_result"],
            "player_vit": v2["player_vit"],
            "death_pending": v2["death_pending"],
        }
        out["rounds"].append(row)
        note("rodada", conflict=n, **row)
        v = v2
        if not v["active"] or r.get("stopped"):
            break
    if v["active"]:
        retry(stream, u, gid, {"input_text": "Fujo do conflito.", "action_kind": "flee"})
        time.sleep(3)
        out["fled"] = not (retry(state, u, gid).get("combat") or {}).get("active")
    out["final"] = {
        k: v[k]
        for k in ("outcome", "outcome_reason", "combat_result", "player_vit", "death_pending")
    }
    seen.update(fams)
    return out


def presagio(admin) -> dict:
    users, games, res = [], [], {"conflicts": []}
    try:
        a = User(BASE, admin, "A")
        users.append(a)
        note("login", a=retry(a.login))
        r = retry(
            a.post,
            "/game/new",
            {
                "name": "Smoke398",
                "race": "Humano",
                "class_name": "Médico de Campo",
                "region": "Pântano da Melancolia",
                "level": 1,
                "action_id": str(uuid4()),
            },
            timeout=180,
        )
        gid = (r.json() if r.status_code == 200 else {}).get("game_id", "")
        if not gid:
            note("new_game_fail", status=r.status_code)
            return res
        games.append(gid)
        seen: set[str] = set()
        for n in range(1, MAX_CONFLICTS + 1):
            c = conflict(a, gid, n, seen)
            res["conflicts"].append(c)
            defended = any(
                rd["defense_played"] and any("Proteção" in m for m in rd["mech"])
                for rd in c.get("rounds") or []
            )
            if (
                c.get("known_family")
                and defended
                and any(
                    rd["pressagios_before"] and any(p.get("faixa") for p in rd["pressagios_before"])
                    for rd in c.get("rounds") or []
                )
            ):
                res["item4_ok_conflict"] = n
                break
            if (c.get("final") or {}).get("death_pending"):
                break
        return res
    finally:
        res["cleanup"] = cleanup(admin, users, [(users[0], g) for g in games] if users else [])


def purga(admin) -> dict:
    """Gera 1 retrato `unico` (1 imagem paga) e apaga o jogo pela API; as linhas `unico:<jogo>:` somem."""
    from infrastructure.contracts import Principal
    from infrastructure.wallet import PostgresWallet
    from scripts.staging.ops_pool import open_ops_pool
    from scripts.staging.synthetic_data import WALLET_SKU, seed_wallet_prereqs

    users, games, res = [], [], {}
    try:
        seed_wallet_prereqs(ENV["RPG_STAGING_DB_URL"])
        a = User(BASE, admin, "P")
        users.append(a)
        note("login", a=retry(a.login))
        retry(
            lambda: PostgresWallet(
                open_ops_pool(ENV["RPG_STAGING_DB_URL"])
            ).credit_verified_purchase(
                Principal(UUID(a.id), "supabase", a.id),
                channel="web",
                payment_id="pi_smoke398_" + uuid4().hex[:12],
                sku_id=WALLET_SKU,
                verified=True,
            )
        )
        gid = tgt = None
        for region, boss in UNICO_REGIONS:
            r = retry(
                a.post,
                "/game/new",
                {
                    "name": "Smoke398P",
                    "race": "Humano",
                    "class_name": "Devoto do Abismo",
                    "region": region,
                    "level": 1,
                    "action_id": str(uuid4()),
                },
                timeout=180,
            )
            g = (r.json() if r.status_code == 200 else {}).get("game_id", "")
            if not g:
                continue
            games.append(g)
            st = open_combat(a, g, (f"Procuro {boss} e o ataco de frente",) + OPEN_PHRASES)
            un = [
                e
                for e in (st.get("combat") or {}).get("enemies") or []
                if ((e.get("retrato") or {}).get("gerar") or {}).get("escopo") == "unico"
            ]
            note("oferta", region=region, unico=[e.get("name") for e in un])
            if un:
                gid, tgt, res["region"] = g, un[0], region
                break
        if not gid:
            res["stop"] = "sem oferta unico"
            return res
        q = retry(
            a.post, f"/game/{gid}/art/quote", {"image_type": "monster", "enemy_id": tgt["id"]}
        )
        qid = (q.json() if q.status_code == 200 else {}).get("quote_id")
        note("quote", status=q.status_code)
        if not qid:
            res["stop"] = f"quote {q.status_code}"
            return res
        c = retry(
            a.post,
            f"/game/{gid}/art/confirm",
            {"action_id": str(uuid4()), "quote_id": qid, "confirmed": True},
        )
        note("confirm", status=c.status_code)
        rows = []
        for _ in range(60):
            rows = db_rows(
                "select status from app.creature_portraits where portrait_key like %s",
                (f"unico:{gid}:%",),
            )
            if any(r_["status"] == "ready" for r_ in rows):
                break
            time.sleep(3)
        res["rows_before"] = [r_["status"] for r_ in rows]
        d = a.c.delete(f"{BASE}/game/save/{gid}", headers=_idem(a))
        res["delete_status"] = d.status_code
        time.sleep(3)
        res["rows_after"] = len(
            db_rows(
                "select 1 from app.creature_portraits where portrait_key like %s",
                (f"unico:{gid}:%",),
            )
        )
        res["game_row_after"] = len(db_rows("select 1 from app.games where id::text=%s", (gid,)))
        if d.status_code < 300:
            games.remove(gid)
        note("purga", **res)
        return res
    finally:
        res["cleanup"] = cleanup(admin, users, [(users[0], g) for g in games] if users else [])


def cleanup(admin, users: list, games: list) -> dict:
    out: dict = {"games": []}
    for u, g in games:
        try:
            d = u.c.delete(f"{BASE}/game/save/{g}", headers=_idem(u))
            out["games"].append(d.status_code)
        except Exception as exc:  # noqa: BLE001
            out["games"].append(type(exc).__name__)
    out["users"] = [admin.delete_user(u.id) for u in users]
    out["users_exist_after"] = [admin.user_exists(u.id) for u in users]
    note("cleanup", **out)
    return out


def main() -> int:
    admin = s192.Admin(ENV)
    try:
        if MODE in ("presagio", "tudo"):
            RES["presagio"] = presagio(admin)
        if MODE in ("purga", "tudo"):
            RES["purga"] = purga(admin)
    finally:
        (OUT / "result.json").write_text(
            json.dumps(RES, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )
    return 0


sys.exit(main())
