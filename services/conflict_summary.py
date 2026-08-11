"""services/conflict_summary.py — resumo canônico pós-conflito (spec conflito-12).

Contrato ÚNICO entre o motor determinístico e a LLM: depois que combate,
perseguição e loot resolvem 100% SEM LLM, `build_summary` monta o `ConflictSummary`
(fatos canônicos, não detalhes mecânicos brutos) que a narrativa retoma — sem poder
reverter nenhum fato (R3). `economy.roll_loot` NÃO muda (risco §7): `loot_context`
só decide o que passar como `danger` (Nível do Encontro em vez de `danger_level`).

ADITIVO: módulo novo + testes. O consumo em `agents/loot.py`/`agents/archivist.py`
é o cutover (conflito-13).
"""
import hashlib
import json
import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ConflictSummary(BaseModel):
    conflict_id: str = ""
    conflict_turn: Optional[int] = None
    participantes: List[str] = Field(default_factory=list)
    sobreviventes: List[str] = Field(default_factory=list)
    mortos: List[str] = Field(default_factory=list)
    inconscientes: List[str] = Field(default_factory=list)
    rendidos: List[str] = Field(default_factory=list)
    fugitivos: List[str] = Field(default_factory=list)
    capturados: List[str] = Field(default_factory=list)
    ferimentos: Dict[str, List[Dict]] = Field(default_factory=dict)
    cicatrizes_a_gerar: List[str] = Field(default_factory=list)
    recursos_gastos: Dict[str, int] = Field(default_factory=dict)
    cartas_descobertas: List[str] = Field(default_factory=list)
    resistencias_descobertas: List[str] = Field(default_factory=list)
    objetos_utilizados: List[str] = Field(default_factory=list)
    mudancas_permanentes_cenario: List[str] = Field(default_factory=list)
    companheiros_separados: List[Dict] = Field(default_factory=list)
    decisoes_morais: List[str] = Field(default_factory=list)
    fatos_de_relacao: List[str] = Field(default_factory=list)
    loot_obtido: List[Dict] = Field(default_factory=list)
    estado_final_party: Dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ensure_identity(self):
        if not str(self.conflict_id or "").strip():
            self.conflict_id = ensure_conflict_id(
                self.model_dump(), turn=self.conflict_turn,
            )
        return self


CONSUMED_CONFLICT_IDS_LIMIT = 64


def ensure_conflict_id(summary: dict, *, turn: Optional[int] = None) -> str:
    """Retorna o ID existente ou deriva um fallback estável do conteúdo.

    O fallback é somente rede de segurança para produtores antigos. O produtor
    deve preferir `extras.conflict_id` e `extras.turn`, evitando que dois
    conflitos materialmente idênticos compartilhem identidade.
    """
    existing = str((summary or {}).get("conflict_id") or "").strip()
    if existing:
        return existing
    turn_hint = turn
    if turn_hint is None:
        raw_turn = (summary or {}).get("conflict_turn")
        try:
            turn_hint = int(raw_turn) if raw_turn is not None else None
        except (TypeError, ValueError):
            turn_hint = None
    payload = dict(summary or {})
    payload.pop("conflict_id", None)
    payload["conflict_turn"] = turn_hint
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:16]
    turn_part = f"-t{turn_hint}" if turn_hint is not None else ""
    return f"conflict{turn_part}-{digest}"


def normalize_consumed_conflict_ids(values) -> List[str]:
    """Normaliza o ledger persistente, preservando ordem e o limite mais novo."""
    out: List[str] = []
    for value in values or []:
        conflict_id = str(value or "").strip()
        if conflict_id and conflict_id not in out:
            out.append(conflict_id)
    return out[-CONSUMED_CONFLICT_IDS_LIMIT:]


def append_consumed_conflict_id(values, conflict_id: str) -> List[str]:
    ledger = normalize_consumed_conflict_ids(values)
    normalized = str(conflict_id or "").strip()
    if not normalized or normalized in ledger:
        return ledger
    return (ledger + [normalized])[-CONSUMED_CONFLICT_IDS_LIMIT:]


def _pid(p: dict) -> str:
    return p.get("name") or p.get("id") or "?"


def _flatten_wounds(p: dict) -> List[dict]:
    fer = p.get("ferimentos") or {}
    out = []
    for cat in ("critico", "grave", "leve"):
        out.extend(fer.get(cat, []) or [])
    return out


