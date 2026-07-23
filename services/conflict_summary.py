"""services/conflict_summary.py — resumo canônico pós-conflito (spec conflito-12).

Contrato ÚNICO entre o motor determinístico e a LLM: depois que combate,
perseguição e loot resolvem 100% SEM LLM, `build_summary` monta o `ConflictSummary`
(fatos canônicos, não detalhes mecânicos brutos) que a narrativa retoma — sem poder
reverter nenhum fato (R3). `economy.roll_loot` NÃO muda (risco §7): `loot_context`
só decide o que passar como `danger` (Nível do Encontro em vez de `danger_level`).

ADITIVO: módulo novo + testes. O consumo em `agents/loot.py`/`agents/archivist.py`
é o cutover (conflito-13).
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ConflictSummary(BaseModel):
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
    return summary.model_dump()


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
    return facts
