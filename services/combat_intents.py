"""services/combat_intents.py - intencoes de combate por regex fechada (SPEC-325).

Funcoes puras, sem LLM: a intencao vem de regex ou nome canonico. Fase A expoe o
golpe nao-letal; Fase B (fuga) a abordagem, o abandono de companheiro e o aceite
do sacrificio. Fase C: uso de objeto de cena e ordem a companheiro.
"""

from __future__ import annotations

import re
import unicodedata

from services.death_flow import NONLETHAL_RE, nonlethal_declared  # noqa: F401

__all__ = [
    "NONLETHAL_RE",
    "abandon_target",
    "accepts_sacrifice",
    "chase_approach",
    "companion_order",
    "nonlethal_declared",
    "object_step",
]

_NEGATION = re.compile(r"\b(?:nao|nunca|jamais|sem|ninguem)\b")


def _fold(text: object) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in raw if not unicodedata.combining(c)).lower()


def _negated(folded: str, start: int) -> bool:
    """Negacao na mesma oracao, antes do trecho (janela curta, sem cruzar `,`/`;`/`.`)."""
    before = folded[max(0, start - 24) : start]
    clause = re.split(r"[,;.!?]", before)[-1]
    return bool(_NEGATION.search(clause))


# SPEC-325 R10: palavras-chave FECHADAS -> chave de `chase.APPROACH_VIRTUDE`.
_APPROACH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("correr", re.compile(r"\bcorr(?:o|er|endo|emos)\b")),
    ("desviar", re.compile(r"\bdesvi(?:o|ar|ando|amos)\b")),
    ("rotas", re.compile(r"\brotas?\b")),
    ("atalhos", re.compile(r"\batalhos?\b")),
    ("romper", re.compile(r"\b(?:rompo|romper|rompendo|rompemos)\b")),
    ("obstaculos", re.compile(r"\bobstaculos?\b")),
    ("resistencia", re.compile(r"\b(?:resistencia|resisto|resistir)\b")),
    ("prolongada", re.compile(r"\bprolongad[ao]\b")),
    ("coordenar", re.compile(r"\bcoorden(?:o|ar|amos)\b")),
    ("mobilizar", re.compile(r"\bmobiliz(?:o|ar|amos)\b")),
)


def chase_approach(text: str) -> str | None:
    """Abordagem da fuga declarada no texto (primeira palavra-chave nao negada), ou None."""
    folded = _fold(text)
    best: tuple[int, str] | None = None
    for key, rx in _APPROACH_PATTERNS:
        for m in rx.finditer(folded):
            if _negated(folded, m.start()):
                continue
            if best is None or m.start() < best[0]:
                best = (m.start(), key)
            break
    return best[1] if best else None


# SPEC-325 R12: "deixo/abandono <nome>" (so casa com candidatos reais).
_ABANDON_RE = re.compile(
    r"\b(?:deixo|deixamos|deixar|abandono|abandonamos|abandonar)\b\s+(?:(?:a|o|as|os)\s+)?"
    r"(?P<rest>[^.,;!?]*)"
)


def abandon_target(text: str, candidates: dict[str, str]) -> str | None:
    """Id do candidato abandonado pelo texto (`candidates` = id -> nome), ou None.

    Casa o nome inteiro ou o primeiro nome; negacao e falso positivo ("abandono o
    plano") nao casam porque so os candidatos existem no mapa."""
    if not candidates:
        return None
    folded = _fold(text)
    for m in _ABANDON_RE.finditer(folded):
        if _negated(folded, m.start()):
            continue
        rest = m.group("rest").strip()
        first_pass: list[tuple[str, str]] = [
            (cid, _fold(name).strip()) for cid, name in candidates.items()
        ]
        for cid, name in first_pass:  # nome inteiro primeiro
            if name and re.match(rf"{re.escape(name)}\b", rest):
                return cid
        for cid, name in first_pass:  # depois o primeiro nome
            token = name.split()[0] if name else ""
            if len(token) >= 3 and re.match(rf"{re.escape(token)}\b", rest):
                return cid
    return None


_ACCEPT_RE = re.compile(r"\baceit(?:o|ar|amos)\b")


def accepts_sacrifice(text: str) -> bool:
    """Aceite da oferta de sacrificio (so e consultado com oferta pendente)."""
    folded = _fold(text)
    return any(not _negated(folded, m.start()) for m in _ACCEPT_RE.finditer(folded))


