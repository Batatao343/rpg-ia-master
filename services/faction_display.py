"""SPEC-293 — rótulo de exibição de combatente de fação oculta (por observador).

O nome canônico de combatentes de fação carrega o nome da fação ("Iniciado da Chama
Azul"). Enquanto o jogador não conhece a fação (`faction_intel[fid].known`), toda
superfície player-facing mostra só o papel ("Iniciado"). O canônico segue interno
(save, ids, manifesto, prompts). O rótulo é derivado na LEITURA — nunca gravado —,
então a revelação (`apply_faction_reveal`) mostra o nome completo retroativamente.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

GENERIC_LABEL = "Combatente desconhecido"

_QUALIFIER = re.compile(r"\s+d(?:a|e|o|as|os)\s+|\s*\(", re.IGNORECASE)
_INSTANCE = re.compile(r"^(.*?)(\s+\d+)$")
_ID_KEY = re.compile(r"(?:^|_)ids?$")


def _faction_entry(faction_id: str, factions) -> dict | None:
    import gamedata

    for pool in (list(factions or []), gamedata.seed_factions()):
        for fac in pool:
            if isinstance(fac, dict) and fac.get("id") == faction_id:
                return fac
    return None


def display_label(name: str, faction_id: str, factions, intel) -> str:
    """R1: rótulo que o jogador vê para `name` (canônico) de um combatente de `faction_id`."""
    from world_utils import _theme_stems, concealed_faction

    name = str(name or "")
    match = _INSTANCE.match(name)
    base, suffix = (match.group(1), match.group(2)) if match else (name, "")
    entry = {"faction": faction_id, "name": base}
    if not base or not concealed_faction(entry, factions, intel):
        return name
    role = _QUALIFIER.split(base, maxsplit=1)[0].strip()
    if role and role != base:
        return role + suffix
    fac = _faction_entry(str(faction_id), factions) or {}
    fac_stems = _theme_stems(fac.get("name", ""))
    if fac_stems and fac_stems <= _theme_stems(base):
        return GENERIC_LABEL + suffix
    return name


def _concealed_entries(state: Mapping) -> dict[str, tuple[str, str]]:
    """{nome canônico: (rótulo, fid)} só onde o rótulo difere, para o observador `state`."""
    import gamedata

    factions = state.get("factions") or []
    intel = state.get("faction_intel") or {}
    pairs: list[tuple[str, str]] = []
    for entry in (gamedata.BESTIARY or {}).values():
        if isinstance(entry, dict) and entry.get("faction"):
            pairs.append((str(entry.get("name") or ""), str(entry["faction"])))
    for enemy in state.get("enemies") or []:
        if isinstance(enemy, dict):
            fid = enemy.get("faction_id") or enemy.get("faction")
            if fid:
                pairs.append((str(enemy.get("name") or ""), str(fid)))
    manifest = (state.get("combat") or {}).get("encounter") or {}
    for part in manifest.get("participants") or [] if isinstance(manifest, dict) else []:
        if isinstance(part, dict) and part.get("faction_id"):
            pairs.append((str(part.get("species_label") or ""), str(part["faction_id"])))
    out: dict[str, tuple[str, str]] = {}
    seen: set[str] = set()
    for name, fid in pairs:
        # instâncias numeradas ("X 2") são cobertas pelo nome-base (fronteira de palavra)
        match = _INSTANCE.match(name)
        base = match.group(1) if match else name
        if not base or base in seen:
            continue
        seen.add(base)
        label = display_label(base, fid, factions, intel)
        if label != base:
            out[base] = (label, fid)
    return out


def concealed_name_map(state: Mapping) -> dict[str, str]:
    """R2: {nome canônico: rótulo} só onde difere, para o observador `state`."""
    return {name: label for name, (label, _fid) in _concealed_entries(state).items()}


_VARIANTS = {
    "a": "aáàâãä",
    "e": "eéèêë",
    "i": "iíìîï",
    "o": "oóòôõö",
    "u": "uúùûü",
    "c": "cç",
    "n": "nñ",
}
_CONNECTORS = {"da", "de", "do", "das", "dos"}
_SEP = re.compile(r"[\s\-]+")


def _base_char(ch: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFD", ch)[:1].lower()


def _name_regex(name: str) -> str:
    """Revisão SPEC-293: tolera caixa, acento, espaço/quebra/hífen entre palavras e
    plural (`s`/`es`) das palavras de conteúdo — a prosa do LLM varia nesses eixos."""
    parts = []
    for word in _SEP.split(name.strip()):
        if not word:
            continue
        chars = "".join(
            f"[{_VARIANTS[b]}]" if (b := _base_char(ch)) in _VARIANTS else re.escape(ch)
            for ch in word
        )
        if word.casefold() not in _CONNECTORS and word[-1:].isalpha():
            chars += "(?:e?s)?"
        parts.append(chars)
    return r"[\s\-]+".join(parts)


def _pattern(mapping: Mapping[str, str]) -> re.Pattern | None:
    if not mapping:
        return None
    names = sorted(mapping, key=len, reverse=True)
    alts = "|".join(f"(?P<n{i}>{_name_regex(n)})" for i, n in enumerate(names))
    return re.compile(r"(?<!\w)(?:" + alts + r")(?!\w)", re.IGNORECASE)


def _pluralize(label: str, suffix: str) -> str:
    if not suffix:
        return label
    if label.startswith(GENERIC_LABEL):
        return "Combatentes desconhecidos" + label[len(GENERIC_LABEL) :]
    head, sep, tail = label.partition(" ")
    return head + suffix + sep + tail


def _replacer(mapping: Mapping[str, str]):
    names = sorted(mapping, key=len, reverse=True)

    def repl(match: re.Match) -> str:
        canon = names[int(str(match.lastgroup)[1:])]
        found = match.group(0)
        first_found = _SEP.split(found, maxsplit=1)[0]
        first_canon = _SEP.split(canon.strip(), maxsplit=1)[0]
        suffix = first_found[len(first_canon) :].lower()
        label = _pluralize(mapping[canon], suffix)
        if found[:1].islower():
            return label[:1].lower() + label[1:]
        return label

    return repl


def conceal_text(text: str, mapping: Mapping[str, str]) -> str:
    pattern = _pattern(mapping)
    if pattern is None or not isinstance(text, str):
        return text
    return pattern.sub(_replacer(mapping), text)


def conceal_payload(obj: Any, mapping: Mapping[str, str]) -> Any:
    """R3: cópia de `obj` com todo valor string projetado; chaves e campos de id intactos."""
    pattern = _pattern(mapping)
    if pattern is None:
        return obj
    repl = _replacer(mapping)

    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return pattern.sub(repl, value)
        if isinstance(value, Mapping):
            return {
                k: (v if isinstance(k, str) and _ID_KEY.search(k) else walk(v))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, tuple):
            return tuple(walk(v) for v in value)
        return value

    return walk(obj)


def conceal_for(state: Mapping, obj: Any) -> Any:
    return conceal_payload(obj, concealed_name_map(state))


def _fold(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _SEP.sub(" ", stripped.casefold()).strip()


def _oracle_regex(name: str) -> re.Pattern:
    r"""SPEC-294 R1: ocorrência de palavra inteira no texto dobrado (sem acento,
    casefold, `[\s-]+` → espaço) — mesma tolerância de `_name_regex` (plural
    `s`/`es` nas palavras de conteúdo), com fronteira `\w` como a projeção."""
    parts = []
    for word in _fold(name).split(" "):
        if not word:
            continue
        chunk = re.escape(word)
        if word not in _CONNECTORS and word[-1:].isalpha():
            chunk += "(?:e?s)?"
        parts.append(chunk)
    return re.compile(r"(?<!\w)" + " ".join(parts) + r"(?!\w)")


def concealed_name_problems(payload: Any, state: Mapping) -> list[str]:
    """Oráculo R6: nomes canônicos de fação desconhecida presentes em `payload`."""
    from services.player_knowledge import _text_of

    entries = _concealed_entries(state)
    if not entries:
        return []
    scan = _fold(_text_of(payload))
    return sorted(
        {
            f"e:concealed_faction_name:{fid}"
            for name, (_l, fid) in entries.items()
            if _oracle_regex(name).search(scan)
        }
    )
