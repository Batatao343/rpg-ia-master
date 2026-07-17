# -*- coding: utf-8 -*-
"""prologue.py — Início de campanha personalizado (spec inicio-personalizado).

Gera o cenário de abertura a partir da ficha + descrição livre do jogador:
1 chamada SMART com structured output; guard de FallbackLLM obrigatório com
template determinístico (nunca levanta). `scenario_to_state_seed` traduz o
cenário aprovado em seed puro para o `/game/new` aplicar.

IA propõe, Python valida na borda; o cenário vive no client entre preview e
confirm (API continua stateless por save).
"""

from __future__ import annotations

from typing import List, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from gamedata import CLASS_THEMES, load_json_data
from llm_setup import ModelTier, get_llm
from services.chronicle import default_chapter_title

ATTITUDES = ("hostil", "neutro", "aliado")
# attitude → initial_relationship (0..10) — determinístico, nunca LLM
REL_MAP = {"hostil": 2, "neutro": 5, "aliado": 8}

MAX_BEAT_CHARS = 300


# --- Schema voltado ao LLM: SEM max_length duro. Achado do smoke real
# (2026-07-17): DeepSeek/Groq/Anthropic escrevem climax > 300 e attitude livre
# ("cauteloso e ambicioso") — limite duro derruba TODOS os candidatos por
# validação. Tamanho vira dica no description; Python trunca em `_normalize`.
class SeedNPC(BaseModel):
    name: str = Field(description="Nome do NPC (curto)")
    role: str = Field(description="Papel na história pessoal, ex.: 'credor', 'irmã exilada'")
    attitude: str = Field(description="EXATAMENTE uma palavra: hostil, neutro ou aliado")
    persona: str = Field(description="1-2 frases de personalidade")


class StartScenario(BaseModel):
    prologue: str = Field(description="Prólogo para o JOGADOR, 2ª pessoa, 100-180 palavras, pt-BR")
    opening_scene_brief: str = Field(description="Brief para o narrador: local, situação e tensão da 1ª cena (2-4 frases)")
    arc_title: str = Field(description="Título do arco, 3-6 palavras, pt-BR")
    beats: List[str] = Field(description="3 a 5 beats pessoais, 1-2 frases cada")
    climax: str = Field(description="Clímax do arco em 1-2 frases")
    seed_npcs: List[SeedNPC] = Field(default_factory=list,
                                     description="0 a 2 NPCs novos da história pessoal")


# --- Borda da API (R4): limites ESTRITOS — excedente do client vira 422.
# O server nunca confia no client; o que o próprio server gerou passa porque
# `_normalize` já truncou para estes tetos.
class SeedNPCIn(SeedNPC):
    name: str = Field(max_length=60)
    role: str = Field(max_length=80)
    attitude: str = Field(max_length=20)
    persona: str = Field(max_length=400)


class StartScenarioIn(StartScenario):
    prologue: str = Field(max_length=2000)
    opening_scene_brief: str = Field(max_length=1200)
    arc_title: str = Field(max_length=80)
    beats: List[str] = Field(max_length=5)
    climax: str = Field(max_length=300)
    seed_npcs: List[SeedNPCIn] = Field(default_factory=list, max_length=2)


def _region_context(region_name: str) -> str:
    """Card curado da região (data/onboarding.json); fallback: origins.json."""
    onboarding = load_json_data("onboarding.json") or {}
    for card in (onboarding.get("regions") or {}).values():
        if card.get("name") == region_name:
            return (f"Região: {region_name}. {card.get('tagline', '')} "
                    f"{card.get('description', '')} Gancho típico: {card.get('hook', '')} "
                    f"Bônus inicial: {card.get('bonus', '')}")
    origins = load_json_data("origins.json") or {}
    for r in origins.get("regions") or []:
        if r.get("name") == region_name:
            return f"Região: {region_name}. Bônus inicial: {r.get('bonus', '')}"
    return f"Região: {region_name}."


