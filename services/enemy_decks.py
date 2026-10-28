"""services/enemy_decks.py - baralhos de inimigo por família/facção e padrão de intenção (SPEC-332).

Camada determinística (sem LLM, sem rng global) sobre a IA tática do inimigo:

- ``build_enemy_deck``: o conflito monta o baralho da criatura = ``cartas`` próprias
  (assinatura da criatura) + 3-5 da família + 0-3 da facção, escolhidas por hash de
  ``id`` + seed (a mesma criatura sempre monta o mesmo baralho);
- ``plan``: o *padrão de intenção* (``padrao``: lista de tipos de presságio) e a
  *assinatura* (``assinatura``: carta forte a cada N rodadas) da rodada. Os gatilhos do
  perfil tático (vida baixa, alvo vulnerável...) continuam com precedência: o plano só
  vale quando o gatilho que decide é ``sempre``;
- ``prenuncio``: frase do Presságio (SPEC-329) uma rodada ANTES da assinatura;
- ``apply_phases``: chefes trocam de fase por Vitalidade (baralho extra + padrão novo);
- ``padrao_publico``: o "costuma: ..." do painel, depois de o personagem já ter visto a
  família lutar (``bestiary_knowledge``).

Flag ``RPG_ENEMY_DECKS=off|shadow|on`` (default ``off``): ``off`` = nada muda;
``shadow`` monta o baralho numa cópia (``_deck_shadow``) e mede, sem usar; ``on`` usa.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

_DIR = Path(__file__).resolve().parent.parent / "data" / "cards" / "inimigos"
_DECKS_PATH = _DIR / "_decks.json"
_MODES = ("off", "shadow", "on")

FAMILIAS = (
    "predador",
    "covarde_oportunista",
    "conjurador",
    "morto_vivo_implacavel",
    "bruto",
    "guardiao",
    "predador_apice",
    "tatico",
    "lider_matilha",
    "emboscador",
    "abissal",
)
_ABISSAL_HINTS = ("abis", "vazio", "aberra")

# tipos do padrão -> efeitos de carta que o cumprem (o resto cai no ataque básico)
_DAMAGE_KINDS = frozenset({"dano", "contra_ataque", "dot"})
_CONTROL_KINDS = frozenset(
    {
        "aplicar_condicao",
        "marca",
        "taunt",
        "empurrao",
        "torpor",
        "rachadura",
        "sangria",
        "marca_do_abismo",
        "mover_alvo_zona",
        "revelar",
    }
)
_SLOT_LABEL = {
    "ataque": "ataque",
    "ataque_multiplo": "golpe em área",
    "defesa": "defesa",
    "reforco_proprio": "reforço",
    "enfraquecer": "enfraquece",
    "mover": "manobra",
}

_EXTRA_FILES = frozenset({"chefes"})  # cartas de fase de chefe: não são pool de família
_LOG = logging.getLogger(__name__)
_meta_cache: dict | None = None
_pools_cache: dict | None = None


# --------------------------------------------------------------------------
# Flag
# --------------------------------------------------------------------------
def mode() -> str:
    raw = os.getenv("RPG_ENEMY_DECKS", "off").strip().lower()
    return raw if raw in _MODES else "off"


def active() -> bool:
    return mode() == "on"


# --------------------------------------------------------------------------
# Dados
# --------------------------------------------------------------------------
def _meta() -> dict:
    global _meta_cache
    if _meta_cache is None:
        try:
            _meta_cache = json.loads(_DECKS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _meta_cache = {}
    return _meta_cache


def _pools() -> dict[str, dict[str, list[str]]]:
    """``{"familias": {fam: [ids]}, "faccoes": {fac: [ids]}}`` lidos de ``data/cards/inimigos``."""
    global _pools_cache
    if _pools_cache is None:
        fams: dict[str, list[str]] = {}
        facs: dict[str, list[str]] = {}
        if _DIR.is_dir():
            for path in sorted(_DIR.glob("*.json")):
                if path.name.startswith("_"):
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                ids = [str(c["id"]) for c in data.get("cards") or [] if c.get("id")]
                stem = path.stem
                if stem.startswith("faccao_"):
                    facs[stem[len("faccao_") :]] = ids
                elif stem in FAMILIAS:
                    fams[stem] = ids
                elif stem not in _EXTRA_FILES:  # arquivo órfão: fora de FAMILIAS/faccao_/chefes
                    _LOG.warning("enemy_decks: arquivo de baralho ignorado: %s", path.name)
        _pools_cache = {"familias": fams, "faccoes": facs}
    return _pools_cache


def reload() -> None:
    global _meta_cache, _pools_cache
    _meta_cache = None
    _pools_cache = None


def _fold(text: object) -> str:
    raw = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return raw.strip().lower().replace("-", "_").replace(" ", "_")


def family_key(creature: dict) -> str | None:
    """Família do baralho: ``abissal`` por sinal explícito, senão o ``arquetipo`` curado."""
    blob = " ".join(
        str(creature.get(k) or "") for k in ("archetype_id", "id", "faction", "type")
    ).lower()
    if any(h in blob for h in _ABISSAL_HINTS):
        return "abissal"
    arq = _fold(creature.get("arquetipo"))
    return arq if arq in FAMILIAS else None


def _h(*parts: object) -> int:
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12], 16)


def _own_ids(creature: dict) -> list[str]:
    out: list[str] = []
    for entry in creature.get("cartas") or creature.get("enemy_cards") or []:
        cid = str(entry.get("id") if isinstance(entry, dict) else entry or "").strip()
        if cid and cid not in out:
            out.append(cid)
    return out


# --------------------------------------------------------------------------
# R3 - montagem do baralho
# --------------------------------------------------------------------------
def _signature_configs(creature: dict) -> list[dict]:
    fam = family_key(creature)
    cfg = (_meta().get("familias") or {}).get(fam or "") or {}
    return [s for s in cfg.get("assinaturas") or [] if isinstance(s, dict) and s.get("carta")]


def family_signature(creature: dict, seed: int | str = 0) -> dict | None:
    """Assinatura DA FAMÍLIA para esta criatura (uma de duas, por hash de id+seed, para que
    nenhuma carta fique em mais de ~15 criaturas)."""
    sigs = _signature_configs(creature)
    if not sigs:
        return None
    return sigs[_h(creature.get("id"), seed, "sig") % len(sigs)]


def _curate_shared(creature: dict, deck: list[str], seed: int | str) -> tuple[list[str], int]:
    """Curadoria do bestiário (critério 1), só com ``on``: cartas legadas compartilhadas por
    dezenas de criaturas (``legadas_compartilhadas`` em ``_decks.json``) ficam em metade delas
    (hash de id+seed). Devolve ``(deck, n_retiradas)``: a montagem garante um ataque da família
    no lugar, SEM aumentar o número de cartas da família (não empurra nenhuma carta nova acima
    do teto de uso). O ``bestiary.json`` não muda, então ``off`` segue idêntico."""
    shared = set(_meta().get("legadas_compartilhadas") or [])
    out: list[str] = []
    dropped = 0
    for card_id in deck:
        if card_id in shared and _h(creature.get("id"), seed, "curadoria", card_id) % 2 == 1:
            dropped += 1
        else:
            out.append(card_id)
    return out, dropped


def _is_attack(card_id: str) -> bool:
    from services import cards

    return ((cards.get_card(card_id) or {}).get("efeito") or {}).get("kind") == "dano"


_CASTER_ARCHETYPES = {"conjurador", "mistico", "místico", "abissal"}
_CASTER_DAMAGE = {"arcano", "abissal", "elemental"}


def _is_melee_only(creature: dict) -> bool:
    """SPEC-353 R38a: criatura sem estilo conjurador e só com ataques corpo a corpo."""
    if _fold(creature.get("arquetipo")) in {_fold(a) for a in _CASTER_ARCHETYPES}:
        return False
    attacks = [a for a in (creature.get("attacks") or []) if isinstance(a, dict)]
    return bool(attacks) and all(str(a.get("type") or "melee") == "melee" for a in attacks)


def _fits_creature(creature: dict, card_id: str) -> bool:
    """Carta de família/facção de dano arcano/abissal/elemental não entra em criatura só-melee."""
    from services import cards

    dtype = str(((cards.get_card(card_id) or {}).get("efeito") or {}).get("dano_tipo") or "")
    return not (dtype in _CASTER_DAMAGE and _is_melee_only(creature))


def build_enemy_deck(creature: dict, seed: int | str = 0) -> list[str]:
    """Baralho de conflito da criatura: próprias + 3-5 da família + 0-3 da facção.
    Determinístico por ``id`` + ``seed`` (``deck_seed`` do conflito, gravado no spawn); mantém a ordem das próprias e nunca repete."""
    deck = _own_ids(creature)
    cid = creature.get("id")
    fam = family_key(creature)
    pools = _pools()
    deck, dropped = _curate_shared(creature, deck, seed)
    if dropped and not fam:
        deck, dropped = _own_ids(creature), 0  # sem família para repor: mantém a carta legada
    sig = family_signature(creature, seed)
    if fam:
        # a assinatura alternativa (a outra de `assinaturas`) só vale como assinatura
        alt = {str(s["carta"]) for s in _signature_configs(creature)}
        pool = [
            c
            for c in pools["familias"].get(fam, [])
            if c not in deck and c not in alt and _fits_creature(creature, c)
        ]
        want = 3 + _h(cid, seed, "fam") % 3  # 3..5
        picked: list[str] = []
        if sig and sig["carta"] not in deck:
            picked.append(sig["carta"])
        rest = sorted((c for c in pool if c not in picked), key=lambda c: _h(cid, seed, "fam", c))
        if dropped and not any(_is_attack(c) for c in (*deck, *picked)):
            atk = next((c for c in rest if _is_attack(c)), None)
            if atk:  # o ataque que repõe a carta legada entra dentro da cota da família
                picked.append(atk)
                rest.remove(atk)
        picked += rest[: max(0, want - len(picked))]
        deck += picked
    fac = _fold(creature.get("faction"))
    if fac and pools["faccoes"].get(fac):
        pool = [c for c in pools["faccoes"][fac] if c not in deck and _fits_creature(creature, c)]
        want = _h(cid, seed, "fac") % 4  # 0..3
        deck += sorted(pool, key=lambda c: _h(cid, seed, "fac", c))[:want]
    return deck


def apply_deck(actor: dict, seed: int | str | None = None) -> None:
    """Chamado ao normalizar a ficha do inimigo. ``on`` troca ``cartas``; ``shadow`` só
    guarda o baralho em ``_deck_shadow`` (para medir). Idempotente."""
    m = mode()
    if m == "off":
        return
    if m == "on":
        if actor.get("_deck332"):
            return
        pools = _pools()
        known = {
            c for ids in (*pools["familias"].values(), *pools["faccoes"].values()) for c in ids
        }
        # F-1: o marcador `_deck332` decide; sem ele (ficha reconstruída) só conta como já
        # montada com >= 3 cartas dos pools (a montagem soma >= 3 da família), de modo que
        # 1-2 cartas `inf_*` curadas no bestiário não pulem a montagem.
        if len(known & set(_own_ids(actor))) >= 3:
            actor["_deck332"] = True
            return
        actor["cartas"] = build_enemy_deck(
            actor, actor.get("deck_seed", 0) if seed is None else seed
        )
        actor["_deck332"] = True
    elif not actor.get("_deck332_shadow"):
        actor["_deck_shadow"] = build_enemy_deck(
            actor, actor.get("deck_seed", 0) if seed is None else seed
        )
        actor["_deck332_shadow"] = True


# --------------------------------------------------------------------------
# R4 - padrão de intenção e assinatura
# --------------------------------------------------------------------------
def _profile(actor: dict) -> dict:
    prof = actor.get("tactical_profile")
    return prof if isinstance(prof, dict) else {}


def _phase_cfg(actor: dict) -> dict:
    idx = int(actor.get("fase_idx", 0) or 0)
    fases = _sorted_phases(actor)
    return fases[idx - 1] if 0 < idx <= len(fases) else {}


def pattern_of(actor: dict) -> list[str]:
    """Padrão vigente: fase do chefe > perfil da criatura > padrão da família."""
    phase = _phase_cfg(actor).get("padrao")
    own = _profile(actor).get("padrao")
    fam = ((_meta().get("familias") or {}).get(family_key(actor) or "") or {}).get("padrao")
    for cand in (phase, own, fam):
        if isinstance(cand, list) and cand:
            return [str(s) for s in cand]
    return []


def assinatura_of(actor: dict) -> dict | None:
    """``{carta, a_cada_n, telegrafo}``: fase > perfil > família. ``a_cada_n >= 2``."""
    phase_sig = _phase_cfg(actor).get("assinatura")
    cands = (
        phase_sig,
        _profile(actor).get("assinatura"),
        family_signature(actor, actor.get("deck_seed", 0)),
    )
    for cand in cands:
        if isinstance(cand, dict) and cand.get("carta"):
            if cand is phase_sig:
                cand = {**cand, "_fase": True}
            try:
                n = int(cand.get("a_cada_n", 3))
            except (TypeError, ValueError):
                continue
            if n >= 2:
                return {**cand, "a_cada_n": n}
    return None


def _sig_falls_on(actor: dict, sig: dict, rnd: int) -> bool:
    """A assinatura cai na rodada ``rnd``? Cada criatura tem um desvio próprio (hash do id,
    ou ``desvio`` explícito) para que um bando não dispare todas na mesma rodada. Nunca antes
    da rodada 2: a assinatura sempre tem uma rodada anterior para ser telegrafada."""
    n = int(sig["a_cada_n"])
    try:
        off = int(sig["desvio"])
    except (KeyError, TypeError, ValueError):
        off = _h(actor.get("id"), "desvio") % n
    if sig.get("_fase") and rnd < int(actor.get("fase_rnd", 0) or 0) + 1:
        return False  # assinatura de fase nova: só depois de uma rodada telegrafada
    return rnd >= 2 and (rnd + off) % n == 0


def plan(actor: dict, rnd: int) -> dict | None:
    """Plano da rodada ``rnd`` (1-based): ``{"slot": tipo, "assinatura": carta|None}``.
    ``None`` quando a criatura não tem padrão nem assinatura."""
    from services import cards

    pat = pattern_of(actor)
    sig = assinatura_of(actor)
    if not pat and not sig:
        return None
    slot = pat[(max(1, rnd) - 1) % len(pat)] if pat else "ataque"
    carta = None
    if (
        sig
        and not _badly_wounded(actor)  # mesmo helper do `prenuncio`: sem promessa, sem jogada
        and _sig_falls_on(actor, sig, rnd)
        and sig["carta"] in cards.enemy_card_ids(actor)
    ):
        carta = str(sig["carta"])
    return {"slot": slot, "assinatura": carta, "rnd": rnd}


def _badly_wounded(actor: dict) -> bool:
    """Espelha ``vitalidade_baixa`` do orquestrador (<= 35 % ou ferimento grave/crítico)."""
    if _vitality_pct(actor) <= 35.0:
        return True
    wounds = actor.get("ferimentos") or {}
    return isinstance(wounds, dict) and any(wounds.get(k) for k in ("grave", "critico"))


def prenuncio(actor: dict, rnd_exec: int) -> str | None:
    """Frase do Presságio quando a assinatura cai na rodada SEGUINTE a ``rnd_exec``."""
    sig = assinatura_of(actor)
    if not sig:
        return None
    if _badly_wounded(actor):  # perfil decidiria por fuga/recuo, não pelo `sempre`: não promete
        return None
    if not _sig_falls_on(actor, sig, rnd_exec + 1):
        return None
    from services import cards

    if sig["carta"] not in cards.enemy_card_ids(actor):
        return None
    texto = str(sig.get("telegrafo") or "{nome} se prepara para algo pior.")
    return texto.format(nome=str(actor.get("name") or actor.get("id") or "O inimigo"))


def card_pool_kinds(slot: str) -> frozenset[str] | None:
    """Efeitos de carta preferidos pelo ``slot`` do padrão (``None`` = sem preferência)."""
    if slot in ("ataque", "ataque_multiplo"):
        return _DAMAGE_KINDS
    if slot == "enfraquecer":
        return _CONTROL_KINDS
    return None


def rotate_index(actor: dict, rnd: int, size: int) -> int:
    """Índice estável dentro dos candidatos (varia por rodada e por criatura, sem rng)."""
    return (_h(actor.get("id"), "rot") + max(0, rnd - 1)) % size if size else 0


# --------------------------------------------------------------------------
# R5 - fases de chefe
# --------------------------------------------------------------------------
def _sorted_phases(actor: dict) -> list[dict]:
    """Fases em ordem de entrada (``ate_vitalidade_pct`` decrescente)."""
    raw = _profile(actor).get("fases")
    if not isinstance(raw, list):
        # fases autoradas por criatura em `_decks.json` (não tocam o bestiário: `off` idêntico)
        base = str(actor.get("archetype_id") or re.sub(r"_\d+$", "", str(actor.get("id") or "")))
        raw = (_meta().get("fases") or {}).get(base)
    if not isinstance(raw, list):
        return []
    ok = [f for f in raw if isinstance(f, dict) and isinstance(f.get("ate_vitalidade_pct"), int)]
    return sorted(ok, key=lambda f: -int(f["ate_vitalidade_pct"]))


def _vitality_pct(actor: dict) -> float:
    try:
        cur = float(actor.get("vitalidade", actor.get("hp", 0)) or 0)
        mx = float(actor.get("max_vitalidade", actor.get("max_hp", 1)) or 1)
    except (TypeError, ValueError):
        return 100.0
    return max(0.0, min(100.0, 100.0 * cur / max(1.0, mx)))


def apply_phases(
    actors_by_id: dict[str, dict], sides: dict[str, list[str]], out: dict, rnd: int = 0
) -> bool:
    """Troca de fase dos inimigos vivos (só ``on``). Fase só avança, nunca volta.
    Acrescenta ``baralho_extra`` a ``cartas`` e narra em ``out['logs']``. Devolve True
    se alguém mudou de fase (o chamador refaz o presságio)."""
    if not active():
        return False
    changed = False
    for aid in sides.get("enemy", []):
        actor = actors_by_id.get(aid)
        if not actor or actor.get("dead") or actor.get("fled"):
            continue
        fases = _sorted_phases(actor)
        if not fases:
            continue
        pct = _vitality_pct(actor)
        reached = sum(1 for f in fases if pct <= int(f["ate_vitalidade_pct"]))
        current = int(actor.get("fase_idx", 0) or 0)
        if reached <= current:
            continue
        from services import cards

        for idx in range(current, reached):
            fase = fases[idx]
            cartas = list(actor.get("cartas") or [])
            for extra in fase.get("baralho_extra") or []:
                if extra not in cartas and cards.get_card(str(extra)):
                    cartas.append(str(extra))
            actor["cartas"] = cartas
        actor["fase_idx"] = reached
        actor["fase_rnd"] = int(rnd) + 1  # 1ª rodada da fase nova (assinatura dela: depois)
        nome = str(actor.get("name") or aid)
        for idx in range(current, reached):  # dano que pula fases narra todas, em ordem
            linha = str(
                fases[idx].get("narracao") or "{nome} muda de postura; a luta não será a mesma."
            )
            out.setdefault("logs", []).append(linha.format(nome=nome))
            out.setdefault("fases", []).append({"actor_id": aid, "fase": idx + 1})
        changed = True
    return changed


# --------------------------------------------------------------------------
# R6 - conhecimento do padrão
# --------------------------------------------------------------------------
def known_pattern(actor: dict) -> bool:
    """O personagem já viu esta família lutar (carta revelada neste combate ou no bestiário)."""
    return bool(actor.get("revealed_cards"))


def padrao_publico(actor: dict) -> str | None:
    """``"costuma: ataque, ataque, reforço"`` quando o padrão já é conhecido."""
    if not active() or not known_pattern(actor):
        return None
    pat = pattern_of(actor)
    if not pat:
        return None
    texto = "costuma: " + ", ".join(_SLOT_LABEL.get(s, s) for s in pat)
    sig = assinatura_of(actor)
    if sig:
        texto += f"; a cada {sig['a_cada_n']} rodadas, algo pior"
    return texto


def shadow_summary(actors_by_id: dict[str, dict], sides: dict[str, list[str]]) -> dict[str, Any]:
    """Medição do modo ``shadow``: quantos inimigos, quantas cartas novas montariam."""
    total = novos = 0
    for aid in sides.get("enemy", []):
        actor = actors_by_id.get(aid) or {}
        shadow = actor.get("_deck_shadow")
        if shadow is None:
            continue
        total += 1
        novos += max(0, len(shadow) - len(_own_ids(actor)))
    return {"inimigos": total, "cartas_novas": novos}
