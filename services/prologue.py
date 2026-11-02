"""prologue.py — Início de campanha personalizado (spec inicio-personalizado).

Gera o cenário de abertura a partir da ficha + descrição livre do jogador:
1 chamada SMART com structured output; guard de FallbackLLM obrigatório com
template determinístico (nunca levanta). `scenario_to_state_seed` traduz o
cenário aprovado em seed puro para o `/game/new` aplicar.

IA propõe, Python valida na borda; o cenário vive no client entre preview e
confirm (API continua stateless por save).
"""

from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from gamedata import CLASS_THEMES, load_json_data
from llm_setup import ModelTier, get_llm
from observability.telemetry import log_event as _log_event
from services.chronicle import default_chapter_title
from services.prompt_guard import PLAYER_INPUT_RULE, wrap_player_input

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
    kind: Literal["personal", "plot"] = Field(
        default="personal", description="DERIVADO pelo servidor; a LLM não preenche"
    )


class PersonalNPC(BaseModel):
    """SPEC-351 R5.6: duas camadas — pública (pode ir ao pool) e `bond` (só local)."""

    name: str = Field(description="Nome curto, inventado; nunca um nome escrito pelo jogador")
    role_public: str = Field(description="Quem ele é no mundo, sem citar o protagonista")
    persona_public: str = Field(
        description="1-2 frases; sem citar o protagonista nem a história dele"
    )
    appearance: str = Field(description="1 frase concreta")
    legend: str = Field(description="O que dizem dele, 1 frase (<=160)")
    bond: str = Field(description="Laço com o protagonista (fica só nesta partida)")
    attitude: str = Field(description="EXATAMENTE uma palavra: hostil, neutro ou aliado")


class StartScenario(BaseModel):
    prologue: str = Field(description="Prólogo para o JOGADOR, 2ª pessoa, 100-180 palavras, pt-BR")
    opening_scene_brief: str = Field(
        description="Brief para o narrador: local, situação e tensão da 1ª cena (2-4 frases)"
    )
    arc_title: str = Field(description="Título do arco, 3-6 palavras, pt-BR")
    beats: list[str] = Field(description="3 a 5 beats pessoais, 1-2 frases cada")
    climax: str = Field(description="Clímax do arco em 1-2 frases")
    seeking: str = Field(
        default="", description="O que o personagem busca, 1 frase, em palavras do mundo"
    )
    thread_refs: list[str] = Field(
        default_factory=list, description="ids EXATOS do <PORTAS_DE_TRAMA> (1 ou 2)"
    )
    plot_npc_id: str = Field(default="", description="entity_id EXATO do <NPCS_DA_TRAMA>")
    plot_npc_hook: str = Field(default="", description="Como ele cruza o caminho do herói, 1 frase")
    plot_npc_name: str = Field(default="", description="DERIVADO pelo servidor; a LLM não preenche")
    personal_npc: PersonalNPC | None = None
    seed_npcs: list[SeedNPC] = Field(
        default_factory=list,
        description="0 a 2 NPCs novos da história pessoal (DERIVADO quando há personal_npc)",
    )


# --- Borda da API (R4): limites ESTRITOS — excedente do client vira 422.
# O server nunca confia no client; o que o próprio server gerou passa porque
# `_normalize` já truncou para estes tetos.
class SeedNPCIn(SeedNPC):
    name: str = Field(max_length=60)
    role: str = Field(max_length=80)
    attitude: str = Field(max_length=20)
    persona: str = Field(max_length=400)


class PersonalNPCIn(PersonalNPC):
    name: str = Field(max_length=60)
    role_public: str = Field(max_length=80)
    persona_public: str = Field(max_length=400)
    appearance: str = Field(max_length=300)
    legend: str = Field(max_length=160)
    bond: str = Field(max_length=300)
    attitude: str = Field(max_length=20)


