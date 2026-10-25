"""SPEC-314: fações do mundo sob a regra de ouro (o NPC não entrega o plano secreto).

Puro e determinístico: sem LLM, sem rede, sem gravação. Tudo sai de `faction_intel` (o que o
jogador sabe), da fação do próprio NPC e da faixa de relação.

API pública estável (usada também pela SPEC-315):

- ``is_secret(fid)``                       a fação é secreta (catálogo ou visibilidade do grafo)
- ``known_to_player(state, fid)``          o jogador sabe que a fação existe (``intel.known``)
- ``goal_known_to_player(state, fid)``     o jogador sabe o plano (``intel.knows_goal``)
- ``display_faction(state, fid)``          nome, ou "uma facção desconhecida" se secreta e ignota
- ``redacted_lore_ids(state, own="")``     ids do Codex que o RAG não pode devolver (R13)
- ``npc_faction_view(...)`` / ``resolve_proposed_id`` / ``cap_reveal``  bloco do NPC e propostas
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field

ALIAS_OWN = "sua_irmandade"
UNKNOWN_FACTION = "uma facção desconhecida"
LORE_REDACT_PURPOSES = frozenset({"npc", "story", "combat_narration"})
_PLAN_TIERS = frozenset({"amistoso", "leal"})


def is_secret(fid: str) -> bool:
    """Catálogo `secret` ou entidade de fação com visibilidade != public (SPEC-310 R-gate)."""
    from services import faction_membership as fm
    from services import graph_resolver as gr

    fid = str(fid or "")
    if not fid:
        return False
    if fm.load_catalog().get(fid, {}).get("secret"):
        return True
    ent = gr.get_entity(fid) or {}
    if ent.get("type") not in (None, "faction"):
        return False
    return bool(ent) and str(ent.get("visibility") or "public") != "public"


def _intel_row(state: Mapping | None, fid: str) -> dict:
    intel = (state or {}).get("faction_intel") if isinstance(state, Mapping) else None
    if not isinstance(intel, dict):
        return {}
    row = intel.get(fid)
    return row if isinstance(row, dict) else {}


def known_to_player(state: Mapping | None, fid: str) -> bool:
    return bool(_intel_row(state, fid).get("known"))


def goal_known_to_player(state: Mapping | None, fid: str) -> bool:
    return bool(_intel_row(state, fid).get("knows_goal"))


def display_faction(state: Mapping | None, fid: str) -> str:
    """R14: nome da fação, ou "uma facção desconhecida" se secreta que o jogador não conhece."""
    from services import faction_membership as fm

    if is_secret(fid) and not known_to_player(state, fid):
        return UNKNOWN_FACTION
    return fm.faction_name(state or {}, fid)


def _is_faction_id(fid: str) -> bool:
    from services import faction_membership as fm

    return str(fid or "") in fm.load_catalog()


def display_if_faction(
    state: Mapping | None, entity_id: str, fallback: str, unknown: str = UNKNOWN_FACTION
) -> str:
    """`fallback` (nome já resolvido) salvo se `entity_id` for fação secreta ignota (R14).

    `unknown` troca o texto da máscara (a crônica do jogador usa "homens sem insígnia")."""
    try:
        if (
            entity_id
            and _is_faction_id(entity_id)
            and display_faction(state, entity_id) == UNKNOWN_FACTION
        ):
            return unknown
    except Exception as exc:  # falha fechada: nunca derruba o pack
        from observability.telemetry import log_fallback

        log_fallback("faction_gate", "display_failed", exc)
        return unknown
    return fallback


# Apelidos além do nome oficial (e do nome sem artigo): nomes de criaturas, slugs, termos-núcleo.
_EXTRA_ALIASES: dict[str, tuple[str, ...]] = {
    "mao_sombria": ("Mão Sombria",),
    "filhos_chama_azul": ("Chama Azul", "Filhos da Chama"),
    "druidas_renegados": (
        "Druida-Renegado",
        "Druida Renegado",
        "Druidas Renegados",
        "Druidas-renegados",
    ),
    "cultistas_destilacao": ("Cultista da Destilação", "Destilação"),
}
_ARTICLES = ("A ", "O ", "Os ", "As ")
_ACCENTS = {"a": "aáàâãä", "e": "eéèêë", "i": "iíìîï", "o": "oóòôõö", "u": "uúùûü", "c": "cç"}
MASK_TEXT = "[facção desconhecida]"


def aliases(fid: str) -> tuple[str, ...]:
    """Nome, nome sem artigo e apelidos curados da fação (maiores primeiro)."""
    from services import faction_membership as fm

    name = fm.faction_name({}, fid)
    out = {name}
    for art in _ARTICLES:
        if name.startswith(art):
            out.add(name[len(art) :])
    out.update(_EXTRA_ALIASES.get(fid, ()))
    return tuple(sorted((a for a in out if a and a != fid), key=len, reverse=True))


def _alias_regex(alias: str):
    import re

    words = [w for w in re.split(r"[\s_\-]+", _fold_word(alias)) if w]
    parts = [
        "".join(f"[{_ACCENTS[c]}]" if c in _ACCENTS else re.escape(c) for c in w) for w in words
    ]
    # separador flexível cobre espaço, hífen e "_" (slugs); bordas só por letra/dígito
    return re.compile(r"(?<![^\W_])" + r"[\s_\-]+".join(parts) + r"(?![^\W_])", re.IGNORECASE)


_PATTERNS: dict[str, tuple] = {}


def _patterns(fid: str) -> tuple:
    if fid not in _PATTERNS:
        _PATTERNS[fid] = tuple(_alias_regex(a) for a in aliases(fid))
    return _PATTERNS[fid]


def _unknown_secret_ids(state: Mapping | None, keep: Collection[str] = ()) -> list[str]:
    from services import faction_membership as fm

    return [
        fid
        for fid in fm.load_catalog()
        if fid not in keep and is_secret(fid) and not known_to_player(state, fid)
    ]


def mask_secret_names(
    state: Mapping | None, text: str, keep: Collection[str] = (), repl: str = MASK_TEXT
) -> str:
    """Troca nome/apelidos de fação secreta ignota por `repl` em texto livre ou slug."""
    out = str(text or "")
    if not out:
        return out
    for fid in _unknown_secret_ids(state, keep):
        for pat in _patterns(fid):
            out = pat.sub(repl, out)
    return out


def _fold_word(w: str) -> str:
    import unicodedata

    base = unicodedata.normalize("NFKD", w.casefold())
    return "".join(c for c in base if not unicodedata.combining(c))


def beat_leaks(state: Mapping | None, text: str) -> bool:
    """P2-4: o beat cita fação secreta ignota ou ≥2 termos do plano de fação sem `knows_goal`."""
    import re

    import gamedata
    from services import faction_membership as fm

    raw = str(text or "")
    if not raw:
        return False
    if mask_secret_names(state, raw) != raw:
        return True
    words = {_fold_word(w) for w in re.findall(r"\w{7,}", raw)}
    goals = {f.get("id"): f.get("goal", "") for f in gamedata.seed_factions()}
    for fid in fm.load_catalog():
        if not is_secret(fid) or goal_known_to_player(state, fid):
            continue
        toks = {_fold_word(w) for w in re.findall(r"\w{7,}", str(goals.get(fid, "")))}
        if len(toks & words) >= 2:
            return True
    return False


def redacted_lore_ids(state: Mapping | None, own: str = "") -> frozenset[str]:
    """R13: páginas do Codex de fação secreta cujo plano o jogador ainda não conhece.

    Exceção: a fação do próprio NPC quando o jogador é membro ativo dela."""
    from services import faction_membership as fm

    ids: set[str] = set(fm.load_catalog())
    rows = state.get("factions") if isinstance(state, Mapping) else None
    for f in rows or []:
        if isinstance(f, dict) and f.get("id"):
            ids.add(str(f["id"]))
    out: set[str] = set()
    for fid in ids:
        if not is_secret(fid) or goal_known_to_player(state, fid):
            continue
        if own and fid == own and fm.is_member(state or {}, fid):
            continue
        out.add(fid)
    return frozenset(out)


@dataclass(frozen=True)
class FactionView:
    block: str
    visible: Mapping[str, str] = field(default_factory=dict)  # id no prompt -> faction_id real
    goal_shown: frozenset[str] = frozenset()  # faction_ids cuja linha trouxe o plano
    counts: Mapping[str, int] = field(default_factory=dict)
    anon: frozenset[str] = frozenset()  # faction_ids mostrados só como alias (sem nome)


_INSTRUCTION = (
    "Fale do plano de uma facção só se ele estiver escrito acima. "
    '"plano: você não sabe" = admita que não sabe ou especule sem afirmar. '
    "Facção fora desta lista: você nunca ouviu falar dela.\n"
    "Registre em 'faction_reveals' só ids desta lista, com o nível: 'existencia' (só citou), "
    "'objetivo' (contou o plano), 'progresso' (sabe quão perto está)."
)
_EMPTY = "Nenhuma facção conhecida no mundo."


def _other_plan_allowed(state: Mapping, fid: str, own: str, tier: str, secret: bool) -> bool:
    from services import faction_membership as fm
    from services import reputation

    if goal_known_to_player(state, fid):
        return True
    if not secret:
        return reputation.reveal_ceiling(tier) in ("objetivo", "progresso")
    # D2: inimigo jurado conta o plano da secreta que o jogador já sabe que existe.
    if own and known_to_player(state, fid) and tier in _PLAN_TIERS:
        return fid in (fm.load_catalog().get(own, {}).get("rivals") or [])
    return False


def _build(state: Mapping, npc_key: str, row: Mapping, tier: str) -> FactionView:
    from services import faction_membership as fm
    from services import npc_self
    from world_utils import ensure_factions

    own = npc_self.self_faction(dict(state), npc_key, dict(row or {}))
    lines: list[str] = []
    visible: dict[str, str] = {}
    shown: set[str] = set()
    anon: set[str] = set()
    hidden = 0
    for f in ensure_factions(state.get("factions")):
        fid = str(f.get("id") or "")
        if not fid or f.get("defeated"):
            continue
        secret = is_secret(fid)
        head = f"{f.get('name')} ({f.get('region', '')})"
        goal = str(f.get("goal", ""))
        if fid == own and secret:
            member = fm.is_member(state, fid)
            named = known_to_player(state, fid) or tier == "leal" or member
            plan = goal_known_to_player(state, fid) or member
            if not named:
                visible[ALIAS_OWN] = fid
                anon.add(fid)
                lines.append(
                    f"- id={ALIAS_OWN} · (a sua; secreta) · nunca nomeie nem descreva o plano"
                )
                continue
            visible[fid] = fid
            if plan:
                shown.add(fid)
                lines.append(f"- id={fid} · {head} · (a sua; secreta) · plano: {goal}")
            else:
                lines.append(
                    f"- id={fid} · {head} · (a sua; secreta) · plano: não o descreva a ninguém"
                )
            continue
        if fid == own:
            visible[fid] = fid
            shown.add(fid)
            lines.append(f"- id={fid} · {head} · (a sua) · plano: {goal}")
            continue
        if secret and not known_to_player(state, fid):
            hidden += 1
            continue
        visible[fid] = fid
        if _other_plan_allowed(state, fid, own, tier, secret):
            shown.add(fid)
            lines.append(f"- id={fid} · {head} · plano: {goal}")
        else:
            lines.append(f"- id={fid} · {head} · plano: você não sabe")
    body = "\n".join(lines) if lines else _EMPTY
    counts = {
        "listed": len(lines),
        "hidden_secret": hidden,
        "goals": len(shown),
        "alias": int(bool(anon)),
    }
    return FactionView(
        block=f"{body}\n{_INSTRUCTION}",
        visible=visible,
        goal_shown=frozenset(shown),
        counts=counts,
        anon=frozenset(anon),
    )


def _public_fallback(state: Mapping) -> FactionView:
    """R17: só fações públicas, sem plano (o turno segue)."""
    from world_utils import ensure_factions

    lines: list[str] = []
    visible: dict[str, str] = {}
    for f in ensure_factions(state.get("factions") if isinstance(state, Mapping) else None):
        fid = str(f.get("id") or "")
        try:
            skip = (not fid) or f.get("defeated") or is_secret(fid)
        except Exception:  # silent-ok: sem catálogo, nada é listado
            skip = True
        if skip:
            continue
        visible[fid] = fid
        lines.append(f"- id={fid} · {f.get('name')} ({f.get('region', '')}) · plano: você não sabe")
    body = "\n".join(lines) if lines else _EMPTY
    return FactionView(
        block=f"{body}\n{_INSTRUCTION}",
        visible=visible,
        counts={"listed": len(lines), "hidden_secret": 0, "goals": 0, "alias": 0},
    )


def npc_faction_view(state: Mapping, npc_key: str, row: Mapping, tier: str) -> FactionView:
    """R1-R8, R16-R18: o que o NPC lê sobre as fações do mundo. Falha fechada."""
    from observability.telemetry import log_event

    try:
        view = _build(state, npc_key, row, tier)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("npc", "faction_block_failed", exc)
        view = _public_fallback(state)
    log_event("npc", "faction_block", **dict(view.counts))
    return view


def resolve_proposed_id(view: FactionView, prompt_id: str) -> str:
    """R9: id do prompt (ou alias) -> faction_id real; "" se não estava no bloco."""
    from observability.telemetry import log_event

    real = view.visible.get(str(prompt_id or "").strip(), "")
    if not real and str(prompt_id or "").strip():
        log_event("npc", "faction_id_not_visible")
    return real


def cap_reveal(view: FactionView, fid: str, level: str, tier: str) -> str:
    """R10: depois do `clamp_reveal`. Só passa o que a linha do bloco autorizou."""
    if not level or fid in view.anon:
        return ""
    if fid not in view.goal_shown and level in ("objetivo", "progresso"):
        return "existencia"
    return level
