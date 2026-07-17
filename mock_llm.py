"""
mock_llm.py
Modo SIMULADO — usado quando não há GOOGLE_API_KEY.

Devolve dados fictícios plausíveis para cada agente, deixando o jogo jogável
(e a UI testável) sem chave de API. Não faz nenhuma chamada de rede.

Estratégia: um preenchedor genérico introspecta qualquer modelo Pydantic e
fabrica valores por tipo; "overrides" por modelo injetam conteúdo temático
(narrativa, roteamento, fichas) onde a qualidade importa.
"""
import random
import re
import typing
from enum import Enum

from langchain_core.messages import AIMessage
from pydantic import BaseModel

# --------------------------------------------------------------------------
# Pools de conteúdo dark fantasy
# --------------------------------------------------------------------------
_NARRATIVES = [
    "O vento carrega cinzas frias por entre as ruínas. {acao_eco} Sombras se mexem onde "
    "não deveria haver ninguém, e um cheiro de ferro velho paira no ar. Ao longe, um sino "
    "rachado bate uma única vez.\n\nO que você faz?",
    "A neblina engole os seus passos. {acao_eco} Uma porta de carvalho range sozinha à sua "
    "frente, entreaberta para uma escuridão que parece respirar. Marcas de garras descem "
    "pela madeira.\n\nVocê avança, recua ou observa mais?",
    "Tochas mortas forram o corredor de pedra. {acao_eco} Algo sussurra o seu nome — ou "
    "talvez seja só o eco da sua própria respiração. No chão, ossos pequenos formam um "
    "círculo deliberado.\n\nQual o seu próximo movimento?",
    "O céu cor de chumbo se fecha sobre a aldeia abandonada. {acao_eco} Janelas vazias "
    "encaram você como órbitas ocas. Um corvo pousa, inclina a cabeça, e espera.\n\n"
    "Para onde você vai?",
]

_NPC_LINES = [
    "Você não é daqui, é? Poucos chegam tão longe e ainda respiram.",
    "Cuidado com o que pergunta. Algumas respostas custam mais que ouro.",
    "Já vi muitos como você. A maioria não voltou pra contar.",
    "Se procura o que está enterrado nessas terras, devia procurar a morte primeiro.",
]
_NPC_ACTIONS = [
    "cospe no chão e aperta o cabo de uma faca",
    "ajusta o capuz, escondendo metade do rosto",
    "ri baixo, sem nenhum humor",
    "encara você por um longo instante antes de falar",
]
_NPC_NAMES = ["Corvo", "Velha Maren", "Tobias Cinza", "A Encapuzada"]
_NPC_ROLES = ["mercador", "andarilho", "guarda", "vidente"]

_ENEMY_NAMES = ["Goblin", "Carniçal", "Lobo Sombrio", "Bandido", "Esqueleto"]
_ITEM_NAMES = [
    ("Adaga Enferrujada", "adaga_enferrujada", "weapon"),
    ("Poção Turva", "pocao_turva", "potion"),
    ("Amuleto Rachado", "amuleto_rachado", "armor"),
    ("Moeda Antiga", "moeda_antiga", "material"),
]
_BEATS = [
    "Estabeleça a atmosfera opressora do local e um detalhe perturbador.",
    "O jogador encontra um vestígio de quem esteve aqui antes.",
    "Uma ameaça se revela — sutil primeiro, depois inegável.",
]


def _last_human(messages) -> str:
    for m in reversed(messages or []):
        if m.__class__.__name__ == "HumanMessage":
            return str(getattr(m, "content", ""))
    return ""


def _acao_eco(messages) -> str:
    txt = _last_human(messages).strip()
    if not txt:
        return "Você respira fundo e segue em frente."
    txt = txt[0].upper() + txt[1:]
    if not txt.endswith((".", "!", "?")):
        txt += "."
    return f"Você {txt[0].lower()}{txt[1:]}"


