"""services/prose_guard.py — anti-repetição de prosa (spec polish-prosa).

Funções PURAS (sem LLM) para o narrador: extrair a "abertura" de uma narração,
pegar as últimas aberturas do histórico (injetadas no prompt, R1), detectar
repetição (telemetria R4) e alimentar a invariante R5. Zero mecânica de jogo.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import List

_LOG = logging.getLogger("rpg.prose")

_META_NOUN = (
    r"(?:a\s+|o\s+|uma\s+|um\s+)?"
    r"(?:narrativa|resposta|descrição|texto|trecho|versão|cena)"
)

_META_PREAMBLE = re.compile(
    r"^\s*(?:#{1,6}\s*)?"
    rf"(?:aqui (?:está|vai|segue)\s+{_META_NOUN}[^:\n.!?]{{0,90}}[:.!?\n-]+|"
    rf"abaixo (?:você encontra|segue|está)\s+{_META_NOUN}[^:\n.!?]{{0,90}}[:.!?\n-]+|"
    r"como solicitado[^:\n.!?]{0,90}[:.!?\n-]+|"
    r"(?:narrativa|resposta|descrição)\s*[:\n-]+)",
    flags=re.IGNORECASE,
)

_ENGINE_MARKERS = re.compile(
    r"(?:\[\s*ECOS\s+DO\s+MUNDO\s*\]|\bContexto\s+do\s+local\s*:)",
    flags=re.IGNORECASE,
)

_ECHOED_IMPERATIVE = re.compile(
    r"(?:^|(?<=[.!?])\s+)(?:Descreva|Narre)\b[^.!?]*(?:[.!?]|$)\s*",
    flags=re.IGNORECASE,
)

_NEUTRAL_TRANSITIONS = (
    "A cena encontra outro compasso. ",
    "O momento avança sob nova tensão. ",
    "Por outro ângulo, a situação persiste. ",
    "A paisagem permanece, mas o instante muda. ",
    "O silêncio se rearranja ao seu redor. ",
    "Desta vez, o gesto ganha outro peso. ",
)


def opening(text: str, words: int = 6) -> str:
    """Primeiras `words` palavras normalizadas (minúsculas, sem pontuação) —
    a 'assinatura' de abertura de uma narração."""
    toks = re.findall(r"\w+", (text or "").lower())
    return " ".join(toks[:words])


_NPC_SCAFFOLD = re.compile(
    r"^\s*(?:🗣️?\s*)?[^:\n]{1,80}:\s*",
    flags=re.IGNORECASE,
)


def semantic_opening(text: str, words: int = 6) -> str:
    """Opening without the deterministic speaker label used by NPC messages."""
    value = _NPC_SCAFFOLD.sub("", str(text or ""), count=1).lstrip('* "“')
    while True:
        prefix = next((p for p in _NEUTRAL_TRANSITIONS if value.startswith(p)), None)
        if prefix is None:
            break
        value = value[len(prefix) :].lstrip('* "“')
    return opening(value, words)


def is_deterministic_interaction_message(text: str) -> bool:
    value = str(text or "")
    return bool(
        _NPC_SCAFFOLD.match(value)
        and re.search(
            r"\b(?:recusa|não está aqui|já está no grupo|grupo já está cheio)\b",
            value,
            re.IGNORECASE,
        )
    )


def sanitize_meta_preamble(text: str) -> str:
    """Remove moldura de assistente no início, preservando a prosa do jogo."""
    cleaned = str(text or "").strip()
    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = _META_PREAMBLE.sub("", cleaned, count=1).lstrip(" \t\r\n—-:")
    return cleaned.strip()


def sanitize_player_facing(text: str) -> str:
    """Fecha a fronteira motor→jogador sem reescrever conteúdo livre.

    Remove somente o vocabulário fechado usado nas notas internas do motor e
    imperativos de prompt que alguns providers ecoam literalmente.
    """
    cleaned = sanitize_meta_preamble(text)
    cleaned = _ENGINE_MARKERS.sub("", cleaned)
    cleaned = _ECHOED_IMPERATIVE.sub(" ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r"\s+([,.;!?])", r"\1", cleaned)
    return cleaned.strip()


_OUTER_QUOTES = (('"', '"'), ("“", "”"), ("‘", "’"))


def strip_outer_quotes(text: str) -> str:
    """Remove apenas aspas que envolvem a resposta inteira do provider.

    O renderer de NPC já adiciona suas próprias aspas. Sem esta fronteira, uma
    resposta estruturada que venha como ``"fala"`` aparece como ``""fala""``.
    Aspas internas e apóstrofos permanecem intactos.
    """
    value = str(text or "").strip()
    previous = None
    while value and value != previous:
        previous = value
        for opening_quote, closing_quote in _OUTER_QUOTES:
            if (
                len(value) >= 2
                and value.startswith(opening_quote)
                and value.endswith(closing_quote)
            ):
                value = value[len(opening_quote) : -len(closing_quote)].strip()
                break
    return value


_PROTAGONIST_THIRD_PERSON = re.compile(
    r"\b(?:O jogador|O personagem|O herói)\b",
    flags=re.IGNORECASE,
)


def normalize_protagonist_voice(text: str) -> str:
    """Converte somente o sujeito fechado do protagonista para segunda pessoa.

    SPEC-346 R22: "Você" só no início de frase (início do texto ou depois de `.!?`/quebra);
    no meio da frase, "você"."""
    value = str(text or "")

    def _repl(match: re.Match[str]) -> str:
        before = value[: match.start()]
        starts_sentence = not before.strip() or bool(re.search(r"[.!?:]\s*$|\n\s*$", before))
        return "Você" if starts_sentence else "você"

    return _PROTAGONIST_THIRD_PERSON.sub(_repl, value)


# --- SPEC-346 R13: pós-filtro de números/aritmética no resumo final do combate ----------
_NUM_WORDS = (
    "um|uma|dois|duas|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|"
    "quatorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte"
)
_N = rf"(?:\d+|{_NUM_WORDS})"
_STRIP_PARENS = re.compile(r"\s*\([^()]*(?:\d|→|->)[^()]*\)")
_STRIP_VS = re.compile(
    rf"(?:\b\w+\s+de\s+)?\b{_N}\s+(?:contra|vs\.?)\s+(?:a\s+)?(?:esquiva\s+(?:de\s+)?)?{_N}\b",
    re.IGNORECASE,
)
_STRIP_UNITS = re.compile(
    rf"\b{_N}\s+(?:pontos?\s+)?(?:de\s+)?(?:vitalidade|vigor|dano|f[ôo]lego|esquiva|prote[cç][aã]o)s?\b",
    re.IGNORECASE,
)


def strip_mechanic_numbers(text: str) -> tuple[str, int]:
    """Remove aritmética que escapou da prosa: parênteses com dígitos/setas, "N contra M" e
    "N (pontos de) vitalidade/vigor/dano/fôlego/esquiva/proteção". Normaliza U+00AD/U+2011.

    Devolve ``(texto, remoções)``; sem espaço duplo nem pontuação órfã."""
    value = str(text or "").replace("­", "").replace("‑", "-")
    removed = 0
    for rx in (_STRIP_PARENS, _STRIP_VS, _STRIP_UNITS):
        value, n = rx.subn("", value)
        removed += n
    if removed:
        value = re.sub(r"[ \t]{2,}", " ", value)
        value = re.sub(r"\s+([,.;!?])", r"\1", value)
        value = re.sub(r"([,;])(\s*[,;])+", r"\1", value)
        value = re.sub(r"[,;]\s*([.!?])", r"\1", value)
        value = re.sub(r"\s+\n", "\n", value)
        value = re.sub(r"([.!?])\s*\.", r"\1", value)
    return value.strip(), removed


_PLAYER_GOLD_PATTERNS = (
    re.compile(
        r"(?i)(\b(?:voc[eê]\s+)?(?:possui|tem|carrega|restam|sobram)\s+)"
        r"\d+(\s+moedas?\s+de\s+ouro\b)"
    ),
    re.compile(r"(?i)(\b(?:ouro\s+total|saldo)\s*:\s*)\d+\b"),
    re.compile(
        r"(?i)\b\d+(?=\s+moedas?\s+de\s+ouro\s+(?:pesando\s+)?"
        r"(?:(?:na|em sua)\s+bolsa|no\s+fundo\s+da\s+bolsa|"
        r"(?:no|em seu)\s+(?:cinto|bolso))\b)"
    ),
)


def reconcile_player_gold_claims(text: str, gold: int) -> str:
    """Corrige somente alegações inequívocas sobre o saldo do protagonista."""
    value = str(text or "")
    canonical = str(max(0, int(gold or 0)))
    value = _PLAYER_GOLD_PATTERNS[0].sub(
        lambda match: f"{match.group(1)}{canonical}{match.group(2)}", value
    )
    value = _PLAYER_GOLD_PATTERNS[1].sub(lambda match: f"{match.group(1)}{canonical}", value)
    return _PLAYER_GOLD_PATTERNS[2].sub(canonical, value)


def contains_engine_marker(text: str) -> bool:
    """True quando uma narração visível ainda contém marcador interno."""
    return bool(_ENGINE_MARKERS.search(str(text or "")))


def vary_repeated_opening(text: str, recent_openings: list[str], *, salt: str = "") -> str:
    """Quebra abertura literalmente repetida com transição neutra e estável.

    A transformação é conservadora: só atua quando seis palavras iniciais são
    iguais às de uma abertura recente, e nunca chama o LLM novamente.
    """
    value = str(text or "").strip()
    recent = [str(item or "").strip() for item in recent_openings if str(item or "").strip()]
    if not value or not any(repeats(value, item) for item in recent):
        return value
    # SPEC-319: o digest so olha a abertura (nao o texto inteiro), para o stream escolher a
    # MESMA transicao que o texto final assim que as primeiras palavras chegam.
    digest = hashlib.sha256(f"{salt}|{opening(value)}".encode()).digest()
    start = int.from_bytes(digest[:2], "big") % len(_NEUTRAL_TRANSITIONS)
    for offset in range(len(_NEUTRAL_TRANSITIONS)):
        prefix = _NEUTRAL_TRANSITIONS[(start + offset) % len(_NEUTRAL_TRANSITIONS)]
        candidate = prefix + value
        if not any(repeats(candidate, item) for item in recent):
            return candidate
    return _NEUTRAL_TRANSITIONS[start] + value


def remove_rejected_claims(text: str, rejected_terms: list[str]) -> str:
    """Remove frases que afirmam um item/evento rejeitado pelo motor.

    A comparação é literal e case-insensitive; não tenta inferir semântica.
    """
    terms = [str(term).strip().casefold() for term in rejected_terms if str(term).strip()]
    if not terms:
        return str(text or "")
    value = str(text or "")
    # Quantias aparecem com frequência em algarismo no structured output e por
    # extenso na prosa ("15" vs. "quinze"). Se o motor rejeitou uma aquisição
    # monetária, descarta o parágrafo inteiro que menciona ouro/moedas para não
    # deixar frases anafóricas como "você guarda a bolsa" sobreviverem.
    if any("ouro" in term or "moeda" in term for term in terms):
        paragraphs = re.split(r"\n\s*\n", value)
        value = "\n\n".join(
            paragraph
            for paragraph in paragraphs
            if not re.search(r"\b(?:ouro|moedas?)\b", paragraph, re.IGNORECASE)
        )
    chunks = re.split(r"(?<=[.!?])(\s+)", value)
    kept: list[str] = []
    for index in range(0, len(chunks), 2):
        sentence = chunks[index]
        separator = chunks[index + 1] if index + 1 < len(chunks) else ""
        lowered = sentence.casefold()
        if not any(term in lowered for term in terms):
            kept.extend((sentence, separator))
    return "".join(kept).strip()


def ultimas_aberturas(messages, n: int = 2, words: int = 12) -> list[str]:
    """As `n` últimas aberturas de narração (mensagens não-humanas) do histórico,
    com ~`words` palavras cada — para o prompt pedir variação (R1)."""
    out: list[str] = []
    for m in reversed(messages or []):
        content = getattr(m, "content", "")
        if content and getattr(m, "type", "") != "human":
            ab = opening(str(content), words)
            if ab:
                out.append(ab)
            if len(out) >= n:
                break
    return out


def repeats(a: str, b: str, words: int = 6) -> bool:
    """True se `a` e `b` começam com as mesmas `words` palavras (não-vazias)."""
    oa = opening(a, words)
    return bool(oa) and oa == opening(b, words)


def openings_clause(aberturas: list[str]) -> str:
    """Cláusula de prompt (R1): pede para NÃO repetir a estrutura/imagem das
    aberturas recentes. Vazio se não há histórico."""
    if not aberturas:
        return ""
    listadas = " | ".join(f'"{a}…"' for a in aberturas)
    return (
        "\n    - VARIE A ABERTURA: as últimas narrações começaram assim: "
        f"{listadas}. NÃO comece com estrutura ou imagem parecida; abra diferente."
    )


def log_if_repeats(new_text: str, prev_text: str, *, where: str = "prose") -> bool:
    """R4: telemetria (não pune) — loga warning se a abertura repete a anterior."""
    if repeats(new_text, prev_text):
        # SPEC-222 R2/PRIV-09: nunca o trecho da narração (pode conter nomes do jogador).
        digest = hashlib.sha256(opening(new_text).encode("utf-8")).hexdigest()[:12]
        _LOG.warning("Abertura repetida (%s): opening_sha=%s", where, digest)
        return True
    return False


# ---------------------------------------------------------------------------
# SPEC-203 R9 — prosa ancorada no manifesto do encontro
# ---------------------------------------------------------------------------
# Cabeças de nome de bestiário que são títulos/ofícios comuns (não espécie).
_NON_SPECIES_HEADS = {
    "capitao",
    "guarda",
    "senhor",
    "senhora",
    "mestre",
    "rei",
    "rainha",
    "soldado",
    "lider",
    "chefe",
    "sacerdote",
    "cavaleiro",
    "guardiao",
    "filho",
    "filha",
    "mae",
    "pai",
    "irma",
    "irmao",
    "velho",
    "velha",
    "sombra",
    "voz",
    "eco",
    "coisa",
    "algo",
    # Revisão Astra: palavras comuns de prosa de combate (substantivo
    # não-criatura, verbo flexionado ou ofício genérico) que
    # derrubavam narração legítima ("uma faísca salta", "vinha").
    "fumaca",
    "faisca",
    "vinha",
    "horror",
    "eclipse",
    "vigia",
    "sentinela",
    "general",
    "lorde",
    "guerreiro",
    "cacador",
    "predador",
    "observador",
    "devorador",
    "iniciado",
    "nomade",
    "filhote",
    "larva",
    "elemental",
    "colosso",
    "renegado",
    "saqueador",
    "capanga",
    "assassino",
    "cobrador",
    "capturador",
}


def _species_heads() -> dict:
    """{token-cabeça normalizado: nome} de cada espécie do bestiário curado."""
    import gamedata
    from services.encounter_manifest import name_tokens

    heads: dict = {}
    for entry in (gamedata.BESTIARY or {}).values():
        tokens = name_tokens(entry.get("name", ""))
        if tokens and len(tokens[0]) >= 4 and tokens[0] not in _NON_SPECIES_HEADS:
            heads.setdefault(tokens[0], entry.get("name", ""))
    return heads


def species_drift(text: str, manifest: dict | None) -> list:
    """Marca prosa que atribui ao encontro uma espécie fora do manifesto: menciona
    espécie do bestiário ausente do elenco E não menciona nenhuma espécie canônica.
    Não reescreve estado; o chamador decide neutralizar (texto determinístico)."""
    from services.encounter_manifest import name_tokens

    participants = (manifest or {}).get("participants") or []
    if not text or not participants:
        return []
    canonical = set()
    for p in participants:
        canonical.update(name_tokens(p.get("species_label", "")))
    prose_tokens = name_tokens(text)
    if canonical & set(prose_tokens):
        return []
    heads = _species_heads()
    flags, seen = [], set()
    for tok in prose_tokens:
        if tok in heads and tok not in canonical and tok not in seen:
            seen.add(tok)
            flags.append(
                {
                    "species": tok,
                    "bestiary_name": heads[tok],
                    "canonical": sorted({p.get("species_label", "") for p in participants}),
                }
            )
    return flags


def log_species_drift(flags: list, *, where: str = "combate") -> None:
    if flags:
        _LOG.warning("species_drift where=%s species=%s", where, [f.get("species") for f in flags])


# --------------------------------------------------------------------------
# SPEC-353 R17: contagem da narração de entrada x manifesto do encontro
# --------------------------------------------------------------------------
_NUM_WORDS = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
}
_NUM_BY_VALUE = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete"}


def count_drift(text: str, manifest: dict | None) -> list[dict]:
    """Numeral ligado ao nome de uma espécie do manifesto, maior que o N ATIVO dela
    ("três bandidos" com 2 no tabuleiro). Só marca; quem chama decide reconciliar."""
    from services.encounter_manifest import _fold, name_tokens

    participants = (manifest or {}).get("participants") or []
    if not text or not participants:
        return []
    active: dict[str, int] = {}
    for p in participants:
        if p.get("status", "ativo") == "ativo":
            label = str(p.get("species_label") or "")
            active[label] = active.get(label, 0) + 1
    flags: list[dict] = []
    folded = _fold(text)
    for label, n in active.items():
        tokens = name_tokens(label)
        if not tokens:
            continue
        stem = tokens[0][: max(4, len(tokens[0]) - 2)]
        rx_num = r"(\d+|" + "|".join(_NUM_WORDS) + r")"
        for m in re.finditer(rx_num + r"\s+(?:[a-z]+\s+){0,2}?" + re.escape(stem), folded):
            raw = m.group(1)
            claimed = int(raw) if raw.isdigit() else _NUM_WORDS.get(raw, 0)
            if claimed > n:
                flags.append({"species": label, "claimed": claimed, "active": n})
                break
    return flags


def reconcile_count_sentence(flags: list[dict]) -> str:
    """Frase determinística que corrige a contagem: "Só dois Bandidos avançam contra você..."."""
    if not flags:
        return ""
    parts = []
    for f in flags:
        n = int(f["active"])
        word = _NUM_BY_VALUE.get(n, str(n))
        label = str(f["species"])
        if n == 1:
            parts.append(f"Só {word} {label} avança")
        else:
            parts.append(f"Só {word} {label}s avançam")
    return " ".join(p + " contra você; o resto some na sombra." for p in parts[:1])