# ==========================================================================
# Etapa 1 — build_summary (R2/R4)
# ==========================================================================
def build_summary(participants: List[dict], *, scene: Optional[dict] = None,
                  chase_state: Optional[dict] = None,
                  death_outcomes: Optional[List[dict]] = None,
                  loot_result: Optional[List[dict]] = None,
                  resources_spent: Optional[Dict[str, int]] = None,
                  extras: Optional[dict] = None) -> dict:
    """R2/R4: monta o resumo canônico a partir do estado FINAL já resolvido (sem
    LLM). `participants` traz o estado de cada um (dead/conscious/surrendered/fled/
    captured/incapacitated/ferimentos/scar_pending). `extras` cobre os campos
    livres (decisões morais, fatos de relação, mudanças de cenário, party final)."""
    participants = participants or []
    extras = extras or {}
    raw_turn = extras.get("turn", extras.get("conflict_turn"))
    try:
        conflict_turn = int(raw_turn) if raw_turn is not None else None
    except (TypeError, ValueError):
        conflict_turn = None
    explicit_id = str(
        extras.get("conflict_id") or extras.get("id") or ""
    ).strip()

    mortos = [_pid(p) for p in participants if p.get("dead")]
    fugitivos = [_pid(p) for p in participants if p.get("fled")]
    if chase_state and chase_state.get("escapou") and chase_state.get("fugitive_id"):
        fid = chase_state["fugitive_id"]
        if fid not in fugitivos:
            fugitivos.append(fid)

    cartas = list(extras.get("cartas_descobertas") or [])
    resist = list(extras.get("resistencias_descobertas") or [])
    objetos_usados = list(extras.get("objetos_utilizados") or [])
    if scene:
        for e in (scene.get("enemies") or []):
            cartas += [c for c in (e.get("revealed_cards") or []) if c not in cartas]
            resist += [r for r in (e.get("revealed_resistances") or []) if r not in resist]
        for o in (scene.get("objects") or []):
            if o.get("destroyed"):
                nome = o.get("name") or o.get("id")
                if nome and nome not in objetos_usados:
                    objetos_usados.append(nome)

    fatos_rel = list(extras.get("fatos_de_relacao") or [])
    for out in (death_outcomes or []):
        fatos_rel += [f for f in (out.get("fatos_relacionais") or []) if f not in fatos_rel]

    summary = ConflictSummary(
        conflict_id=explicit_id,
        conflict_turn=conflict_turn,
        participantes=[_pid(p) for p in participants],
        sobreviventes=[_pid(p) for p in participants if not p.get("dead")],
        mortos=mortos,
        inconscientes=[_pid(p) for p in participants
                       if not p.get("dead") and (not p.get("conscious", True) or p.get("incapacitated"))],
        rendidos=[_pid(p) for p in participants if p.get("surrendered")],
        fugitivos=fugitivos,
        capturados=[_pid(p) for p in participants if p.get("captured")],
        ferimentos={_pid(p): _flatten_wounds(p) for p in participants if _flatten_wounds(p)},
        cicatrizes_a_gerar=[_pid(p) for p in participants if p.get("scar_pending")],
        recursos_gastos=dict(resources_spent or {}),
        cartas_descobertas=cartas,
        resistencias_descobertas=resist,
        objetos_utilizados=objetos_usados,
        mudancas_permanentes_cenario=list(extras.get("mudancas_permanentes_cenario") or []),
        companheiros_separados=list(extras.get("companheiros_separados") or []),
        decisoes_morais=list(extras.get("decisoes_morais") or []),
        fatos_de_relacao=fatos_rel,
        loot_obtido=list(loot_result or []),
        estado_final_party=dict(extras.get("estado_final_party") or {}),
    )
    data = summary.model_dump()
    data["conflict_id"] = ensure_conflict_id(data, turn=conflict_turn)
    return data


# ==========================================================================
# Etapa 2 — integração de loot (R1) — reaproveita economy.roll_loot como está
# ==========================================================================
def loot_context(summary: dict, *, region_id: str = "default",
                 encounter_level: Optional[int] = None, danger_level: int = 1) -> dict:
    """R1: parâmetros pro loot a partir do resultado do conflito. A raridade passa
    a refletir o Nível do Encontro (`conflito-11`) quando disponível, no lugar do
    `danger_level` bruto — MAS `economy.roll_loot(region_id, danger, ...)` fica
    intacta: só muda o número que entra em `danger`."""
    danger = int(encounter_level) if encounter_level is not None else int(danger_level or 1)
    return {"loot_source": "TREASURE", "region_id": region_id, "danger": danger,
            "mortos": list(summary.get("mortos") or [])}