# --------------------------------------------------------------------------
# Preenchedor genérico por introspecção de tipo
# --------------------------------------------------------------------------
def _value_for(annotation):
    if annotation is None:
        return ""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin in (list, typing.List):
        return []
    if origin in (dict, typing.Dict):
        return {}
    if origin is typing.Union:  # inclui Optional
        non_none = [a for a in args if a is not type(None)]
        return None if len(non_none) != len(args) else _value_for(non_none[0])
    if origin is typing.Literal:
        return args[0] if args else ""

    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel):
            return _fill(annotation, {})
        if issubclass(annotation, Enum):
            return list(annotation)[0]
        if annotation is bool:
            return False
        if annotation is int:
            return 1
        if annotation is float:
            return 0.0
        if annotation is str:
            return ""
    return ""


def _fill(model, overrides):
    data = {}
    for name, field in model.model_fields.items():
        if name in overrides:
            data[name] = overrides[name]
        else:
            data[name] = _value_for(field.annotation)
    try:
        return model(**data)
    except Exception:
        return model.model_construct(**data)


def _list_item_cls(model, field_name):
    """Classe do item de um campo List[X]."""
    ann = model.model_fields[field_name].annotation
    args = typing.get_args(ann)
    return args[0] if args else None


# --------------------------------------------------------------------------
# Overrides por modelo (conteúdo temático)
# --------------------------------------------------------------------------
def _route_decision(model, messages):
    txt = _last_human(messages).lower()
    enum_cls = model.model_fields["route"].annotation

    def route(v):
        try:
            return enum_cls(v)
        except Exception:
            return list(enum_cls)[0]

    combat = ["atac", "golpe", "luto", "luta", "mato", "mata", "espada", "lâmina",
              "lamina", "soco", "chute", "dispar", "flecha", "enfrent", "mira", "esfaque"]
    npc = ["fal", "pergunt", "convers", "cumpriment", "negoci", "saúd", "saud",
           "respond", "grit", "digo", "peço", "peco"]
    loot = ["peg", "vasculh", "baú", "bau", "saque", "loot", "recolh", "abro",
            "compr", "vend", "forj", "craft"]

    if any(k in txt for k in combat):
        return _fill(model, {"route": route("combat_agent"), "target": "Inimigo",
                             "reasoning": "[simulado] intenção de combate", "confidence": 0.9,
                             "loot_context": None})
    if any(k in txt for k in loot):
        ctx = "SHOP" if ("compr" in txt or "vend" in txt) else "CRAFT" if "forj" in txt or "craft" in txt else "TREASURE"
        return _fill(model, {"route": route("loot"), "loot_context": ctx,
                             "reasoning": "[simulado] intenção de saque/comércio", "confidence": 0.85,
                             "target": None})
    if any(k in txt for k in npc):
        return _fill(model, {"route": route("npc_actor"), "target": random.choice(_NPC_NAMES),
                             "reasoning": "[simulado] intenção social", "confidence": 0.8,
                             "loot_context": None})
    return _fill(model, {"route": route("storyteller"), "reasoning": "[simulado] exploração",
                         "confidence": 0.8, "target": None, "loot_context": None})


_MOCK_FACTION_ID = "legiao_ferro"  # id real de data/factions.json (modo simulado)


def _story_update(model, messages):
    narrative = random.choice(_NARRATIVES).format(acao_eco=_acao_eco(messages))
    # Fase 2: sem chave, deixa a reputação reagir a palavras-chave (jogável offline).
    txt = _last_human(messages).lower()
    impacts = []
    if any(k in txt for k in ("ajud", "alia", "favor", "apoi")):
        impacts = [{"faction_id": _MOCK_FACTION_ID, "direction": "ajudou"}]
    elif any(k in txt for k in ("trai", "sabot", "ataco a", "contra a")):
        impacts = [{"faction_id": _MOCK_FACTION_ID, "direction": "prejudicou"}]
    # Fase 3.3: ~15% dos turnos propõe 1 missão (offline exercita validação/zeragem de
    # ids inválidos — location_id/origin_entity_id de propósito fora do grafo).
    quests = []
    if random.random() < 0.15:
        quests = [{"title": "Recuperar o medalhão perdido",
                   "description": "Um estranho pediu ajuda para achar uma relíquia.",
                   "origin_name": "Um estranho encapuzado", "origin_entity_id": "",
                   "location_id": "", "reward_hint": "algumas moedas"}]
    # Fase 5: se o prompt lista quests ATIVAS (bloco "- id=<id> · ..."), ~50% das
    # vezes propõe a CONCLUSÃO de uma delas. Sem isto o harness offline nunca
    # fecha quest (mock só criava, nunca completava — achado do playtest).
    proposed_events = []
    todo_texto = " ".join(str(getattr(m, "content", "") or "") for m in messages)
    quest_ids = re.findall(r"- id=(\S+) ·", todo_texto)
    if quest_ids and random.random() < 0.5:
        qid = random.choice(quest_ids)
        proposed_events = [{"type": "quest_completed", "target_id": qid,
                            "actor_id": "player", "payload": {"quest_id": qid}}]
    # Avança o beat ~30% das vezes para a UI de objetivos progredir no modo simulado.
    return _fill(model, {"narrative": narrative, "introduced_npcs": [],
                         "faction_impacts": impacts, "proposed_quests": quests,
                         "proposed_events": proposed_events,
                         "beat_completed": random.random() < 0.30})