def _class_context(class_name: str) -> str:
    themes = CLASS_THEMES.get(class_name) or {}
    allowed = ", ".join(themes.get("allowed") or [])
    forbidden = ", ".join(themes.get("forbidden") or [])
    style = themes.get("style", "")
    parts = [f"Classe: {class_name}."]
    if style:
        parts.append(f"Estilo: {style}")
    if allowed:
        parts.append(f"Temas da classe: {allowed}.")
    if forbidden:
        parts.append(f"O gancho NÃO pode exigir que o personagem faça: {forbidden}.")
    return " ".join(parts)


def fallback_scenario(char_input: dict) -> StartScenario:
    """Template determinístico (R3) — interpola nome/classe/região, sem NPCs."""
    name = char_input.get("name", "Herói")
    class_name = char_input.get("class_name", "aventureiro")
    region = char_input.get("region", "Valoria")
    return StartScenario(
        prologue=(
            f"Você é {name}, {class_name} em {region}. O passado que o trouxe até "
            f"aqui não importa para mais ninguém — importa para você. O dia começa "
            f"como todos os outros nestas terras: com trabalho perigoso para quem "
            f"souber cobrá-lo, e com perguntas que ninguém quer responder de graça. "
            f"O que você carrega, ninguém tira. O que você busca, ninguém entrega."
        ),
        opening_scene_brief=(
            f"Cena de abertura em {region}: {name}, {class_name}, começa o dia no "
            f"local inicial da região. Estabeleça a atmosfera local, um detalhe "
            f"perturbador e um gancho de oportunidade imediata."
        ),
        arc_title=default_chapter_title(region),
        beats=[
            f"Estabeleça a chegada de {name} e a atmosfera de {region}.",
            "Apresente uma oportunidade ou ameaça ligada à vocação do personagem.",
            "Uma escolha com consequência revela o que está em jogo na região.",
        ],
        climax="Um confronto ou revelação que define o lugar do personagem nesta terra.",
        seed_npcs=[],
    )


def _normalize(scenario: StartScenario, char_input: dict) -> StartScenario:
    """Saneamento determinístico pós-LLM (nunca confia no que veio).

    Trunca cada campo para os tetos de `StartScenarioIn` — o cenário devolvido
    ao client precisa passar na re-validação estrita do `/game/new`.
    """
    data = scenario.model_dump()
    data["prologue"] = (data.get("prologue") or "").strip()[:2000]
    data["opening_scene_brief"] = (data.get("opening_scene_brief") or "").strip()[:1200]
    data["climax"] = (data.get("climax") or "").strip()[:300]
    data["arc_title"] = ((data.get("arc_title") or "").strip() or
                         default_chapter_title(char_input.get("region", "")))[:80]
    beats = [b.strip()[:MAX_BEAT_CHARS] for b in (data.get("beats") or []) if b and b.strip()]
    if not beats:
        beats = [b[:MAX_BEAT_CHARS] for b in fallback_scenario(char_input).beats]
    data["beats"] = beats[:5]
    npcs = []
    for npc in data.get("seed_npcs") or []:
        att = (npc.get("attitude") or "").strip().lower()
        npc["attitude"] = att if att in ATTITUDES else "neutro"
        npc["name"] = (npc.get("name") or "").strip()[:60]
        npc["role"] = (npc.get("role") or "").strip()[:80]
        npc["persona"] = (npc.get("persona") or "").strip()[:400]
        if npc["name"]:
            npcs.append(npc)
    data["seed_npcs"] = npcs[:2]
    return StartScenario(**data)