# ==========================================================================
# Etapa 3 — entrega à narrativa: contrato de não-reversão (R3) + fatos p/ archivist
# ==========================================================================
def validate_narrative_consistency(summary: dict, proposed: dict) -> dict:
    """R3: a narrativa só continua A PARTIR dos fatos — não pode reverter
    morte→fuga, libertar capturado ou restaurar cenário destruído SEM um novo
    acontecimento posterior explícito (`proposed['novo_acontecimento']`). Retorna
    {ok, violations}."""
    violations: List[str] = []
    novo = bool(proposed.get("novo_acontecimento"))
    mortos = set(summary.get("mortos") or [])
    capturados = set(summary.get("capturados") or [])

    for nome in proposed.get("vivos") or []:
        if nome in mortos:
            violations.append(f"'{nome}' está morto no resumo — narrativa não pode revivê-lo.")
    for nome in proposed.get("libertados") or []:
        if nome in capturados and not novo:
            violations.append(f"'{nome}' foi capturado — não pode ser libertado sem novo acontecimento.")
    for cenario in proposed.get("cenario_restaurado") or []:
        if cenario in set(summary.get("mudancas_permanentes_cenario") or []) and not novo:
            violations.append(f"Mudança de cenário '{cenario}' é permanente — não pode ser restaurada.")
    return {"ok": not violations, "violations": violations}


def summary_facts(summary: dict) -> List[str]:
    """Fatos canônicos a persistir na memória (archivist): mortes, rendições,
    capturas, fugas, Cicatrizes, mudanças de cenário e fatos de relação."""
    facts: List[str] = []
    for nome in summary.get("mortos") or []:
        facts.append(f"{nome} morreu no conflito.")
    for nome in summary.get("rendidos") or []:
        facts.append(f"{nome} se rendeu.")
    for nome in summary.get("capturados") or []:
        facts.append(f"{nome} foi capturado.")
    for nome in summary.get("fugitivos") or []:
        facts.append(f"{nome} fugiu.")
    for nome in summary.get("cicatrizes_a_gerar") or []:
        facts.append(f"{nome} carregará uma Cicatriz deste conflito.")
    facts.extend(summary.get("mudancas_permanentes_cenario") or [])
    facts.extend(summary.get("fatos_de_relacao") or [])
    for loot in summary.get("loot_obtido") or []:
        if not isinstance(loot, dict):
            continue
        if loot.get("kind") == "gold" and int(loot.get("amount", 0) or 0):
            facts.append(f"O grupo obteve {int(loot['amount'])} de ouro no conflito.")
        elif loot.get("kind") == "item" and loot.get("item_id"):
            qty = max(1, int(loot.get("qty", 1) or 1))
            facts.append(f"O grupo obteve {qty}x {loot['item_id']} no conflito.")
    return facts


def canonical_summary_text(summary: dict) -> str:
    """Representação curta, determinística e própria para prompt/crônica."""
    clauses: List[str] = []
    mapping = (
        ("mortos", "Mortos"),
        ("rendidos", "Rendidos"),
        ("capturados", "Capturados"),
        ("fugitivos", "Fugitivos"),
        ("inconscientes", "Inconscientes"),
    )
    for field, label in mapping:
        values = [str(value) for value in summary.get(field) or [] if str(value).strip()]
        if values:
            clauses.append(f"{label}: {', '.join(values)}.")
    loot = summary.get("loot_obtido") or []
    if loot:
        rendered = []
        for entry in loot:
            if not isinstance(entry, dict):
                continue
            if entry.get("kind") == "gold":
                rendered.append(f"{int(entry.get('amount', 0) or 0)} ouro")
            elif entry.get("kind") == "item" and entry.get("item_id"):
                rendered.append(f"{max(1, int(entry.get('qty', 1) or 1))}x {entry['item_id']}")
        if rendered:
            clauses.append(f"Espólio: {', '.join(rendered)}.")
    return " ".join(clauses) or "O conflito terminou sem mudança permanente registrada."


def validate_narrative_text(summary: dict, text: str) -> dict:
    """Barreira conservadora contra reversões explícitas na prosa livre.

    Não tenta fazer fact-check semântico geral. Detecta apenas afirmações diretas
    que contradizem morte/captura/fuga canônicas e deixa o restante para o
    contrato de prompt.
    """
    lowered = str(text or "").casefold()
    violations: List[str] = []
    alive_terms = r"\b(vivo|viva|sobrevive|sobreviveu|ergueu-se|levanta-se|escapa|foge|fugiu)\b"
    free_terms = r"\b(livre|liberto|liberta|libertado|libertada|escapa|foge|fugiu)\b"
    for name in summary.get("mortos") or []:
        key = str(name).strip().casefold()
        if key and re.search(re.escape(key) + r".{0,80}" + alive_terms, lowered):
            violations.append(f"{name} foi narrado vivo/fugitivo apesar de morto.")
    for name in summary.get("capturados") or []:
        key = str(name).strip().casefold()
        if key and re.search(re.escape(key) + r".{0,80}" + free_terms, lowered):
            violations.append(f"{name} foi narrado livre apesar de capturado.")
    return {"ok": not violations, "violations": violations}


def narrative_or_fallback(summary: dict, proposed_text: str) -> str:
    """Retém prosa consistente; em contradição usa somente fatos canônicos."""
    check = validate_narrative_text(summary, proposed_text)
    if check["ok"]:
        return str(proposed_text or "").strip()
    return canonical_summary_text(summary)