# SPEC-325 R14: "<rotulo da interacao> <nome do objeto>" -> (object_id, label). So casa com
# objetos VISIVEIS (`visible` = saida de `conflict_scene.visible_objects`): objeto secreto
# ainda nao descoberto nunca aparece aqui, entao nao pode ser declarado.
def _word_start(folded: str, token: str) -> int:
    m = re.search(rf"\b{re.escape(token)}", folded)
    return m.start() if m else -1


def _label_matches(folded: str, label: str) -> bool:
    """Rotulo inteiro, ou o radical (verbo conjugado: "derrubar" ~ "derrubo")."""
    fl = _fold(label).strip()
    if not fl:
        return False
    if re.search(rf"\b{re.escape(fl)}\b", folded):
        return True
    stem = fl[: max(4, len(fl) - 2)]
    return len(fl) > 4 and _word_start(folded, stem) >= 0


def object_step(text: str, visible: list[dict]) -> tuple[str, str] | None:
    """`(object_id, interaction_label)` quando o texto traz o nome canonico de um objeto
    visivel E o rotulo de uma das suas interacoes (sem LLM); None caso contrario."""
    folded = _fold(text)
    if not folded or not visible:
        return None
    for obj in visible:
        name = _fold(obj.get("name")).strip()
        oid = obj.get("id")
        if not name or not oid:
            continue
        at = _word_start(folded, name)
        if at < 0 or _negated(folded, at):
            continue
        for it in obj.get("interactions") or []:
            label = str(it.get("label") or "")
            if label and _label_matches(folded, label):
                return str(oid), label
    return None


# SPEC-325 R15: "<aliado>, <verbo> [alvo]" (so no inicio de uma oracao).
_ORDER_RE = re.compile(
    r"^\s*(?P<name>[^,:]{2,40}?)\s*[,:]\s*(?P<neg>(?:nao|nunca)\s+)?(?P<verb>\w+)(?P<rest>.*)$"
)
_ORDER_VERBS: dict[str, str] = {
    "atacar": "atacar", "ataca": "atacar", "ataque": "atacar", "atacando": "atacar",
    "proteger": "proteger", "protege": "proteger", "proteja": "proteger",
    "recuar": "recuar", "recua": "recuar", "recue": "recuar",
    "curar": "curar", "cura": "curar", "cure": "curar",
}  # fmt: skip


def _match_name(rest: str, name: str) -> bool:
    n = _fold(name).strip()
    if not n:
        return False
    if re.match(rf"{re.escape(n)}\b", rest):
        return True
    token = n.split()[0]
    return len(token) >= 3 and bool(re.match(rf"{re.escape(token)}\b", rest))


def companion_order(text: str, allies: dict[str, str], enemies: list[dict]) -> dict | None:
    """`{ally_id, verb, target_id, tags}` para "<aliado>, <verbo> ..." (`allies` = id -> nome;
    `enemies` = fichas com id/name/status). None se nao ha ordem fechada valida. As tags saem
    do alvo e do verbo (`atacar_rendido`, `atacar_incapacitado`, `abandonar_posto`)."""
    if not allies:
        return None
    for clause in re.split(r"[.!?;]", _fold(text)):
        m = _ORDER_RE.match(clause)
        if not m or m.group("neg"):
            continue
        verb = _ORDER_VERBS.get(m.group("verb"))
        if verb is None:
            continue
        name = m.group("name").strip()
        ally_id = next((aid for aid, an in allies.items() if _match_name(name, an)), None)
        if ally_id is None:
            continue
        target_id: str | None = None
        tags: list[str] = []
        rest = m.group("rest").strip()
        if verb == "atacar":
            rest = re.sub(r"^(?:o|a|os|as|ao|aos|na|no)\s+", "", rest)
            for enemy in enemies or []:
                if (
                    _match_name(rest, str(enemy.get("name") or ""))
                    or _fold(enemy.get("id")).strip() == rest.split(" ")[0]
                ):
                    target_id = str(enemy.get("id"))
                    status = str(enemy.get("status") or "")
                    if enemy.get("surrendered") or status == "rendido":
                        tags.append("atacar_rendido")
                    if enemy.get("incapacitated") or status == "incapacitado":
                        tags.append("atacar_incapacitado")
                    break
        elif verb == "recuar":
            tags.append("abandonar_posto")
        return {"ally_id": ally_id, "verb": verb, "target_id": target_id, "tags": tags}
    return None
