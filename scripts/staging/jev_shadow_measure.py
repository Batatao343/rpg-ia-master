"""SPEC-217 R15: shadow do Jev no router do staging (CLASSIFY decide; o Jev so observa).

Roda turnos SSE reais (usuarios sinteticos, DeepSeek) com acoes variadas (conversa, combate, comercio,
fabricacao, saque, viagem, exploracao) em varios jogos curtos, e depois junta as linhas ``jev.shadow``
dos logs da funcao (``vercel logs --json``) aos turnos pela janela de tempo de cada turno. Mede:
concordancia nos turnos que o Jev resolveria (rota/alvo/fonte), confusao por rota, cobertura e motivos de
fallback, latencia do Jev, espera adicionada ao turno, timeouts/erros. Teto de chamadas: cada turno faz no
maximo 1 chamada ao Jev, entao ``--max-turns`` limita o gasto. Saida sem ids, segredos ou texto de jogador
real (as acoes sao sinteticas, deste arquivo).

Uso: python -m scripts.staging.jev_shadow_measure --max-turns 58 --out docs/spec217/evidence/shadow.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from scripts.staging import s192
from scripts.staging.e2e_session import _h
from scripts.staging.projection_measure import stream_turn

# (categoria, acao). Combate fica no fim de cada jogo: depois dele o gate Python de combate ativo decide
# (sem Jev), o que desperdicaria turnos de observacao.
SESSIONS: list[list[tuple[str, str]]] = [
    [("story", "Observo ao redor com cuidado."),
     ("talk", "Pergunto à pessoa mais próxima o que tem acontecido por aqui."),
     ("talk", "Olá! Você sabe onde fica o mercado?"),
     ("loot_shop", "Procuro um mercador e compro uma tocha."),
     ("loot_shop", "Vendo a adaga velha ao mercador."),
     ("story", "Examino os muros da cidade."),
     ("loot_take", "Pego a moeda caída no chão."),
     ("talk", "Pergunto ao guarda se há trabalho para um viajante."),
     ("story", "Espero um pouco observando o movimento."),
     ("loot_craft", "Fabrico uma tocha com o pano e o galho."),
     ("travel", "Viajo para a próxima cidade."),
     ("story", "Caminho pela estrada observando o horizonte."),
     ("combat", "Saco a espada e ataco o bandido mais próximo.")],
    [("story", "Olho para o céu e tento entender que horas são."),
     ("talk", "Cumprimento o taverneiro e peço notícias."),
     ("loot_shop", "Compro pão e água para a viagem."),
     ("talk", "E você, viu algo estranho na estrada?"),
     ("loot_take", "Vasculho o baú esquecido no canto."),
     ("story", "Investigo as pegadas perto da porta."),
     ("loot_craft", "Forjo uma ponta de flecha na bigorna."),
     ("talk", "Pergunto ao ferreiro quanto custa consertar meu escudo."),
     ("story", "Subo até a torre para ver a região."),
     ("loot_shop", "Troco duas peles por uma poção."),
     ("story", "Descanso um instante num canto tranquilo."),
     ("story", "Sigo a trilha até a floresta."),
     ("combat", "Investo contra a criatura que me observa.")],
    [("talk", "Digo ao velho que posso ajudar."),
     ("story", "Examino o mapa que carrego."),
     ("loot_take", "Recolho as ervas que encontrei."),
     ("talk", "Pergunto ao velho sobre a estrada para o norte."),
     ("loot_shop", "Pago ao mercador pela corda."),
     ("story", "Escuto o vento e os sons da mata."),
     ("talk", "Chamo o guarda e pergunto pelo capitão."),
     ("loot_craft", "Construo uma armadilha simples com a corda."),
     ("story", "Atravesso a ponte com cuidado."),
     ("loot_take", "Abro a caixa trancada com a chave."),
     ("talk", "Pergunto ao barqueiro quanto custa a travessia."),
     ("story", "Procuro abrigo antes do anoitecer."),
     ("combat", "Ataco o lobo que avança contra mim.")],
    [("story", "Analiso as marcas na parede."),
     ("talk", "Converso com a mulher na praça sobre os rumores."),
     ("loot_shop", "Compro uma poção de cura."),
     ("story", "Observo os viajantes que chegam pela estrada."),
     ("talk", "Pergunto a ela o que houve com a vila."),
     ("loot_take", "Apanho a faca que ficou na mesa."),
     ("story", "Inspeciono a carroça abandonada."),
     ("loot_shop", "Vendo as peles que juntei."),
     ("talk", "Respondo ao guarda que estou só de passagem."),
     ("story", "Entro na estalagem e procuro uma mesa."),
     ("loot_craft", "Fabrico bandagens com o tecido limpo."),
     ("story", "Olho pela janela à procura de movimento."),
     ("combat", "Disparo uma flecha no bandido no telhado.")],
    [("talk", "Pergunto ao mercador sobre rumores recentes."),
     ("story", "Examino um objeto estranho na banca."),
     ("loot_take", "Saqueio o corpo do bandido caído."),
     ("story", "Procuro pistas sobre a tarefa que aceitei."),
     ("talk", "Explico ao capitão o que vi na estrada."),
     ("combat", "Enfrento o mercenário que bloqueia a passagem.")],
]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _stream(c: httpx.Client, base: str, csrf: str, game_id: str, text: str) -> dict:
    """One SSE turn; keeps the Vercel request id (``x-vercel-id`` suffix = log ``requestId``)."""
    ids: list[str] = []

    def hook(response: httpx.Response) -> None:
        if response.request.url.path.endswith("/game/action/stream"):
            ids.append(response.headers.get("x-vercel-id", "").split("::")[-1])

    c.event_hooks["response"] = [hook]
    try:
        row = stream_turn(c, base, csrf, game_id, text)
    finally:
        c.event_hooks["response"] = []
    row["request_id"] = ids[-1] if ids else ""
    return row


def play(base: str, env: dict, max_turns: int, think: float, sessions: list | None = None,
         before_delete=None) -> tuple[list[dict], dict]:
    """``before_delete(game_id) -> dict`` (opcional) roda antes de apagar cada jogo (ex.: ler timing)."""
    admin = s192.Admin(env)
    turns: list[dict] = []
    cleanup = {"games_deleted": 0, "users_deleted": 0, "errors": []}
    origins = json.loads((s192.common.ROOT / "data" / "origins.json").read_text(encoding="utf-8"))
    for session_i, actions in enumerate(sessions or SESSIONS):
        if len(turns) >= max_turns:
            break
        user = admin.create_user()
        game_id = ""
        c = httpx.Client(timeout=60, follow_redirects=False, transport=httpx.HTTPTransport(retries=3))
        try:
            r = s192.app_login(c, base, user)
            csrf = (r.json() if r.status_code == 200 else {}).get("csrf_token") or c.cookies.get("rpg_csrf") or ""
            body = {"name": "Spec217 Sombra", "race": origins["races"][session_i % len(origins["races"])]["name"],
                    "class_name": "Devoto do Abismo",
                    "region": origins["regions"][session_i % len(origins["regions"])]["name"],
                    "level": 1, "action_id": str(uuid4())}
            r = c.post(f"{base}/game/new", headers=_h(base, csrf), json=body, timeout=180)
            game_id = (r.json() if r.status_code == 200 else {}).get("game_id", "")
            if not game_id:
                cleanup["errors"].append(f"new_game:{r.status_code}")
                continue
            for category, text in actions:
                if len(turns) >= max_turns:
                    break
                start = _now_ms()
                row = _stream(c, base, csrf, game_id, text)
                turns.append({"session": session_i, "category": category, "action": text,
                              "request_id": row["request_id"],
                              "start_ms": start, "end_ms": _now_ms(), "status": row["status"],
                              "has_error": row["has_error"], "done_ms": row.get("done"),
                              "turn_count": row.get("turn_count"),
                              "narration_chars": row["narration_chars"]})
                if row["status"] == 503:
                    cleanup["errors"].append("daily_spend_cap_or_503")
                    return turns, cleanup
                time.sleep(think)
        finally:
            if game_id and before_delete is not None:
                try:
                    cleanup.setdefault("per_game", {})[session_i] = before_delete(game_id)
                except Exception as exc:  # noqa: BLE001
                    cleanup["errors"].append(f"before_delete:{type(exc).__name__}")
            if game_id:
                try:
                    cleanup["games_deleted"] += s192.query(env, lambda conn: conn.execute(
                        "delete from app.games where id::text=%s", (game_id,)).rowcount)
                except Exception as exc:  # noqa: BLE001
                    cleanup["errors"].append(type(exc).__name__)
            cleanup["users_deleted"] += admin.delete_user(user["id"]) in (200, 204)
            c.close()
    return turns, cleanup


def fetch_shadow_logs(env: dict, since: str, event: str = "jev.shadow") -> list[dict]:
    """``jev.<mode>`` log lines as dicts with ``ts`` (ms) — only labels/booleans/latencies."""
    out = s192.vercel(["logs", "--environment", "production", "--since", since, "--query", event,
                       "--limit", "1000", "--json"], env, timeout=300)
    rows = []
    for line in (out.stdout or "").splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        data = item.get("data", item) if isinstance(item, dict) else {}
        message = str(data.get("message") or "")
        start = message.find("{")
        if start < 0 or event not in message:
            continue
        try:
            payload = json.loads(message[start:])
        except ValueError:
            continue
        ts = data.get("timestamp") or item.get("timestamp")
        payload["ts"] = int(ts) if isinstance(ts, (int, float)) else _iso_ms(str(ts or ""))
        payload["request_id"] = str(data.get("requestId") or "")
        payload["_path"] = str(data.get("requestPath") or "")
        rows.append(payload)
    # Fluid compute: a line printed while a concurrent request (e.g. the per-minute cron) shares the
    # instance can come back once per request. Same timestamp + same fields = one Jev call; keep the copy
    # attributed to the turn (``/game/action/stream``).
    unique: dict[tuple, dict] = {}
    for row in sorted(rows, key=lambda r: r["_path"] != "/game/action/stream"):
        key = (row.get("ts"), *(str(row.get(k)) for k in sorted(row) if k not in {"request_id", "_path", "ts"}))
        unique.setdefault(key, row)
    for row in unique.values():
        row.pop("_path", None)
    return sorted(unique.values(), key=lambda r: r.get("ts") or 0)


def _iso_ms(value: str) -> int:
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return 0


def join(turns: list[dict], logs: list[dict]) -> list[dict]:
    """By Vercel request id (exact); a turn whose router took a Python gate has no line."""
    for turn in turns:
        hits = [log for log in logs if turn.get("request_id") and log.get("request_id") == turn["request_id"]
                and not log.get("_used")]
        if hits:
            hits[0]["_used"] = True
            turn["shadow"] = {k: v for k, v in hits[0].items() if k not in {"_used", "request_id"}}
        turn.pop("request_id", None)
    return turns


def _pct(values: list[float], p: float):
    return s192.pct(values, p)


def summarize(turns: list[dict], logs: list[dict]) -> dict:
    obs = [t["shadow"] for t in turns if t.get("shadow")]
    covered = [o for o in obs if o.get("covered")]
    agree_route = [o for o in covered if o.get("agree_route")]

    def full(o):
        return o.get("agree_route") and o.get("agree_target") is not False and o.get("agree_loot") is not False

    agree_all = [o for o in covered if full(o)]
    confusion: dict = {}
    for o in covered:
        key = f"{o.get('classify_route')}->{o.get('jev_route')}"
        confusion[key] = confusion.get(key, 0) + 1
    outcomes: dict = {}
    reasons: dict = {}
    for o in obs:
        outcomes[o.get("outcome")] = outcomes.get(o.get("outcome"), 0) + 1
        if o.get("reason"):
            reasons[o["reason"]] = reasons.get(o["reason"], 0) + 1
    unsafe = [o for o in covered if o.get("jev_route") == "combat_agent" and o.get("classify_route") != "combat_agent"]
    by_category: dict = {}
    for t in turns:
        cat = by_category.setdefault(t["category"], {"turns": 0, "observed": 0, "covered": 0, "agree_all": 0})
        cat["turns"] += 1
        o = t.get("shadow")
        if o:
            cat["observed"] += 1
            cat["covered"] += bool(o.get("covered"))
            cat["agree_all"] += bool(o.get("covered") and full(o))
    target_scope = [o for o in covered if o.get("agree_target") is not None]
    loot_scope = [o for o in covered if o.get("agree_loot") is not None]
    jev_lat = [float(o["latency_ms"]) for o in obs if isinstance(o.get("latency_ms"), (int, float))
               and o.get("outcome") not in {"kill_switch"}]
    waits = [float(o.get("wait_ms") or 0) for o in obs]
    return {
        "turns": len(turns), "turns_ok": sum(t["status"] == 200 and not t["has_error"] for t in turns),
        "shadow_log_lines_unique": len(logs), "observations_joined": len(obs),
        "jev_calls": len(logs),
        "covered": len(covered), "coverage": round(len(covered) / len(obs), 4) if obs else None,
        "agreement_route": round(len(agree_route) / len(covered), 4) if covered else None,
        "agreement_all": round(len(agree_all) / len(covered), 4) if covered else None,
        "agreement_target": (f"{sum(bool(o['agree_target']) for o in target_scope)}/{len(target_scope)}"),
        "agreement_loot": f"{sum(bool(o['agree_loot']) for o in loot_scope)}/{len(loot_scope)}",
        "unsafe_combat_escalations_vs_classify": len(unsafe),
        "confusion_classify_to_jev": dict(sorted(confusion.items())),
        "outcomes": outcomes, "fallback_reasons": reasons,
        "jev_latency_ms": {"p50": _pct(jev_lat, 50), "p95": _pct(jev_lat, 95),
                           "max": max(jev_lat) if jev_lat else None},
        "turn_wait_for_jev_ms": {"p50": _pct(waits, 50), "p95": _pct(waits, 95),
                                 "max": max(waits) if waits else None},
        "by_category": by_category,
        "disagreements": [{"category": t["category"], "action": t["action"],
                           **{k: t["shadow"].get(k) for k in ("classify_route", "jev_route", "agree_route",
                                                             "agree_target", "agree_loot", "confidence")}}
                          for t in turns if t.get("shadow") and t["shadow"].get("covered")
                          and not full(t["shadow"])],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--max-turns", type=int, default=58)
    ap.add_argument("--think", type=float, default=1.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--logs-only-since", help="so recoleta logs (ex.: 60m) e junta com turns de --turns-file")
    ap.add_argument("--turns-file")
    a = ap.parse_args(argv)
    if a.max_turns > 60:
        print("recusado: teto de 60 chamadas ao Jev", file=sys.stderr)
        return 2
    env = s192.load_env()
    started = time.time()
    if a.turns_file:
        saved = json.loads(open(a.turns_file, encoding="utf-8").read())
        turns, cleanup = saved["turns"], saved.get("cleanup") or {}
    else:
        turns, cleanup = play(a.base, env, a.max_turns, a.think)
        with open(a.out + ".turns.json", "w", encoding="utf-8") as fh:
            json.dump({"turns": turns, "cleanup": cleanup}, fh, ensure_ascii=False, indent=1)
        time.sleep(20)  # deixa os logs da funcao chegarem
    since = a.logs_only_since or f"{int((time.time() - started) / 60) + 5}m"
    logs = fetch_shadow_logs(env, since)
    turns = join(turns, logs)
    res = {"at": s192.now_iso(), "turns": turns, "cleanup": cleanup, "summary": summarize(turns, logs)}
    s192.common.write_evidence("spec217_shadow", res, a.out)
    print(json.dumps({"summary": {k: v for k, v in res["summary"].items() if k != "disagreements"},
                      "cleanup": cleanup}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