_WORLD_RUMORS = [
    "Viajantes falam baixo de fumaça vista ao longe e de estradas que mudaram de dono.",
    "Um sino distante toca fora de hora; ninguém sabe dizer por quê.",
    "Mercadores chegam com menos do que partiram, e olham por sobre o ombro.",
    "Aves abandonaram os galhos numa direção só, como se algo as empurrasse.",
]


def _world_pulse(model, messages):
    return _fill(model, {"rumor": random.choice(_WORLD_RUMORS),
                         "fact": "Forças do mundo se moveram nos bastidores enquanto o tempo passava.",
                         "danger_shift": 0})


def _campaign_plan(model, messages):
    return _fill(model, {"location": "Terras Cinzentas",
                         "beats": list(_BEATS),
                         "climax": "Um confronto final contra a verdade enterrada no local.",
                         # Fase 3.1: título estável (não fragmenta capítulos no modo simulado)
                         "arc_title": "A Verdade Enterrada"})


_BARD_LINES = [
    "E assim, sob o céu de chumbo, o herói cravou aço em carne e a sombra recuou — por ora.",
    "Cantam agora os corvos o que os tolos não ousam: que naquele ermo um nome foi forjado em sangue.",
    "Diz-se que naquele instante o vento parou para ver o herói erguer-se sobre os caídos.",
    "Uma porta se abriu onde só havia pedra, e com ela um segredo velho como a fome.",
]


def _memory_update(model, messages):
    overrides = {"new_summary": "A jornada segue por terras sombrias; a tensão cresce.",
                 "important_facts": []}
    # ~45% dos turnos rendem uma linha de menestrel (para a Crônica progredir no modo simulado).
    if "chronicle_entry" in getattr(model, "model_fields", {}) and random.random() < 0.45:
        overrides["chronicle_entry"] = random.choice(_BARD_LINES)
    return _fill(model, overrides)


def _player_stats(model, messages):
    attrs = {k: random.randint(9, 15) for k in ["str", "dex", "con", "int", "wis", "cha"]}
    return _fill(model, {"attributes": attrs,
                         "inventory": ["Espada Gasta", "Capa Esfarrapada", "Ração de Viagem"],
                         "flavor_abilities": ["Golpe Firme", "Olhar Atento"]})


def _npc_schema(model, messages):
    name = random.choice(_NPC_NAMES)
    return _fill(model, {"name": name, "role": random.choice(_NPC_ROLES),
                         "persona": "Desconfiado, cansado, fala pouco e cobra caro.",
                         "appearance": "Figura encapuzada de olhos atentos.",
                         "location": "Terras Cinzentas",
                         "attributes": {"str": 10, "dex": 11, "con": 10, "int": 12, "wis": 13, "cha": 11},
                         "combat_stats": {"hp": 12, "ac": 11, "attacks": []}})


def _npc_response(model, messages):
    # Não-onisciência: se o jogador perguntar de fações/rumores, o NPC "revela" algo (offline).
    txt = _last_human(messages).lower()
    reveals = []
    if any(k in txt for k in ("facç", "faccao", "facc", "rumor", "quem manda", "legi", "ordem")):
        reveals = [{"faction_id": "legiao_ferro", "reveal_level": "objetivo"}]
    return _fill(model, {"dialogue": random.choice(_NPC_LINES),
                         "action_description": random.choice(_NPC_ACTIONS),
                         "memory_update": "Conversou com o herói.",
                         "relationship_change": random.choice([-1, 0, 0, 1]),
                         "faction_reveals": reveals})