class StartScenarioIn(StartScenario):
    prologue: str = Field(max_length=2000)
    opening_scene_brief: str = Field(max_length=1200)
    arc_title: str = Field(max_length=80)
    beats: list[str] = Field(max_length=5)
    climax: str = Field(max_length=300)
    seeking: str = Field(default="", max_length=200)
    thread_refs: list[str] = Field(default_factory=list, max_length=2)
    plot_npc_id: str = Field(default="", max_length=80)
    plot_npc_hook: str = Field(default="", max_length=300)
    plot_npc_name: str = Field(default="", max_length=60)
    personal_npc: PersonalNPCIn | None = None
    seed_npcs: list[SeedNPCIn] = Field(default_factory=list, max_length=2)

    @field_validator("thread_refs")
    @classmethod
    def _ref_len(cls, value: list[str]) -> list[str]:
        if any(len(v) > 80 for v in value):
            raise ValueError("thread_ref acima de 80 caracteres")
        return value


def _region_context(region_name: str) -> str:
    """Card curado da região (data/onboarding.json); fallback: origins.json."""
    onboarding = load_json_data("onboarding.json") or {}
    for card in (onboarding.get("regions") or {}).values():
        if card.get("name") == region_name:
            return (
                f"Região: {region_name}. {card.get('tagline', '')} "
                f"{card.get('description', '')} Gancho típico: {card.get('hook', '')} "
                f"Bônus inicial: {card.get('bonus', '')}"
            )
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


def _thread_on() -> bool:
    from services import opening_threads

    return opening_threads.mode() == "on"


def fallback_scenario(char_input: dict, menu: dict | None = None) -> StartScenario:
    """Template determinístico (R3/R9) — interpola nome/classe/região.

    Com `menu` (SPEC-351): liga à 1ª porta e ao 1º NPC do menu, 0 NPC pessoal (D4)."""
    name = char_input.get("name", "Herói")
    class_name = char_input.get("class_name", "aventureiro")
    region = char_input.get("region", "Valoria")
    doors = (menu or {}).get("doors") or []
    npcs = (menu or {}).get("npcs") or []
    door = doors[0] if doors else None
    npc = npcs[0] if npcs else None
    extra: dict = {}
    if door:
        extra = {
            "seeking": f"descobrir o que há por trás de «{door['name']}»",
            "thread_refs": [door["door_id"]],
            "plot_npc_id": npc["entity_id"] if npc else "",
            "plot_npc_hook": (
                f"{npc['name']} cruza o seu caminho quando você começa a perguntar." if npc else ""
            ),
        }
    prologue = (
        f"Você é {name}, {class_name} em {region}. O passado que o trouxe até "
        f"aqui não importa para mais ninguém — importa para você. O dia começa "
        f"como todos os outros nestas terras: com trabalho perigoso para quem "
        f"souber cobrá-lo, e com perguntas que ninguém quer responder de graça. "
        f"O que você carrega, ninguém tira. O que você busca, ninguém entrega."
    )
    beats = [
        f"Estabeleça a chegada de {name} e a atmosfera de {region}.",
        "Apresente uma oportunidade ou ameaça ligada à vocação do personagem.",
        "Uma escolha com consequência revela o que está em jogo na região.",
    ]
    if door:
        prologue += f" Corre pelas ruas uma conversa baixa: {door['name']}. Você quer saber mais."
        beats = [
            f"Estabeleça a chegada de {name} e a atmosfera de {region}.",
            f"Um primeiro sinal concreto de «{door['name']}» cruza o caminho do personagem.",
            "Seguir o sinal custa algo e revela quem se move nas bordas dessa história.",
        ]
    scenario = StartScenario(
        prologue=prologue,
        opening_scene_brief=(
            f"Cena de abertura em {region}: {name}, {class_name}, começa o dia no "
            f"local inicial da região. Estabeleça a atmosfera local, um detalhe "
            f"perturbador e um gancho de oportunidade imediata."
        ),
        arc_title=default_chapter_title(region),
        beats=beats,
        climax="Um confronto ou revelação que define o lugar do personagem nesta terra.",
        seed_npcs=[],
        **extra,
    )
    return _derive_seed_npcs(scenario, menu) if door else scenario