def build_start_scenario(char_input: dict) -> Tuple[StartScenario, bool]:
    """Monta contexto, chama SMART, aplica guard; retorna (scenario, mock)."""
    llm = get_llm(temperature=0.7, tier=ModelTier.SMART)
    mock = bool(getattr(llm, "is_mock", False))

    region_ctx = _region_context(char_input.get("region", ""))
    class_ctx = _class_context(char_input.get("class_name", ""))
    system_msg = SystemMessage(content=(
        "<PERSONA>\n"
        "Você é o motor de cenários de abertura de um RPG dark fantasy no mundo "
        "de Valoria. Você transforma a ficha e a descrição livre do jogador num "
        "início de campanha pessoal e concreto.\n"
        "<CONTEXTO>\n"
        f"{region_ctx}\n"
        f"{class_ctx}\n"
        f"Raça: {char_input.get('race', '')}.\n"
        "<REGRAS>\n"
        "1. IDIOMA (OBRIGATÓRIO): TUDO em português do Brasil (pt-BR) — prólogo, "
        "beats, arc_title, clímax, NPCs. NUNCA em inglês.\n"
        "2. A cena de abertura é CONCRETA e acontece NA região escolhida.\n"
        "3. Os beats são PESSOAIS: ligados à descrição do jogador, não à trama "
        "global do mundo.\n"
        "4. NPCs (0 a 2) são NOVOS, inventados para a história pessoal do "
        "personagem — não cite personagens nomeados do lore além da própria região.\n"
        "5. O prólogo fala com o JOGADOR em 2ª pessoa, 100-180 palavras.\n"
        "6. `opening_scene_brief` é instrução para o narrador: local, situação e "
        "tensão imediata da primeira cena.\n"
        "7. `arc_title`: 3-6 palavras, evocativo.\n"
        "8. `attitude` de cada NPC: EXATAMENTE uma palavra — hostil, neutro ou "
        "aliado.\n"
        "9. Seja conciso: clímax em 1-2 frases; cada beat em 1-2 frases."
    ))
    backstory = (char_input.get("backstory") or "").strip() or \
        "(nenhuma — crie um início coerente e genérico da região para esta classe)"
    human_msg = HumanMessage(content=(
        f"Nome: {char_input.get('name', 'Herói')}\n"
        f"Raça: {char_input.get('race', '')}\n"
        f"Classe: {char_input.get('class_name', '')}\n"
        f"Nível: {char_input.get('level', 1)}\n"
        f"Região inicial: {char_input.get('region', '')}\n"
        f"Descrição livre do jogador: {backstory}"
    ))

    # Guard de resiliência (convenção CRÍTICA): FallbackLLM devolve AIMessage,
    # não StartScenario — isinstance + try/except, nunca 500.
    try:
        result = llm.with_structured_output(StartScenario).invoke([system_msg, human_msg])
        if not isinstance(result, StartScenario):
            return fallback_scenario(char_input), mock
        return _normalize(result, char_input), mock
    except Exception as exc:  # noqa: BLE001
        print(f"[PROLOGUE ERROR] {exc}")
        return fallback_scenario(char_input), mock


def scenario_to_state_seed(scenario: StartScenario, char_input: dict,
                           start_loc_id: str) -> dict:
    """Traduz cenário aprovado em seed de estado (função pura — R5).

    O `/game/new` só aplica: campaign_plan, npcs, mensagem de abertura,
    título do capítulo 1 e sufixo do resumo narrativo.
    """
    from services import npc_layers

    region = char_input.get("region", "")
    beats = [{"description": b.strip()[:MAX_BEAT_CHARS], "status": "pending"}
             for b in scenario.beats if b and b.strip()]
    arc_title = (scenario.arc_title or "").strip() or default_chapter_title(region)

    npcs: dict = {}
    game_id = str(char_input.get("game_id", ""))
    for s in scenario.seed_npcs[:2]:
        att = s.attitude if s.attitude in ATTITUDES else "neutro"
        npc = {
            "name": s.name, "role": s.role, "persona": s.persona,
            "initial_relationship": REL_MAP[att],
            "relationship": REL_MAP[att],
            "location": region,
            "memory": [],
            "attributes": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
            "combat_stats": {"hp": 10, "ac": 10, "attacks": []},
        }
        npc = npc_layers.ensure_npc_fields(npc, game_id,
                                           home_location_id=start_loc_id,
                                           in_scene=True)
        npc["known_by_player"] = True
        npcs[s.name] = npc

    return {
        "campaign_plan": {
            "location": region,
            "beats": beats,
            "climax": scenario.climax,
            "current_step": 0,
            "last_planned_turn": 0,
            "arc_title": arc_title,
        },
        "npcs": npcs,
        "opening_message": f"Comece minha história. Cena de abertura: {scenario.opening_scene_brief}",
        "chronicle_title": arc_title,
        "summary_extra": f" Prólogo: {scenario.prologue[:300]}",
    }