def _enemy_schema(model, messages):
    name = random.choice(_ENEMY_NAMES)
    hp = random.randint(12, 26)
    atk_cls = _list_item_cls(model, "attacks")
    attacks = []
    if atk_cls:
        attacks = [_fill(atk_cls, {"name": "Ataque", "type": "melee", "bonus": 3,
                                   "damage": "1d6+1", "range": "1.5m", "save_dc": None})]
    return _fill(model, {"name": name, "description": "Criatura hostil das ruínas.",
                         "type": "Minion", "hp": hp, "max_hp": hp, "ac": 12,
                         "attacks": attacks,
                         "attributes": {"str": 12, "dex": 11, "con": 11, "int": 6, "wis": 8, "cha": 6},
                         "abilities": [], "loot": []})


def _encounter_scanner(model, messages):
    hint = _last_human(messages) or "Inimigo"
    name = next((n for n in _ENEMY_NAMES if n.lower() in hint.lower()), random.choice(_ENEMY_NAMES))
    item_cls = _list_item_cls(model, "detected_enemies")
    detected = [_fill(item_cls, {"name": name, "count": random.randint(1, 2)})] if item_cls else []
    return _fill(model, {"detected_enemies": detected,
                         "flavor_text": f"{name} surge das sombras, rosnando."})


def _loot_schema(model, messages):
    item_cls = _list_item_cls(model, "items")
    items = []
    if item_cls:
        nm, iid, typ = random.choice(_ITEM_NAMES)
        items = [_fill(item_cls, {"name": nm, "item_id": iid, "description": "Achado nas ruínas.",
                                  "type": typ, "rarity": "common", "gold_value": random.randint(5, 40),
                                  "combat_stats": {}, "mechanics": {}})]
    return _fill(model, {"items": items, "gold": random.randint(5, 50),
                         "narrative": "Você vasculha os destroços e encontra algo de valor."})


def _item_generation(model, messages):
    nm, iid, typ = random.choice(_ITEM_NAMES)
    return _fill(model, {"name": nm, "item_id": iid, "description": "Item simulado.",
                         "type": typ, "rarity": "common", "gold_value": random.randint(5, 40),
                         "combat_stats": {}, "mechanics": {}})


def _transaction(model, messages):
    return _fill(model, {"success": True, "message": "O mercador resmunga, mas fecha negócio.",
                         "items_to_remove": [], "gold_cost": 0, "new_item": None})


def _ruling(model, messages):
    return _fill(model, {"is_allowed": True, "dice_formula": "1d20+2",
                         "mechanical_effect": "Efeito padrão (simulado).",
                         "flavor_text": "Ação resolvida pelas regras."})


def _entity_match(model, messages):
    return _fill(model, {"match_found": False, "existing_id": None})


def _trade_intent(model, messages):
    """Fase 4.4: intenção de comércio por palavra-chave (offline)."""
    txt = _last_human(messages).lower()
    mode = "buy"
    if any(w in txt for w in ("vend", "negoci minha", "ofereço")):
        mode = "sell"
    elif any(w in txt for w in ("forj", "cri", "fabric", "melhor", "temper", "destil")):
        mode = "craft"
    # item_ref: casa nome de artefato/receita conhecido dentro da fala
    ref = txt.strip()[:60] or "item"
    try:
        import unicodedata

        def _fold(s):
            n = unicodedata.normalize("NFKD", str(s))
            return "".join(c for c in n if not unicodedata.combining(c)).lower()

        from gamedata import ARTIFACTS_DB, load_json_data
        folded_txt = _fold(txt)
        candidates = [a.get("name", "") for a in ARTIFACTS_DB.values()]
        candidates += [rid.replace("_", " ") for rid in (load_json_data("recipes.json") or {})]
        for nm in sorted(candidates, key=len, reverse=True):
            if nm and _fold(nm) in folded_txt:
                ref = nm
                break
    except Exception:
        pass
    return _fill(model, {"mode": mode, "item_ref": ref, "qty": 1})


