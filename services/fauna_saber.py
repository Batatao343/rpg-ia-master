"""services/fauna_saber.py - o que o jogador leu, viu e viveu vira saber (SPEC-371).

100% Python determinístico, zero LLM. Fecha o ciclo "ler, lutar, aprender" da fauna (SPEC-360):
telegrafos vistos e assinaturas sobrevividas são anotados na cena, absorvidos por rodada no
contador do save (`bestiary_knowledge`) e, por uma regra determinística, revelam o
`contra_jogo` da criatura (Codex, presságio e preparação da cena).

Writer único dos campos `telegrafos_vistos`, `assinaturas_sobrevividas` e `saber_revelado`
(`sinais_vistos` segue com `discovery.record_sinais`). Flag `RPG_FAUNA_SABER=off|on`
(default `off`); com `off` nada aqui toca em estado, cena ou prompt.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

MODES = ("off", "on")
MOTIVOS = ("sobreviveu", "estudada", "rastreada")
MOTIVO_LABEL = {
    "sobreviveu": "Aprendido ao aguentar o golpe preparado",
    "estudada": "Aprendido de tanto enfrentá-la",
    "rastreada": "Aprendido seguindo os rastros",
}
MAX_TELEGRAFOS = 4
MAX_TEXTO = 160
MAX_PREP_LINHA = 200
SINAL_TIPOS = ("rastro", "resto", "som", "cheiro", "marca")
SINAL_LABEL = {
    "rastro": "Rastro",
    "resto": "Restos",
    "som": "Som",
    "cheiro": "Cheiro",
    "marca": "Marca",
}
SABER_JSON = Path(__file__).resolve().parent.parent / "data" / "world" / "bestiario_saber.json"

_warned_mode = False


def _log(name: str, **fields: Any) -> None:
    try:
        from observability.telemetry import log_event

        log_event("fauna_saber", name, level="info", **fields)
    except Exception:  # silent-ok: telemetria nunca derruba o jogo
        pass


def mode() -> str:
    global _warned_mode
    raw = os.getenv("RPG_FAUNA_SABER", "").strip().lower()
    if raw in MODES:
        return raw
    if raw and not _warned_mode:
        _warned_mode = True
        _log("modo_invalido")
    return "off"


def active() -> bool:
    return mode() == "on"


# --------------------------------------------------------------------------
# Fonte do contra-jogo (R5)
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _compiled() -> dict[str, str]:
    if not SABER_JSON.exists():
        return {}
    doc = json.loads(SABER_JSON.read_text(encoding="utf-8"))
    return {
        cid: str(e.get("contra_jogo") or "").strip()
        for cid, e in (doc.get("criaturas") or {}).items()
    }


def contra_jogo_of(creature_id: str) -> str:
    """Contra-jogo da criatura: JSON compilado das fichas, depois a ficha da criatura gerada em
    jogo (overlay); legado sem ficha devolve ``""`` (R7)."""
    cid = str(creature_id or "")
    if not cid:
        return ""
    text = _compiled().get(cid, "")
    if text:
        return text
    try:
        from services import discovery

        template = discovery._bestiary_db().get(cid) or {}
        return str((template.get("ficha") or {}).get("contra_jogo") or "").strip()
    except Exception:  # silent-ok: sem overlay, sem saber
        return ""


# --------------------------------------------------------------------------
# Regra de revelação (R4)
# --------------------------------------------------------------------------
def reveal_reason(rec: dict, creature_id: str) -> str | None:
    """Motivo da revelação ou ``None`` (já revelado, sem fonte, ou nenhum limiar atingido)."""
    from services import discovery

    rec = rec or {}
    if rec.get("saber_revelado") or not contra_jogo_of(creature_id):
        return None
    if int(rec.get("assinaturas_sobrevividas", 0) or 0) >= 1:
        return "sobreviveu"
    if discovery.knowledge_tier(rec) >= 3:
        return "estudada"
    if len(rec.get("sinais_vistos") or []) >= 2 and int(rec.get("fought", 0) or 0) >= 1:
        return "rastreada"
    return None


# --------------------------------------------------------------------------
# Observação na cena (R2)
# --------------------------------------------------------------------------
def _obs(scene: dict) -> dict:
    return scene.setdefault("saber_obs", {})


def observe_promise(scene: dict | None, actor: dict, carta: str, texto: str) -> None:
    if not active() or not isinstance(scene, dict):
        return
    aid = str(actor.get("id") or actor.get("name") or "")
    rows = _obs(scene).setdefault("telegrafos", [])
    row = {"actor_id": aid, "carta": str(carta), "texto": str(texto)}
    if row not in rows:
        rows.append(row)


def observe_fulfilled(scene: dict | None, actor_id: str, carta: str, rnd: int) -> None:
    if not active() or not isinstance(scene, dict):
        return
    _obs(scene).setdefault("cumpridas", []).append(
        {"actor_id": str(actor_id), "carta": str(carta), "rnd": int(rnd)}
    )


# --------------------------------------------------------------------------
# Absorção por rodada e fim de combate (R3, R4, R14)
# --------------------------------------------------------------------------
def _cid(actor: dict | None) -> str:
    if not actor:
        return ""
    from services import discovery

    return discovery.normalize_bestiary_id(actor)


def _aprendeu_linha(nome: str) -> str:
    return f"Você aprendeu como enfrentar {nome}: veja o Bestiário."


def _reveal_all(bk: dict, instances: dict[str, str], turn: int, logs: list[str]) -> dict:
    """Avalia R4 para cada criatura presente (``{cid: nome da instância}``); grava uma vez."""
    for cid, nome in instances.items():
        rec = bk.get(cid)
        if rec is None:
            continue
        motivo = reveal_reason(rec, cid)
        if not motivo:
            continue
        bk[cid] = {**rec, "saber_revelado": {"motivo": motivo, "turn": int(turn)}}
        _log("revelado", cid=cid, motivo=motivo)
        logs.append(_aprendeu_linha(nome))
    return bk


def _present(actors: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for actor in actors:
        cid = _cid(actor)
        if cid and cid not in out:
            out[cid] = str(actor.get("name") or actor.get("id") or cid)
    return out


def absorb(
    bk: dict, scene: dict, actors_by_id: dict[str, dict], player_alive: bool, turn: int
) -> tuple[dict, list[str]]:
    """Depois de cada ``run_round`` do combate real: leva a observação da cena para o save.
    Devolve ``(bk novo, linhas de log)``. Com a flag ``off`` nada muda."""
    if not active():
        return bk, []
    bk = {cid: dict(rec) for cid, rec in (bk or {}).items()}
    logs: list[str] = []
    obs = scene.pop("saber_obs", None) if isinstance(scene, dict) else None
    obs = obs if isinstance(obs, dict) else {}
    for row in obs.get("telegrafos") or []:
        cid = _cid(actors_by_id.get(str(row.get("actor_id"))))
        texto = str(row.get("texto") or "").strip()[:MAX_TEXTO]
        if not cid or not texto:
            continue
        rec = bk.setdefault(cid, {})
        seen = list(rec.get("telegrafos_vistos") or [])
        if texto not in seen and len(seen) < MAX_TELEGRAFOS:
            seen.append(texto)
            rec["telegrafos_vistos"] = seen
            _log("telegrafo", cid=cid)
    if player_alive:
        for row in obs.get("cumpridas") or []:
            cid = _cid(actors_by_id.get(str(row.get("actor_id"))))
            if not cid:
                continue
            rec = bk.setdefault(cid, {})
            rec["assinaturas_sobrevividas"] = int(rec.get("assinaturas_sobrevividas", 0) or 0) + 1
            _log("sobreviveu", cid=cid)
    enemies = [a for a in actors_by_id.values() if not a.get("is_player") and _cid(a)]
    bk = _reveal_all(bk, _present(enemies), turn, logs)
    return bk, logs


def finish_combat(bk: dict, enemies: list[dict], turn: int) -> tuple[dict, list[str]]:
    """Fim do combate, depois de ``record_kills``: regras ``estudada``/``rastreada``."""
    if not active():
        return bk, []
    bk = {cid: dict(rec) for cid, rec in (bk or {}).items()}
    logs: list[str] = []
    bk = _reveal_all(bk, _present(enemies), turn, logs)
    return bk, logs


# --------------------------------------------------------------------------
# Ator, preparação da cena e visão (R8, R11, R13)
# --------------------------------------------------------------------------
def stamp_actor(enemy: dict, bk: dict) -> None:
    """R8: ``enemy["saber_jogador"]`` ao entrar no combate. Fora do painel público."""
    if not active():
        return
    cid = _cid(enemy)
    if not cid:
        return
    rec = (bk or {}).get(cid) or {}
    contra = contra_jogo_of(cid) if rec.get("saber_revelado") else ""
    assinaturas: list[str] = []
    if int(rec.get("assinaturas_sobrevividas", 0) or 0) >= 1:
        from services import enemy_decks

        sig = enemy_decks.assinatura_of(enemy)
        if sig and sig.get("carta"):
            assinaturas.append(str(sig["carta"]))
    enemy["saber_jogador"] = {"contra_jogo": contra or None, "assinaturas": assinaturas}


def prep_line(state: dict, enemies: list[dict]) -> str:
    """R11: linha curta, sem nomes, para a preparação da cena (``""`` quando nada a dizer)."""
    if not active():
        return ""
    bk = (state or {}).get("bestiary_knowledge") or {}
    tipos: list[str] = []
    for cid in _present(enemies):
        for tipo in (bk.get(cid) or {}).get("sinais_vistos") or []:
            if tipo in SINAL_TIPOS and tipo not in tipos:
                tipos.append(tipo)
    partes: list[str] = []
    if tipos:
        partes.append(f"O herói leu antes: {', '.join(tipos)}.")
    aprox = str(((state or {}).get("combat_encounter_hint") or {}).get("aproximacao") or "")
    if aprox:
        partes.append(f"Aproximação: {aprox}")
    return " ".join(" ".join(partes).split())[:MAX_PREP_LINHA]


def view_fields(creature_id: str, rec: dict, tier: int) -> dict:
    """R13: campos extras da entrada do bestiário (``{}`` com a flag off ou tier < 2)."""
    if not active() or tier < 2:
        return {}
    rec = rec or {}
    out: dict = {}
    from services import fauna

    sinais_txt = (fauna.entry(creature_id) or {}).get("sinais") or {}
    sinais = [
        {"tipo": t, "texto": str(sinais_txt[t])}
        for t in (rec.get("sinais_vistos") or [])
        if t in SINAL_TIPOS and sinais_txt.get(t)
    ]
    if sinais:
        out["sinais_vistos"] = sinais
    if rec.get("telegrafos_vistos"):
        out["telegrafos_vistos"] = list(rec["telegrafos_vistos"])
    revelado = rec.get("saber_revelado")
    if isinstance(revelado, dict):
        texto = contra_jogo_of(creature_id)
        motivo = str(revelado.get("motivo") or "")
        if texto and motivo in MOTIVO_LABEL:
            out["contra_jogo"] = texto
            out["contra_jogo_motivo"] = MOTIVO_LABEL[motivo]
    return out
