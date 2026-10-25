"""SPEC-202 — política de interlocutor narrador × NPC.

Python puro: sem LLM, sem I/O de save. Decide, a partir do texto do jogador e do
estado, QUEM responde ao turno — o narrador ou um NPC presente — e publica um
`speaker` canônico. Regras (ordem fixa, ver spec §3):

1. marcadores de meta (narrador/mestre como vocativo ou alvo de verbo de fala,
   `(( ))`, "fora do jogo", OOC) ou "sobre <NPC>" sem verbo de fala → narrador;
2. pedidos de descrição de cena → narrador;
3. vocativo inicial / verbo de fala + alias / aspas + alias de NPC EM CENA → NPC;
4. alvo do CLASSIFY: só vira NPC se resolver para ficha existente em cena;
   conhecido fora de cena → resposta "não está aqui"; papel genérico só gera NPC
   em assentamento (P2); nome desconhecido → narrador explica a ausência.

O alvo cru do CLASSIFY NUNCA vira identidade nova (R5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Optional
from collections.abc import Mapping

from services.entity_identity import (
    find_runtime_npc_key,
    normalize_entity_label,
    normalize_runtime_npc_ref,
    resolve_npc_entity_id,
    runtime_npc_aliases,
)
from services.input_normalization import optional_entity_ref

SpeakerKind = Literal["narrator", "npc", "system"]
ReasonCode = Literal[
    "meta_to_narrator",
    "scene_description",
    "direct_address",
    "quoted_vocative",
    "single_in_scene",
    "continuity_last_speaker",
    "ambiguous_multi_mediated",
    "npc_absent_known",
    "npc_unknown_absent",
    "generic_role_spawn",
    "classify_story",
    "classify_fallback",
    "action_refused",
]

REASON_CODES: frozenset[str] = frozenset(ReasonCode.__args__)  # type: ignore[attr-defined]
# Motivos em que o narrador fala SOBRE um NPC (mediação, R11).
MEDIATION_REASONS = frozenset({"meta_to_narrator", "ambiguous_multi_mediated"})
# Motivos em que a rota NPC resulta em resposta do narrador (ninguém fala).
ABSENT_REASONS = frozenset({"npc_absent_known", "npc_unknown_absent"})

NARRATOR_ID = "narrator"
NARRATOR_NAME = "Narrador"
SYSTEM_ID = "system"
SYSTEM_NAME = "Sistema"

# P3: continuidade só vale se o último turno NPC foi há ≤ 2 ações.
CONTINUITY_WINDOW = 2
# Alias mínimo (R-matching): nunca casa 1–2 letras.
MIN_ALIAS_LEN = 3

# R6/P2: lista FECHADA de papéis genéricos (forma normalizada, sem acento).
GENERIC_ROLES: frozenset[str] = frozenset(
    {
        "taverneiro",
        "taverneira",
        "estalajadeiro",
        "estalajadeira",
        "guarda",
        "guardas",
        "mercador",
        "mercadora",
        "comerciante",
        "vendedor",
        "vendedora",
        "ferreiro",
        "ferreira",
        "sacerdote",
        "sacerdotisa",
        "barqueiro",
        "barqueira",
        "pescador",
        "pescadora",
        "marinheiro",
        "marinheira",
        "curandeiro",
        "curandeira",
        "boticario",
        "boticaria",
        "mendigo",
        "mendiga",
        "soldado",
        "bardo",
        "barda",
        "cocheiro",
        "estivador",
        "atendente",
        "carcereiro",
    }
)
# Tags de local que caracterizam assentamento (não-ermo).
_SETTLEMENT_TAGS = frozenset(
    {
        "cidade",
        "favela",
        "porto",
        "docas",
        "taverna",
        "salao",
        "urbano",
        "comercio",
    }
)
_SETTLEMENT_ECONOMY = frozenset({"comercio", "porto"})

# Tokens que não servem de apelido curto (adjetivos/títulos/artigos/papéis).
_STOP_TOKENS = (
    frozenset(
        {
            "o",
            "a",
            "os",
            "as",
            "de",
            "da",
            "do",
            "das",
            "dos",
            "e",
            "um",
            "uma",
            "velha",
            "velho",
            "jovem",
            "senhor",
            "senhora",
            "dona",
            "dom",
            "mestre",
            "mestra",
            "irmao",
            "irma",
            "padre",
            "madre",
            "capitao",
            "capita",
            "lorde",
            "lady",
            "sir",
            "rei",
            "rainha",
            "principe",
            "princesa",
            "anciao",
            "anciã",
            "narrador",
        }
    )
    | GENERIC_ROLES
)

_TALK_VERBS = (
    r"(?:pergunto|perguntamos|pergunta|digo|dizemos|falo|falamos|respondo|peco|"
    r"conto|explico|sussurro|grito|indago|questiono|converso|chamo|aceno|"
    r"cumprimento|ofereco|mostro|entrego|proponho)"
)
_TALK_RE = re.compile(rf"\b{_TALK_VERBS}\b")
_ARTICLES = r"(?:(?:o|a|os|as|um|uma)\s+)?"
_PREP = r"(?:a|ao|aos|as|para|pra|pro|com)"

_OOC_RE = re.compile(r"\(\(|\)\)")
_OOC_NORM_RE = re.compile(r"\b(?:fora do jogo|ooc|off game|offgame)\b")
_META_VOCATIVE_RE = re.compile(
    r"^\s*(?:(?:ei|oi|ola|olá|ó|o)\s+)?(?:narrador|mestre)\s*[,:!?]", re.IGNORECASE
)
# Astra: "mestre" seguido de nome/papel ("mestre Orlan", "mestre ferreiro",
# "mestre da guilda") é PERSONAGEM, não o mestre do jogo — só é meta no fim da
# frase ou antes de palavra funcional (o que / se / sobre / quem / ela ...).
_MESTRE_META = (
    r"mestre(?=\s*$|\s+(?:o|a|os|as|se|sobre|quem|como|por|porque|"
    r"qual|quais|onde|quando|que|e|ela|ele|eles|elas)\b)"
)
_META_VERB_RE = re.compile(rf"\b{_TALK_VERBS}\s+{_PREP}\s+{_ARTICLES}(?:narrador\b|{_MESTRE_META})")

_DESCRIPTION_RES = (
    re.compile(r"\bdescrev\w*\b"),
    re.compile(r"\bo que (?:eu )?(?:vejo|ouco|escuto|sinto|percebo|noto|enxergo)\b"),
    re.compile(
        r"\bquem (?:mais )?(?:esta|estao|ha|tem) (?:aqui|por perto|ao redor|"
        r"na sala|no local|na taverna|no salao)\b"
    ),
    re.compile(r"\b(?:olho|observo) (?:ao|em) (?:redor|volta)\b"),
)

_FILLERS_RE = re.compile(
    r"^\s*(?:(?:é|eh|ah|ahn|hm+|hum+|bem|entao|então|ok|tá|ta)\s*(?:\.\.\.|…|,|\s)\s*)+",
    re.IGNORECASE,
)
_HEAD_RE = re.compile(r"^\s*(.+?)\s*(?:\.\.\.|…|,|:|!|\?|—|–|\s-\s)")
_VOCATIVE_PREFIX = re.compile(r"^(?:ei|oi|ola|o|e ai|bom dia|boa tarde|boa noite)\s+")
_PRONOUN_ADDRESS_RE = re.compile(
    rf"(?:\b{_TALK_VERBS}\s+{_PREP}\s+(?:ela|ele)\b|^e (?:voce|tu|ela|ele)\b)"
)
_PRONOUN_TARGETS = frozenset(
    {
        "ela",
        "ele",
        "voce",
        "tu",
        "eles",
        "elas",
        "alguem",
        "pessoa",
        "npc",
        "narrador",
        "mestre",
        "o narrador",
        "o mestre",
    }
)
_QUOTE_RE = re.compile(r"[\"“”«»]")


@dataclass(frozen=True)
class InterlocutorResolution:
    route: str  # RouteType.value
    speaker_kind: SpeakerKind
    npc_state_key: str | None  # chave em state["npcs"]/party; só se npc ou absent_known
    mediated_subject_id: str | None  # NPC de quem o narrador fala (R2/R7/R8)
    reason: ReasonCode
    fallback_hint: str | None  # vira npc_fallback_hint quando npc_unknown_absent


# ---------------------------------------------------------------------------
# Helpers de identidade
# ---------------------------------------------------------------------------


def _norm(text: object) -> str:
    return normalize_entity_label(str(text or ""))


def _has_alias(norm_text: str, alias: str) -> bool:
    return len(alias) >= MIN_ALIAS_LEN and f" {alias} " in f" {norm_text} "


def _row_for(state: Mapping[str, Any], key: str) -> dict | None:
    npcs = state.get("npcs") or {}
    found = find_runtime_npc_key(npcs, key)
    if found is not None and isinstance(npcs.get(found), dict):
        return npcs[found]
    wanted = runtime_npc_aliases(key)
    for member in state.get("party") or []:
        if isinstance(member, dict) and wanted & runtime_npc_aliases(
            str(member.get("name") or ""), member
        ):
            return member
    return None


def _short_alias(row: Mapping[str, Any] | None, key: str) -> str | None:
    """Primeiro token significativo do nome (ex.: 'Velha Magda' → 'magda')."""
    name = str((row or {}).get("name") or key)
    for token in normalize_runtime_npc_ref(name).split():
        if len(token) >= MIN_ALIAS_LEN and token not in _STOP_TOKENS:
            return token
    return None


def _alias_map(state: Mapping[str, Any], keys: list[str]) -> dict[str, str | None]:
    """alias normalizado → chave; alias que casa ≥2 chaves vira None (ambíguo)."""
    out: dict[str, str | None] = {}

    def put(alias: str, key: str) -> None:
        if len(alias) < MIN_ALIAS_LEN or alias in _STOP_TOKENS:
            return
        if alias in out and out[alias] != key:
            out[alias] = None
        else:
            out[alias] = key

    for key in keys:
        row = _row_for(state, key)
        for alias in runtime_npc_aliases(key, row):
            put(alias, key)
        short = _short_alias(row, key)
        if short:
            put(short, key)
    return out


def scene_keys(state: Mapping[str, Any]) -> list[str]:
    from services import npc_layers

    return [
        normalized
        for name in npc_layers.npcs_in_scene(dict(state))
        if (normalized := optional_entity_ref(name)) is not None
    ]


def _known_keys(state: Mapping[str, Any]) -> list[str]:
    keys = [
        str(k)
        for k, v in (state.get("npcs") or {}).items()
        if isinstance(v, dict) and optional_entity_ref(k) is not None
    ]
    for member in state.get("party") or []:
        if isinstance(member, dict) and optional_entity_ref(member.get("name")):
            keys.append(str(member["name"]))
    return list(dict.fromkeys(keys))


def _mentions(norm_text: str, amap: Mapping[str, str | None]) -> list[str]:
    """Chaves citadas no texto, na ordem de aparição (alias mais longo vence)."""
    hits: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    padded = f" {norm_text} "
    for alias in sorted(amap, key=len, reverse=True):
        key = amap[alias]
        if key is None:
            continue
        start = padded.find(f" {alias} ")
        if start < 0:
            continue
        end = start + len(alias) + 2
        if any(start < e and s < end for s, e in taken):
            continue
        taken.append((start, end))
        hits.append((start, key))
    return list(dict.fromkeys(key for _pos, key in sorted(hits)))


def _match_target(tnorm: str, amap: Mapping[str, str | None]) -> str | None:
    if not tnorm:
        return None
    if tnorm in amap:
        return amap[tnorm]
    found = _mentions(tnorm, amap)
    return found[0] if len(found) == 1 else None


def canonical_npc_id(state: Mapping[str, Any], key: str) -> str:
    """R9/R10: id canônico estável (grafo → id da ficha → chave normalizada)."""
    row = _row_for(state, key) or {}
    name = str(row.get("name") or key)
    resolved = resolve_npc_entity_id(row, name)
    if resolved:
        return resolved
    explicit = optional_entity_ref(row.get("id"))
    if explicit:
        return str(explicit)
    slug = "_".join(normalize_runtime_npc_ref(name or key).split()) or "desconhecido"
    return f"npc_{slug}"


def canonical_npc_name(state: Mapping[str, Any], key: str) -> str:
    row = _row_for(state, key) or {}
    return str(row.get("name") or key)


def _strip_article(tnorm: str) -> str:
    return re.sub(r"^(?:o|a|os|as|um|uma)\s+", "", tnorm).strip()


def generic_role(tnorm: str) -> str | None:
    """Papel genérico da lista fechada (R6). Nome próprio nunca entra."""
    bare = _strip_article(tnorm)
    bare = re.sub(r"\s+(?:local|da taverna|do porto|do mercado|da cidade)$", "", bare)
    return bare if bare in GENERIC_ROLES else None


def is_settlement(state: Mapping[str, Any]) -> bool:
    """P2: assentamento = local com tag urbana ou economia de comércio/porto."""
    loc_id = str((state.get("world") or {}).get("current_location_id") or "")
    if not loc_id:
        return False
    import gamedata

    loc = gamedata.get_location(loc_id) or {}
    tags = {_norm(t) for t in loc.get("tags") or []}
    eco = {_norm(t) for t in loc.get("economy_tags") or []}
    return bool(tags & _SETTLEMENT_TAGS or eco & _SETTLEMENT_ECONOMY)


# ---------------------------------------------------------------------------
# Detecção léxica
# ---------------------------------------------------------------------------


def _is_meta_marker(text: str, norm: str) -> bool:
    return bool(
        _OOC_RE.search(text)
        or _OOC_NORM_RE.search(norm)
        or _META_VOCATIVE_RE.search(text)
        or _META_VERB_RE.search(norm)
    )


def _is_description(norm: str) -> bool:
    return any(rx.search(norm) for rx in _DESCRIPTION_RES)


def addressed_in_scene(state: Mapping[str, Any], text: str) -> tuple[str, str] | None:
    """(chave, motivo) quando o jogador se dirige EXPLICITAMENTE a um NPC em cena."""
    amap = _alias_map(state, scene_keys(state))
    if not any(amap.values()):
        return None
    head_text = _FILLERS_RE.sub("", text or "", count=1)
    head = _HEAD_RE.match(head_text)
    if head:
        hnorm = _VOCATIVE_PREFIX.sub("", _norm(head.group(1)))
        key = amap.get(hnorm)
        if key:
            return key, "direct_address"
    norm = _norm(text)
    for alias in sorted(amap, key=len, reverse=True):
        key = amap[alias]
        if key is None or len(alias) < MIN_ALIAS_LEN:
            continue
        if re.search(rf"\b{_TALK_VERBS}\s+{_PREP}\s+{_ARTICLES}{re.escape(alias)}\b", norm):
            return key, "direct_address"
    if _QUOTE_RE.search(text or ""):
        found = _mentions(norm, amap)
        if found:
            return found[0], "quoted_vocative"
    return None


def _continuity_key(state: Mapping[str, Any], in_scene: list[str]) -> str | None:
    last = state.get("last_speaker") or {}
    if not isinstance(last, Mapping):
        return None
    ref = last if last.get("kind") == "npc" else (last.get("last_npc") or {})
    if not isinstance(ref, Mapping) or not ref.get("state_key"):
        return None
    try:
        last_turn = int(ref.get("turn"))
    except (TypeError, ValueError):
        return None
    now = int((state.get("world") or {}).get("turn_count", 0) or 0)
    if now - last_turn > CONTINUITY_WINDOW or now < last_turn:
        return None
    wanted = runtime_npc_aliases(str(ref["state_key"]))
    if ref.get("name"):
        wanted |= runtime_npc_aliases(str(ref["name"]))
    for key in in_scene:
        if wanted & runtime_npc_aliases(key, _row_for(state, key)):
            return key
    return None


def _first_known_subject(state: Mapping[str, Any], norm: str) -> str | None:
    found = _mentions(norm, _alias_map(state, _known_keys(state)))
    return canonical_npc_id(state, found[0]) if found else None


def _resolution(
    route: str,
    kind: SpeakerKind,
    reason: str,
    *,
    key: str | None = None,
    subject: str | None = None,
    hint: str | None = None,
) -> InterlocutorResolution:
    return InterlocutorResolution(
        route=route,
        speaker_kind=kind,
        npc_state_key=key,
        mediated_subject_id=subject,
        reason=reason,  # type: ignore[arg-type]
        fallback_hint=hint,
    )


STORY = "storyteller"
NPC = "npc_actor"


def pre_classify(state: Mapping[str, Any], text: str) -> InterlocutorResolution | None:
    """R2/R3 determinísticos ANTES do CLASSIFY. None = seguir para o CLASSIFY."""
    text = str(text or "")
    if not text.strip():
        return None
    norm = _norm(text)
    if _is_meta_marker(text, norm):
        return _resolution(
            STORY, "narrator", "meta_to_narrator", subject=_first_known_subject(state, norm)
        )
    addressed = addressed_in_scene(state, text)
    if addressed is None and not _TALK_RE.search(norm):
        known = _alias_map(state, _known_keys(state))
        for alias in sorted(known, key=len, reverse=True):
            key = known[alias]
            if key and re.search(rf"\bsobre\s+{_ARTICLES}{re.escape(alias)}\b", norm):
                return _resolution(
                    STORY, "narrator", "meta_to_narrator", subject=canonical_npc_id(state, key)
                )
    if addressed is None and _is_description(norm):
        return _resolution(STORY, "narrator", "scene_description")
    return None


def deterministic_npc_resolution(key: str) -> InterlocutorResolution:
    """SPEC-317 R2: rota NPC para um NPC endereçado de forma inequívoca (sem CLASSIFY)."""
    return _resolution(NPC, "npc", "direct_address", key=key)


def _text_role_target(norm: str) -> str | None:
    match = re.search(rf"\b{_TALK_VERBS}\s+{_PREP}\s+{_ARTICLES}(\w+)", norm)
    if match and match.group(1) in GENERIC_ROLES:
        return match.group(1)
    return None


def post_classify(
    state: Mapping[str, Any], text: str, route: str, target: str | None
) -> InterlocutorResolution:
    """R3–R8 sobre a decisão do CLASSIFY (nenhuma chamada LLM)."""
    text = str(text or "")
    norm = _norm(text)
    addressed = addressed_in_scene(state, text)
    if route not in (STORY, NPC):
        return _resolution(route, "narrator", "classify_story")
    if addressed is None and _is_description(norm):
        return _resolution(STORY, "narrator", "scene_description")
    if addressed is not None:
        key, reason = addressed
        return _resolution(NPC, "npc", reason, key=key)
    if route == STORY and _PRONOUN_ADDRESS_RE.search(norm):
        # R8: "pergunto a ela" / "e você?" seguem a mesma regra da rota NPC sem alvo.
        route, target = NPC, None
    if route == STORY:
        return _resolution(STORY, "narrator", "classify_story")

    in_scene = scene_keys(state)
    scene_map = _alias_map(state, in_scene)

    def unknown() -> InterlocutorResolution:
        # R5(b): ninguém fala em 1ª pessoa. Sem NPC em cena mantém a rota NPC sem
        # alvo — o ator delega ao narrador (SPEC-041 R2, mesmo efeito final).
        if in_scene:
            return _resolution(STORY, "narrator", "npc_unknown_absent", hint=text)
        return _resolution(NPC, "narrator", "npc_unknown_absent", hint=text)

    # Nome de NPC em cena citado pelo PRÓPRIO jogador decide (o alvo do CLASSIFY
    # pode ser alucinado).
    cited = _mentions(norm, scene_map)
    if len(cited) == 1:
        return _resolution(NPC, "npc", "direct_address", key=cited[0])

    tnorm = _strip_article(_norm(optional_entity_ref(target) or ""))
    if tnorm in _PRONOUN_TARGETS or not _target_in_text(tnorm, norm):
        tnorm = ""  # alvo que o jogador não disse não é intenção dele (R5)
    if not tnorm:
        tnorm = _text_role_target(norm) or ""

    if tnorm:
        key = _match_target(tnorm, scene_map)
        if key:
            return _resolution(NPC, "npc", "direct_address", key=key)
        role = generic_role(tnorm)
        if role:
            for scene_key in in_scene:
                row = _row_for(state, scene_key) or {}
                if role in _norm(row.get("role")).split():
                    return _resolution(NPC, "npc", "direct_address", key=scene_key)
        absent = [k for k in _known_keys(state) if k not in in_scene]
        known = _match_target(tnorm, _alias_map(state, absent))
        if known:
            return _resolution(NPC, "narrator", "npc_absent_known", key=known)
        if role and is_settlement(state):
            # Nome exibido = papel DITO pelo jogador (nunca o alvo cru do CLASSIFY).
            display = role
            return _resolution(NPC, "npc", "generic_role_spawn", key=display)
        return unknown()

    absent = [k for k in _known_keys(state) if k not in in_scene]
    cited_absent = _mentions(norm, _alias_map(state, absent)) if _TALK_RE.search(norm) else []
    if cited_absent:
        return _resolution(NPC, "narrator", "npc_absent_known", key=cited_absent[0])

    continuity = _continuity_key(state, in_scene)
    if len(in_scene) == 1:
        reason = "continuity_last_speaker" if continuity == in_scene[0] else "single_in_scene"
        return _resolution(NPC, "npc", reason, key=in_scene[0])
    if len(in_scene) >= 2:
        if continuity:
            return _resolution(NPC, "npc", "continuity_last_speaker", key=continuity)
        return _resolution(STORY, "narrator", "ambiguous_multi_mediated")
    return unknown()


def _target_in_text(tnorm: str, norm: str) -> bool:
    """O alvo do CLASSIFY só conta se algum token significativo foi dito."""
    if not tnorm:
        return False
    if _has_alias(norm, tnorm):
        return True
    return any(
        _has_alias(norm, tok)
        for tok in tnorm.split()
        if tok not in _STOP_TOKENS or tok in GENERIC_ROLES
    )


# ---------------------------------------------------------------------------
# Speaker canônico (R9)
# ---------------------------------------------------------------------------


def narrator_speaker(reason: str | None = None) -> dict:
    code = reason if reason in REASON_CODES else "classify_story"
    return {"kind": "narrator", "id": NARRATOR_ID, "name": NARRATOR_NAME, "reason": code}


def system_speaker() -> dict:
    return {"kind": "system", "id": SYSTEM_ID, "name": SYSTEM_NAME, "reason": "action_refused"}


def public_speaker(speaker: Mapping[str, Any] | None) -> dict:
    """Projeção pública {kind,id,name,reason} (sem campos internos)."""
    if not isinstance(speaker, Mapping) or speaker.get("kind") not in ("narrator", "npc", "system"):
        return narrator_speaker()
    return {k: str(speaker.get(k) or "") for k in ("kind", "id", "name", "reason")}


def _action_refused(state: Mapping[str, Any]) -> bool:
    action = state.get("last_action_outcome") or {}
    return isinstance(action, Mapping) and action.get("allowed", True) is False


def _carry_last_npc(state: Mapping[str, Any]) -> dict | None:
    last = state.get("last_speaker") or {}
    if not isinstance(last, Mapping):
        return None
    if last.get("kind") == "npc" and last.get("state_key"):
        return {k: last.get(k) for k in ("id", "name", "state_key", "turn")}
    carried = last.get("last_npc")
    return dict(carried) if isinstance(carried, Mapping) else None


def speaker_for_turn(state: Mapping[str, Any]) -> dict:
    """R9: speaker do turno finalizado, com campos internos de continuidade.

    Campos públicos: kind/id/name/reason. Internos (só no save): `turn`,
    `state_key` (quando NPC) e `last_npc` (último NPC que falou, p/ R7/R8).
    """
    turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
    if _action_refused(state):
        speaker = system_speaker()
    else:
        reason = state.get("interlocutor_reason")
        key = optional_entity_ref(state.get("active_npc_name"))
        speaker = None
        if state.get("next") == NPC and key and reason not in ABSENT_REASONS:
            from services import npc_layers

            row = _row_for(state, key)
            if row is not None and npc_layers.npc_alive(row):
                speaker = {
                    "kind": "npc",
                    "id": canonical_npc_id(state, key),
                    "name": canonical_npc_name(state, key),
                    "reason": reason if reason in REASON_CODES else "direct_address",
                    "state_key": find_runtime_npc_key(state.get("npcs") or {}, key) or key,
                }
        if speaker is None:
            speaker = narrator_speaker(reason if isinstance(reason, str) else None)
    speaker["turn"] = turn
    if speaker["kind"] != "npc":
        carried = _carry_last_npc(state)
        if carried:
            speaker["last_npc"] = carried
    return speaker


def response_speaker(state: Mapping[str, Any]) -> dict:
    """Speaker público do estado atual (POST/SSE/state/history usam o MESMO)."""
    if _action_refused(state):
        return system_speaker()
    return public_speaker(state.get("last_speaker"))


def legacy_row_speaker(row: Mapping[str, Any]) -> dict:
    """Linha de histórico anterior à SPEC-202: rótulo derivado do `type`."""
    if str(row.get("type") or "") == "NPC":
        return {"speaker_kind": "npc", "speaker_id": "", "speaker_name": ""}
    return {"speaker_kind": "narrator", "speaker_id": NARRATOR_ID, "speaker_name": NARRATOR_NAME}