def _combat_action(model, messages):
    """Identifica a ação de combate por palavra-chave (offline, determinístico)."""
    txt = _last_human(messages).lower()
    ability_id = "ataque_basico"
    try:
        from gamedata import ABILITIES
        for aid, a in ABILITIES.items():
            nm = str(a.get("name", "")).lower()
            if (aid.replace("_", " ") in txt) or (nm and nm in txt):
                ability_id = aid
                break
    except Exception:
        pass
    return _fill(model, {"ability_id": ability_id, "target": "",
                         "is_allowed": True, "reason": "[simulado]"})


def _start_scenario(model, messages):
    """spec inicio-personalizado (R10): fixture fixa válida em pt-BR com 1 NPC
    semeado — a suíte offline exercita endpoint e seed de ponta a ponta."""
    npc_cls = _list_item_cls(model, "seed_npcs")
    npcs = []
    if npc_cls:
        npcs = [_fill(npc_cls, {
            "name": "Mestre Aldric",
            "role": "mentor endividado",
            "attitude": "aliado",
            "persona": "Velho mercenário que deve um favor antigo à família do herói; "
                       "direto, protetor, fala pouco e cobra menos ainda.",
        })]
    return _fill(model, {
        "prologue": "Você chega com pouco mais que o nome que carrega e uma dívida "
                    "que não é sua. A estrada ficou para trás; a cidade à frente não "
                    "promete nada — e é exatamente por isso que você veio. Alguém aqui "
                    "sabe de onde você veio. Resta descobrir quem, e quanto isso custa.",
        "opening_scene_brief": "O herói chega ao local inicial no fim da tarde; um "
                               "conhecido do passado o aguarda com um aviso e uma "
                               "proposta. Tensão: alguém o seguiu até aqui.",
        "arc_title": "Dívidas de Sangue",
        "beats": [
            "Apresente Mestre Aldric e o aviso que ele carrega.",
            "O jogador descobre quem o seguiu até a região.",
            "Uma escolha: pagar a dívida antiga ou enfrentá-la.",
        ],
        "climax": "O confronto com o credor do passado — em aço ou em palavras.",
        "seed_npcs": npcs,
    })


_DISPATCH = {
    "RouterDecision": _route_decision,
    "StoryUpdate": _story_update,
    "WorldPulse": _world_pulse,
    "CampaignPlanModel": _campaign_plan,
    "MemoryUpdate": _memory_update,
    "PlayerStatsSchema": _player_stats,
    "NPCSchema": _npc_schema,
    "NPCResponse": _npc_response,
    "EnemySchema": _enemy_schema,
    "EncounterScanner": _encounter_scanner,
    "LootSchema": _loot_schema,
    "ItemGeneration": _item_generation,
    "TransactionResult": _transaction,
    "Ruling": _ruling,
    "EntityMatch": _entity_match,
    "CombatAction": _combat_action,
    "TradeIntent": _trade_intent,
    "StartScenario": _start_scenario,
}


# --------------------------------------------------------------------------
# O cliente simulado
# --------------------------------------------------------------------------
class _StructuredMock:
    def __init__(self, model):
        self.model = model

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, messages):
        builder = _DISPATCH.get(getattr(self.model, "__name__", ""))
        if builder:
            return builder(self.model, messages)
        return _fill(self.model, {})  # genérico para schemas não mapeados


class MockLLM:
    """Substitui ChatGoogleGenerativeAI quando não há API key. Sem rede."""

    is_fallback = False  # não é o fallback de erro; produz conteúdo válido
    is_mock = True

    def __init__(self, temperature: float = 0.7):
        self.temperature = temperature

    def bind_tools(self, *_a, **_k):
        return self

    def with_structured_output(self, model, *_a, **_k):
        return _StructuredMock(model)

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, messages):
        # invoke "puro" (narrativa direta): sem tool_calls
        return AIMessage(content=random.choice(_NARRATIVES).format(acao_eco=_acao_eco(messages)))

    def stream(self, messages):
        """Yield AIMessage para compatibilidade com chamadas streaming."""
        yield self.invoke(messages)