def _trim(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _derive_seed_npcs(scenario: StartScenario, menu: dict | None) -> StartScenario:
    """`seed_npcs` é DERIVADO (compat de cliente antigo): só o NPC pessoal (o da trama é `plot_npc_id`)."""
    derived: list[SeedNPC] = []
    p = scenario.personal_npc
    if p is not None:
        derived.append(
            SeedNPC(
                name=p.name,
                role=p.role_public,
                attitude=p.attitude if p.attitude in ATTITUDES else "neutro",
                persona=p.persona_public,
                kind="personal",
            )
        )
    return scenario.model_copy(update={"seed_npcs": derived[:2]})


def _normalize(
    scenario: StartScenario, char_input: dict, menu: dict | None = None
) -> StartScenario:
    """Saneamento determinístico pós-LLM (nunca confia no que veio).

    Trunca cada campo para os tetos de `StartScenarioIn` — o cenário devolvido
    ao client precisa passar na re-validação estrita do `/game/new`.
    Com `menu` (SPEC-351 R8): âncoras fora do menu são descartadas; nome/papel do
    NPC da trama vêm do grafo; no máximo 1 NPC pessoal.
    """
    data = scenario.model_dump()
    data["prologue"] = (data.get("prologue") or "").strip()[:2000]
    data["opening_scene_brief"] = (data.get("opening_scene_brief") or "").strip()[:1200]
    data["climax"] = (data.get("climax") or "").strip()[:300]
    data["arc_title"] = (
        (data.get("arc_title") or "").strip() or default_chapter_title(char_input.get("region", ""))
    )[:80]
    beats = [b.strip()[:MAX_BEAT_CHARS] for b in (data.get("beats") or []) if b and b.strip()]
    if not beats:
        beats = [b[:MAX_BEAT_CHARS] for b in fallback_scenario(char_input).beats]
    data["beats"] = beats[:5]
    if (
        menu is not None
    ):  # SPEC-351 E4: beats/clímax vão ao cliente — segredo/fação oculta vira rumor público
        from services.secret_signatures import sanitize_beat

        data["beats"] = [sanitize_beat(b, {}) for b in data["beats"]]
        data["climax"] = sanitize_beat(data["climax"], {})
        # SPEC-366 R2: prólogo (o jogador lê) e brief (vira a 1ª narração) — com acerto, o texto
        # inteiro cai no template (não se reescreve prosa livre).
        base = fallback_scenario(char_input, menu)
        for key, safe in (
            ("prologue", base.prologue),
            ("opening_scene_brief", base.opening_scene_brief),
        ):
            if sanitize_beat(data[key], {}) != data[key]:
                data[key] = safe
                _log_event("prologue", "thread.downgraded", reason=f"{key}_leak")
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
    data["seeking"] = _trim(data.get("seeking"), 200)
    data["plot_npc_hook"] = _trim(data.get("plot_npc_hook"), 300)
    if menu is None:  # flag off / cenário legado: campos novos ficam vazios
        data.update(
            thread_refs=[],
            plot_npc_id="",
            plot_npc_hook="",
            plot_npc_name="",
            seeking="",
            personal_npc=None,
        )
        return StartScenario(**data)
    return _apply_menu(StartScenario(**data), menu)


def _apply_menu(scenario: StartScenario, menu: dict) -> StartScenario:
    """R8: valida as âncoras do cenário contra o menu (também na revalidação do `/game/new`)."""
    doors = {d["door_id"] for d in menu.get("doors") or []}
    refs = [r for r in dict.fromkeys(scenario.thread_refs or []) if r in doors][:2]
    if not refs and menu.get("doors"):
        refs = [menu["doors"][0]["door_id"]]
        _log_event("prologue", "thread.downgraded", reason="refs_defaulted")
    npcs = {n["entity_id"]: n for n in menu.get("npcs") or []}
    plot_id = scenario.plot_npc_id if scenario.plot_npc_id in npcs else ""
    if not plot_id and npcs:
        plot_id = next(iter(npcs))
        _log_event("prologue", "thread.downgraded", reason="plot_npc_defaulted")
    if not npcs:
        _log_event("prologue", "thread.no_plot_npc")
    personal = scenario.personal_npc
    if personal is not None:
        att = (personal.attitude or "").strip().lower()
        personal = PersonalNPC(
            name=_trim(personal.name, 60),
            role_public=_trim(personal.role_public, 80),
            persona_public=_trim(personal.persona_public, 400),
            appearance=_trim(personal.appearance, 300),
            legend=_trim(personal.legend, 160),
            bond=_trim(personal.bond, 300),
            attitude=att if att in ATTITUDES else "neutro",
        )
        if not personal.name:
            personal = None
    out = scenario.model_copy(
        update={
            "thread_refs": refs,
            "plot_npc_id": plot_id,
            "plot_npc_hook": scenario.plot_npc_hook if plot_id else "",
            "plot_npc_name": npcs[plot_id]["name"] if plot_id else "",
            "personal_npc": personal,
        }
    )
    return _derive_seed_npcs(out, menu)


def revalidate_scenario(scenario: StartScenario, menu: dict | None) -> StartScenario:
    """Borda do `/game/new`: âncoras forjadas pelo cliente são descartadas (R8/§3.2)."""
    if menu is None or not _thread_on():
        return scenario
    return _apply_menu(scenario, menu)


_TONE = (
    "Tom de Valoria: tudo tem custo; o poder corrói (entropia); instituições são armadilhas "
    "educadas; a crônica é cansada, sem epopeia; segredos são inversões, não prêmios; "
    "léxico próprio (nada de mana, buff, crítico, loot, boss)."
)


def _legacy_rules() -> str:
    return (
        "3. Os beats são PESSOAIS: ligados à descrição do jogador, não à trama "
        "global do mundo.\n"
        "4. NPCs (0 a 2) são NOVOS, inventados para a história pessoal do "
        "personagem — não cite personagens nomeados do lore além da própria região.\n"
    )


def _thread_rules() -> str:
    return (
        "3. TRAMA: escolha 1 ou 2 portas do <PORTAS_DE_TRAMA> e devolva os ids EXATOS em "
        "`thread_refs`. O personagem começa NA BORDA: busca algo pequeno e pessoal que toca "
        "a trama sem saber — nada de escolhido, profecia, herança secreta ou começar no meio "
        "da crise.\n"
        "4. `seeking`: o que ele busca, 1 frase, em palavras do mundo, e o prólogo diz isso. "
        "Os beats revelam a trama aos poucos: o 1º beat é pessoal e concreto, a trama "
        "aparece pelo 2º ou 3º; o clímax do 1º arco ainda é na borda. OBRIGATÓRIO: cite o "
        "TÍTULO COMPLETO da porta escolhida (a parte antes do travessão), com as mesmas palavras "
        "na mesma ordem, como parte natural de uma frase do `opening_scene_brief` OU do 2º beat "
        "(caixa livre, sem aspas, ex.: um boato ouvido na rua). NUNCA escreva os termos de bastidor porta, trama ou menu na ficção. Evite as "
        "palavras escolhido, profecia, destino e herdeiro.\n"
        "4b. NPCs: exatamente 1 `personal_npc` (NOVO, criado para a história, costurado em "
        "volta da <SEMENTE_NPC_PESSOAL>) e 1 NPC da trama: `plot_npc_id` = entity_id EXATO do "
        "<NPCS_DA_TRAMA> (nome e papel vêm do mundo) e `plot_npc_hook` = como ele cruza o "
        "caminho do herói. O `personal_npc` tem duas camadas: `bond` (relação com o "
        "protagonista, fica só nesta partida) e `persona_public`/`role_public`/`appearance`/"
        "`legend` (quem ele é no mundo, SEM citar o protagonista, o nome dele ou a história "
        "dele). Nunca use um nome escrito pelo jogador.\n"
        f"4c. {_TONE}\n"
    )


def _roll_pool_seed(nonce: str, start_loc_id: str):
    """R14: semente do motor ANTES da LLM; `game_id` sintético, determinístico por nonce+slot."""
    from services import npc_seed, shared_pool
    from services.shared_pool_models import PoolNamespace

    taken = (
        (lambda sig: shared_pool.signature_taken(PoolNamespace.NPC, sig))
        if shared_pool.pool_mode() != "off"
        else (lambda sig: False)
    )
    seed = None
    for slot in range(npc_seed.MAX_REROLLS + 1):
        seed = npc_seed.roll_npc_seed(
            game_id=f"prologue:{nonce}", turn=0, location_id=start_loc_id, slot=slot
        )
        try:
            if not taken(npc_seed.seed_signature(seed)):
                return seed, slot
        except Exception:  # noqa: BLE001  # silent-ok: store indisponível, usa este slot
            return seed, slot
    return seed, npc_seed.MAX_REROLLS


def build_start_scenario_ctx(char_input: dict) -> tuple[StartScenario, bool, dict]:
    """Monta contexto, chama SMART, aplica guard; retorna (scenario, mock, ctx).

    `ctx` = {menu, seed, slot, nonce, template}: o `/game/prologue` assina com ele."""
    import uuid

    from services import opening_threads as ot

    llm = get_llm(temperature=0.7, tier=ModelTier.SMART)
    mock = bool(getattr(llm, "is_mock", False))
    flag = ot.mode()
    ctx: dict = {"menu": None, "seed": None, "slot": 0, "nonce": "", "template": False}

    raw_backstory = (char_input.get("backstory") or "").strip()
    region_ctx = _region_context(char_input.get("region", ""))
    class_ctx = _class_context(char_input.get("class_name", ""))
    thread_ctx = ""
    if flag != "off":
        region_id, start_loc = ot.start_of_region(char_input.get("region", ""))
        menu = ot.thread_menu(
            region_id,
            backstory=raw_backstory,
            start_location_id=start_loc,
            postura=str(char_input.get("class_name") or ""),
            race=str(char_input.get("race") or ""),
        )
        if flag == "shadow":
            _log_event(
                "prologue", "thread.shadow", doors=len(menu["doors"]), npcs=len(menu["npcs"])
            )
        elif menu["doors"]:
            nonce = uuid.uuid4().hex
            seed, slot = _roll_pool_seed(nonce, start_loc)
            ctx.update(menu=menu, seed=seed, slot=slot, nonce=nonce)
            labels = ""
            if seed is not None:
                from services import npc_seed

                labels = "\n".join(
                    f"- {k}: {v}" for k, v in npc_seed.seed_labels(seed).items() if v
                )
            lore = ot.lore_block(menu, raw_backstory)
            thread_ctx = (
                f"{ot.menu_block(menu)}\n<LORE_DA_REGIAO>\n{lore}\n</LORE_DA_REGIAO>\n"
                f"<SEMENTE_NPC_PESSOAL>\n{labels}\n</SEMENTE_NPC_PESSOAL>\n"
            )
    menu = ctx["menu"]
    use_threads = menu is not None
    system_msg = SystemMessage(
        content=(
            "<PERSONA>\n"
            "Você é o motor de cenários de abertura de um RPG dark fantasy no mundo "
            "de Valoria. Você transforma a ficha e a descrição livre do jogador num "
            "início de campanha pessoal e concreto.\n"
            "<CONTEXTO>\n"
            f"{region_ctx}\n"
            f"{class_ctx}\n"
            f"Raça: {char_input.get('race', '')}.\n"
            f"{thread_ctx}"
            "<REGRAS>\n"
            "1. IDIOMA (OBRIGATÓRIO): TUDO em português do Brasil (pt-BR) — prólogo, "
            "beats, arc_title, clímax, NPCs. NUNCA em inglês.\n"
            "2. A cena de abertura é CONCRETA e acontece NA região escolhida.\n"
            f"{_thread_rules() if use_threads else _legacy_rules()}"
            "5. O prólogo fala com o JOGADOR em 2ª pessoa, 100-180 palavras.\n"
            "6. `opening_scene_brief` é instrução para o narrador: local, situação e "
            "tensão imediata da primeira cena.\n"
            "7. `arc_title`: 3-6 palavras, evocativo.\n"
            "8. `attitude` de cada NPC: EXATAMENTE uma palavra — hostil, neutro ou "
            "aliado.\n"
            "9. Seja conciso: clímax em 1-2 frases; cada beat em 1-2 frases.\n"
            f"10. {PLAYER_INPUT_RULE}"
        )
    )
    # SPEC-351 R6/P6: nome e descrição livre entram delimitados como DADO.
    backstory = (
        wrap_player_input(raw_backstory)
        if raw_backstory
        else "(nenhuma — crie um início coerente e genérico da região para esta classe)"
    )
    human_msg = HumanMessage(
        content=(
            f"Nome: {wrap_player_input(char_input.get('name', 'Herói'))}\n"
            f"Raça: {char_input.get('race', '')}\n"
            f"Classe: {char_input.get('class_name', '')}\n"
            f"Nível: {char_input.get('level', 1)}\n"
            f"Região inicial: {char_input.get('region', '')}\n"
            f"Descrição livre do jogador: {backstory}"
        )
    )

    # Guard de resiliência (convenção CRÍTICA): FallbackLLM devolve AIMessage,
    # não StartScenario — isinstance + try/except, nunca 500.
    try:
        result = llm.with_structured_output(StartScenario).invoke([system_msg, human_msg])
        if not isinstance(result, StartScenario):
            return _template(char_input, menu, ctx), mock, ctx
        scenario = _normalize(result, char_input, menu)
    except Exception as exc:  # noqa: BLE001
        _log_event("prologue", "failed", level="error", error=type(exc).__name__)
        return _template(char_input, menu, ctx), mock, ctx
    if menu is not None:
        _log_event(
            "prologue",
            "thread.linked",
            doors=len(scenario.thread_refs),
            plot_npc=bool(scenario.plot_npc_id),
            personal=scenario.personal_npc is not None,
            source=menu["source"],
        )
    return scenario, mock, ctx


def _template(char_input: dict, menu: dict | None, ctx: dict) -> StartScenario:
    ctx["template"] = True
    ctx["seed"] = None  # template não tem NPC pessoal (D4)
    if menu is not None:
        _log_event("prologue", "thread.downgraded", reason="template")
    return fallback_scenario(char_input, menu)


def build_start_scenario(char_input: dict) -> tuple[StartScenario, bool]:
    """Compat (SPEC-045): (scenario, mock). O contexto do token vem de `build_start_scenario_ctx`."""
    scenario, mock, _ctx = build_start_scenario_ctx(char_input)
    return scenario, mock


# --- Token do cenário (R15): `<nonce>.<slot>.<v1.epoch.hmac>` -------------- #
def _token_payload(scenario: StartScenario, nonce: str, slot: int) -> dict:
    return {
        "personal_npc": scenario.personal_npc.model_dump() if scenario.personal_npc else None,
        "nonce": nonce,
        "slot": int(slot),
        "thread_refs": list(scenario.thread_refs),
        "plot_npc_id": scenario.plot_npc_id,
    }


def sign_for_client(scenario: StartScenario, ctx: dict, owner: str) -> str:
    from services import prologue_token

    if not ctx.get("nonce") or scenario.personal_npc is None:
        return ""
    sig = prologue_token.sign_scenario(_token_payload(scenario, ctx["nonce"], ctx["slot"]), owner)
    return f"{ctx['nonce']}.{ctx['slot']}.{sig}" if sig else ""


def verified_seed(scenario: StartScenario, token: str | None, owner: str, start_loc_id: str):
    """Semente do motor se (e só se) o token confere; senão None (NPC pessoal só local)."""
    from services import npc_seed, prologue_token

    if not token or scenario.personal_npc is None:
        return None
    try:
        nonce, slot_raw, sig = token.split(".", 2)
        slot = int(slot_raw)
    except ValueError:
        return None
    if not prologue_token.verify_scenario(sig, _token_payload(scenario, nonce, slot), owner):
        return None
    return npc_seed.roll_npc_seed(
        game_id=f"prologue:{nonce}", turn=0, location_id=start_loc_id, slot=slot
    )


def personal_pool_document(npc: PersonalNPC, seed) -> dict:
    """R16: só a camada pública, pelas chaves da allowlist. Sem bond/attitude/jogador."""
    doc = {
        "name": npc.name,
        "role": npc.role_public,
        "persona": npc.persona_public,
        "appearance": npc.appearance,
        "legend": npc.legend[:160],
        "attributes": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
        "initial_relationship": 5,
    }
    if seed is not None:
        doc.update(
            race_id=seed.race_id,
            origin_region_id=seed.origin_region_id,
            faction_id=seed.faction_id,
            profession_id=seed.profession_id,
        )
    return doc


_HOSTILE = re.compile(
    # verbo de descarte + alvo de instrução explícito ("ignora as regras da guilda" é benigno)
    r"\b(ignor\w*|esque\w*|desconsider\w*|descart\w*|forget|disregard|override)\b"
    r".{0,40}\b(instru\w*|anterior\w*|acima|previous|prior|above|system|prompt|"
    r"regras\s+(do|de)\s+(sistema|jogo|mestre))\b|"
    r"system\s*prompt|prompt\s+do\s+sistema|"
    r"\b(revele|registre|marque|reveal|record)\b.{0,40}\b(json|proposed_events|quest_\w+|sistema)\b|"
    r"</?\w+>|\bquest_\w+|\bproposed_events\b|jailbreak|"
    r"\byou\s+are\s+now\b|\bagora\s+voce\s+e\b|\bnovas?\s+instrucoes\b|\bdeveloper\s+mode\b",
    re.IGNORECASE | re.DOTALL,
)
_SPACED = re.compile(r"(?:\b\w[\s.\-_]){3,}\w\b")


def _fold_hostile(text: str) -> tuple[str, str]:
    """(sem acento/minúsculo/espaço colapsado, idem com letras separadas coladas: "i g n o r e")."""
    import unicodedata

    low = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    low = re.sub(r"\s+", " ", low)
    return low, _SPACED.sub(lambda m: re.sub(r"[\s.\-_]", "", m.group(0)), low)


def looks_hostile(*texts: str) -> bool:
    """Heurística barata de injeção na descrição/nome: tal prólogo nunca promove NPC ao pool.

    É só SINAL extra (SPEC-366 R1): o efeito é o NPC ficar local; as barreiras reais são a
    delimitação da entrada, shingles, PII, nome digitado e o juiz."""
    return any(_HOSTILE.search(v) for t in texts for v in _fold_hostile(t))


def submit_personal_npc(
    scenario: StartScenario, seed, *, game_id: str, region_id: str, char_input: dict
) -> str | None:
    """R17/R18: submete o NPC pessoal ao pool. Chamado DEPOIS de persistir; nunca levanta.

    Sem semente verificada o NPC fica só local (entrada `local_only`)."""
    from services import shared_pool
    from services.shared_pool_models import PoolNamespace

    npc = scenario.personal_npc
    if npc is None or shared_pool.pool_mode() == "off":
        return None
    inputs = [
        str(char_input.get("name") or ""),
        str(char_input.get("backstory") or ""),
        scenario.seeking,
    ]
    origin = "player" if shared_pool.name_typed_by_player(npc.name, inputs) else "narrator"
    if looks_hostile(*inputs):  # §6 caso 8: entrada hostil → só local, nunca promovida
        origin = "player"
        _log_event("prologue", "thread.downgraded", reason="hostile_input")
    if seed is not None:  # P2-6: token reaproveitado → mesma semente já submetida → só local
        try:
            from services import npc_seed

            if shared_pool.signature_taken(PoolNamespace.NPC, npc_seed.seed_signature(seed)):
                seed = None
                _log_event("prologue", "thread.downgraded", reason="seed_reused")
        except Exception:  # noqa: BLE001  # silent-ok: sem checagem, o validador de duplicata ainda barra
            pass
    try:
        entry = shared_pool.submit(
            PoolNamespace.NPC,
            personal_pool_document(npc, seed),
            game_id=str(game_id),
            region_id=region_id,
            name_origin=origin,
            seed=seed,
            player_inputs=inputs,
        )
    except Exception as exc:  # noqa: BLE001
        _log_event("prologue", "pool_submit_failed", level="warning", error=type(exc).__name__)
        return None
    _log_event("prologue", "pool_submit", status=entry.status.value)
    return entry.entry_id


def scenario_to_state_seed(
    scenario: StartScenario,
    char_input: dict,
    start_loc_id: str,
    *,
    menu: dict | None = None,
    pool_seed=None,
) -> dict:
    """Traduz cenário aprovado em seed de estado (função pura — R5).

    O `/game/new` só aplica: campaign_plan, npcs, mensagem de abertura,
    título do capítulo 1 e sufixo do resumo narrativo. Com `menu` (SPEC-351)
    grava o fio de abertura e as fichas do NPC da trama e do NPC pessoal."""
    from services import npc_layers

    region = char_input.get("region", "")
    beats = [
        {"description": b.strip()[:MAX_BEAT_CHARS], "status": "pending"}
        for b in scenario.beats
        if b and b.strip()
    ]
    arc_title = (scenario.arc_title or "").strip() or default_chapter_title(region)

    npcs: dict = {}
    game_id = str(char_input.get("game_id", ""))
    thread_on = menu is not None and bool(scenario.thread_refs)
    structured = thread_on and (scenario.personal_npc is not None or bool(scenario.plot_npc_id))
    for s in [] if structured else scenario.seed_npcs[:2]:
        att = s.attitude if s.attitude in ATTITUDES else "neutro"
        npc = {
            "name": s.name,
            "role": s.role,
            "persona": s.persona,
            "initial_relationship": REL_MAP[att],
            "relationship": REL_MAP[att],
            "location": region,
            "memory": [],
            "attributes": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
            "combat_stats": {"hp": 10, "ac": 10, "attacks": []},
        }
        npc = npc_layers.ensure_npc_fields(
            npc, game_id, home_location_id=start_loc_id, in_scene=True
        )
        npc["known_by_player"] = True
        npcs[s.name] = npc

    plan: dict = {
        "location": region,
        "beats": beats,
        "climax": scenario.climax,
        "current_step": 0,
        "last_planned_turn": 0,
        "arc_title": arc_title,
    }
    brief = scenario.opening_scene_brief
    if thread_on:
        from services import opening_threads as ot

        plot_key = personal_key = ""
        row = next((n for n in menu["npcs"] if n["entity_id"] == scenario.plot_npc_id), None)
        if row:
            npcs[row["name"]] = ot.plot_npc_sheet(
                row, game_id, start_loc_id, hook=scenario.plot_npc_hook
            )
            plot_key = row["name"]
            if scenario.plot_npc_hook:
                brief += f" {scenario.plot_npc_hook}"
            home = row.get("home_location_id")
            if home and home != start_loc_id:
                brief += (
                    f" Quem pode ajudar: {row['name']}, que se encontra em outro lugar da região."
                )
        p = scenario.personal_npc
        if p is not None:
            att = p.attitude if p.attitude in ATTITUDES else "neutro"
            sheet = {
                "name": p.name,
                "role": p.role_public,
                "persona": p.persona_public,
                "appearance": p.appearance,
                "legend": p.legend,
                "bond": p.bond,
                "initial_relationship": REL_MAP[att],
                "relationship": REL_MAP[att],
                "location": region,
                "memory": [],
                "attributes": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
                "combat_stats": {"hp": 10, "ac": 10, "attacks": []},
            }
            if pool_seed is not None:
                from agents.npc import seed_motives_of

                sheet["seed_motives"] = seed_motives_of(pool_seed)
            sheet = npc_layers.ensure_npc_fields(
                sheet, game_id, home_location_id=start_loc_id, in_scene=True
            )
            sheet["known_by_player"] = True
            npcs[p.name] = sheet
            personal_key = p.name
        plan["opening_thread"] = {
            "thread_refs": list(scenario.thread_refs),
            "plot_npc_key": plot_key,
            "personal_npc_key": personal_key,
            "seeking": scenario.seeking,
            "region_id": menu["region_id"],
            "arcs_left": ot.ARCS_LEFT_DEFAULT,
        }

    return {
        "campaign_plan": plan,
        "npcs": npcs,
        "opening_message": f"Comece minha história. Cena de abertura: {brief}",
        "chronicle_title": arc_title,
        "summary_extra": f" Prólogo: {scenario.prologue[:300]}",
    }
