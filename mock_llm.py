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
            # SPEC-223 R5: a entrada chega delimitada; o mock lê o texto cru
            # (fixtures não dependem do delimitador).
            from services.prompt_guard import unwrap_player_input

            return unwrap_player_input(getattr(m, "content", ""))
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

    if origin in (list, list):
        return []
    if origin in (dict, dict):
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

    combat = [
        "atac",
        "golpe",
        "luto",
        "luta",
        "mato",
        "mata",
        "espada",
        "lâmina",
        "lamina",
        "soco",
        "chute",
        "dispar",
        "flecha",
        "enfrent",
        "mira",
        "esfaque",
    ]
    npc = [
        "fal",
        "pergunt",
        "convers",
        "cumpriment",
        "negoci",
        "saúd",
        "saud",
        "respond",
        "grit",
        "digo",
        "peço",
        "peco",
    ]
    loot = [
        "peg",
        "vasculh",
        "baú",
        "bau",
        "saque",
        "loot",
        "recolh",
        "abro",
        "compr",
        "vend",
        "forj",
        "craft",
    ]

    if any(k in txt for k in combat):
        return _fill(
            model,
            {
                "route": route("combat_agent"),
                "target": "Inimigo",
                "reasoning": "[simulado] intenção de combate",
                "confidence": 0.9,
                "loot_context": None,
            },
        )
    if any(k in txt for k in loot):
        ctx = (
            "SHOP"
            if ("compr" in txt or "vend" in txt)
            else "CRAFT"
            if "forj" in txt or "craft" in txt
            else "TREASURE"
        )
        return _fill(
            model,
            {
                "route": route("loot"),
                "loot_context": ctx,
                "reasoning": "[simulado] intenção de saque/comércio",
                "confidence": 0.85,
                "target": None,
            },
        )
    if any(k in txt for k in npc):
        explicit_target = next((name for name in _NPC_NAMES if name.lower() in txt), None)
        return _fill(
            model,
            {
                "route": route("npc_actor"),
                "target": explicit_target or random.choice(_NPC_NAMES),
                "reasoning": "[simulado] intenção social",
                "confidence": 0.8,
                "loot_context": None,
            },
        )
    return _fill(
        model,
        {
            "route": route("storyteller"),
            "reasoning": "[simulado] exploração",
            "confidence": 0.8,
            "target": None,
            "loot_context": None,
        },
    )


_MOCK_FACTION_ID = "legiao_ferro"  # id real de data/factions.json (modo simulado)

# SPEC-299: o mock só emite `crime_claims` com léxico EXPLÍCITO (os 14 perfis do playtest
# não usam estas frases, então não mudam). Não consome `random`.
_MOCK_CRIME_RE = re.compile(
    r"\b(?:roubo\s+a\s+bolsa|furto|esfaqueio\s+(?:o|a)\s+(?P<victim>\w+)|"
    r"quebro\s+a\s+(?:vitrine|janela))\b"
)


def _mock_crime_claims(messages) -> list:
    m = _MOCK_CRIME_RE.search(_last_human(messages).lower())
    if not m:
        return []
    word = m.group(0)
    if word.startswith("esfaqueio"):
        return [{"crime_type": "agressao", "victim": (m.group("victim") or "").title()}]
    if word.startswith("quebro"):
        return [{"crime_type": "dano_propriedade", "victim": "local"}]
    return [{"crime_type": "furto", "victim": "local", "covert": True}]


_MOCK_MEMBERSHIP_FACTIONS = {
    "legi": "legiao_ferro",
    "druidas": "druidas_ciclo_cinzento",
    "kahen": "poder_kahen",
    "pirata": "grupos_piratas_rivais",
    "anões": "ultimos_anoes_reino",
    "anoes": "ultimos_anoes_reino",
    "nômades": "bandos_nomades",
    "nomades": "bandos_nomades",
    "cidades": "cidades_estado_sobreviventes_vaelorn_solvhen",
}


def _mock_membership(txt: str) -> dict | None:
    """SPEC-301: o mock só propõe vínculo quando o jogador PEDE explicitamente
    (perfil `faccionario`); sem pedido, o campo fica vazio como no LLM real."""
    action = ""
    if any(k in txt for k in ("me alist", "quero entrar", "ingresso n")):
        action = "join"
    elif any(k in txt for k in ("deixo a ", "deixo o ", "abandono a ", "saio d")):
        action = "leave"
    elif any(k in txt for k in ("peço uma missão", "peco uma missao", "tem alguma missão")):
        action = "ask_mission"
    if not action:
        return None
    fid = next((v for k, v in _MOCK_MEMBERSHIP_FACTIONS.items() if k in txt), "")
    return {"action": action, "faction_id": fid} if fid else None


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
    todo_texto = " ".join(str(getattr(m, "content", "") or "") for m in messages)
    if random.random() < 0.15:
        # SPEC-223: missão dada AQUI aponta para o local da cena (id do bloco
        # <ENTIDADES_CANONICAS>), para o progresso Python poder prová-la.
        loc_match = re.search(r"- id=(\S+) · [^\n]*· location", todo_texto)
        quests = [
            {
                "title": "Recuperar o medalhão perdido",
                "description": "Um estranho pediu ajuda para achar uma relíquia.",
                "origin_name": "Um estranho encapuzado",
                "origin_entity_id": "",
                "location_id": loc_match.group(1) if loc_match else "",
                "reward_hint": "algumas moedas",
            }
        ]
    # Fase 5: se o prompt lista quests ATIVAS (bloco "- id=<id> · ..."), ~50% das
    # vezes propõe a CONCLUSÃO de uma delas. Sem isto o harness offline nunca
    # fecha quest (mock só criava, nunca completava — achado do playtest).
    proposed_events = []
    quests_match = re.search(
        r"<QUESTS_ATIVAS>(.*?)</QUESTS_ATIVAS>",
        todo_texto,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # SPEC-223 R1: LLM bem-comportado só propõe conclusão de quest PROVADA
    # ("prova: ok"); sem o marcador (prompt legado) mantém o comportamento antigo.
    bloco = quests_match.group(1) if quests_match else ""
    quest_ids = (
        re.findall(r"- id=(\S+) ·[^\n]*prova: ok", bloco)
        if "prova:" in bloco
        else re.findall(r"- id=(\S+) ·", bloco)
    )
    if quest_ids and random.random() < 0.5:
        qid = random.choice(quest_ids)
        proposed_events = [
            {
                "type": "quest_completed",
                "target_id": qid,
                "actor_id": "player",
                "payload": {"quest_id": qid},
            }
        ]
    # Avança o beat ~30% das vezes para a UI de objetivos progredir no modo simulado.
    return _fill(
        model,
        {
            "narrative": narrative,
            "introduced_npcs": [],
            "faction_impacts": impacts,
            "membership_action": _mock_membership(txt),
            "proposed_quests": quests,
            "proposed_events": proposed_events,
            "crime_claims": _mock_crime_claims(messages),
            "beat_completed": random.random() < 0.30,
        },
    )


_WORLD_RUMORS = [
    "Viajantes falam baixo de fumaça vista ao longe e de estradas que mudaram de dono.",
    "Um sino distante toca fora de hora; ninguém sabe dizer por quê.",
    "Mercadores chegam com menos do que partiram, e olham por sobre o ombro.",
    "Aves abandonaram os galhos numa direção só, como se algo as empurrasse.",
]


def _world_pulse(model, messages):
    return _fill(
        model,
        {
            "rumor": random.choice(_WORLD_RUMORS),
            "fact": "Forças do mundo se moveram nos bastidores enquanto o tempo passava.",
            "danger_shift": 0,
        },
    )


def _world_day_narration(model, messages):
    """SPEC-302 R26: reescreve so os FATOS dados (linhas `FATO: ...` do prompt)."""
    content = " ".join(str(getattr(m, "content", "")) for m in messages)
    facts = [ln[5:].strip() for ln in content.splitlines() if ln.strip().startswith("FATO:")]
    return _fill(model, {"text": " ".join(facts) or "O dia passou sem novidades."})


def _campaign_plan(model, messages):
    return _fill(
        model,
        {
            "location": "Terras Cinzentas",
            "beats": list(_BEATS),
            "climax": "Um confronto final contra a verdade enterrada no local.",
            # Fase 3.1: título estável (não fragmenta capítulos no modo simulado)
            "arc_title": "A Verdade Enterrada",
        },
    )


_BARD_LINES = [
    "E assim, sob o céu de chumbo, o herói cravou aço em carne e a sombra recuou — por ora.",
    "Cantam agora os corvos o que os tolos não ousam: que naquele ermo um nome foi forjado em sangue.",
    "Diz-se que naquele instante o vento parou para ver o herói erguer-se sobre os caídos.",
    "Uma porta se abriu onde só havia pedra, e com ela um segredo velho como a fome.",
]


def _memory_update(model, messages):
    overrides = {
        "new_summary": "A jornada segue por terras sombrias; a tensão cresce.",
        "important_facts": [],
    }
    # ~45% dos turnos rendem uma linha de menestrel (para a Crônica progredir no modo simulado).
    if "chronicle_entry" in getattr(model, "model_fields", {}) and random.random() < 0.45:
        overrides["chronicle_entry"] = random.choice(_BARD_LINES)
    return _fill(model, overrides)


def _player_stats(model, messages):
    attrs = {k: random.randint(9, 15) for k in ["str", "dex", "con", "int", "wis", "cha"]}
    return _fill(
        model,
        {
            "attributes": attrs,
            "inventory": ["Espada Gasta", "Capa Esfarrapada", "Ração de Viagem"],
            "flavor_abilities": ["Golpe Firme", "Olhar Atento"],
        },
    )


def _npc_schema(model, messages):
    name = random.choice(_NPC_NAMES)
    return _fill(
        model,
        {
            "name": name,
            "role": random.choice(_NPC_ROLES),
            "persona": "Desconfiado, cansado, fala pouco e cobra caro.",
            "appearance": "Figura encapuzada de olhos atentos.",
            "location": "Terras Cinzentas",
            "attributes": {"str": 10, "dex": 11, "con": 10, "int": 12, "wis": 13, "cha": 11},
            "combat_stats": {"hp": 12, "ac": 11, "attacks": []},
        },
    )


def _mock_lore_quest(messages) -> list[dict]:
    """SPEC-313 R34: com `<GANCHOS_POSSIVEIS>` no prompt, o NPC simulado oferece o PRIMEIRO item
    do menu (determinístico), para o playtest offline cobrir oferta -> conclusao."""
    blob = "\n".join(str(getattr(m, "content", "")) for m in messages or [])
    if "<GANCHOS_POSSIVEIS>" not in blob:
        return []
    rows = re.findall(r"- kind=(\w+) anchor_id=(\S+)", blob.split("<GANCHOS_POSSIVEIS>", 1)[1])
    if not rows:
        return []
    ask = _last_human(messages).lower()
    wanted = next(
        (k for key, k in (("entreg", "entregar_material"), ("escolt", "escoltar")) if key in ask),
        "",
    )
    kind, anchor = next((r for r in rows if r[0] == wanted), rows[0])
    return [
        {
            "title": "Um pedido do mundo",
            "description": "",
            "origin_name": "",
            "origin_entity_id": "",
            "location_id": "",
            "reward_hint": "",
            "kind": kind,
            "anchor_id": anchor,
        }
    ]


def _npc_response(model, messages):
    # Não-onisciência: se o jogador perguntar de fações/rumores, o NPC "revela" algo (offline).
    txt = _last_human(messages).lower()
    reveals = []
    if any(k in txt for k in ("facç", "faccao", "facc", "rumor", "quem manda", "legi", "ordem")):
        reveals = [{"faction_id": "legiao_ferro", "reveal_level": "objetivo"}]
    friendly = any(k in txt for k in ("elogio", "amizade", "confian", "parceria"))
    quests = []
    if re.search(r"\b(?:tarefa|miss[aã]o|trabalho|favor)\s+concret[oa]\b", txt):
        quests = [
            {
                "title": "Investigar o silêncio das estradas",
                "description": "Descobrir por que viajantes desapareceram perto da cidade.",
                "origin_name": "",
                "origin_entity_id": "",
                "location_id": "",
                "reward_hint": "informação e algumas moedas",
            }
        ]
    quests = _mock_lore_quest(messages) or quests
    return _fill(
        model,
        {
            "dialogue": random.choice(_NPC_LINES),
            "action_description": random.choice(_NPC_ACTIONS),
            "memory_update": "Conversou com o herói.",
            "relationship_change": 1 if friendly else random.choice([-1, 0, 0, 1]),
            "faction_reveals": reveals,
            "membership_action": _mock_membership(txt),
            "proposed_quests": quests,
            "crime_claims": _mock_crime_claims(messages),
        },
    )


def _enemy_schema(model, messages):
    name = random.choice(_ENEMY_NAMES)
    return _fill(
        model,
        {
            "name": name,
            "description": "Criatura hostil das ruínas.",
            "categoria": "lacaio",
            "arquetipo": "agil",
            "estilo_ataque": "corpo_a_corpo",
            "nome_ataque": "Ataque",
            "abilities": [],
            "loot": [],
            "regions": [],
        },
    )


_MOCK_NUCLEOS = (
    "Rastejador",
    "Cardume",
    "Ruminante",
    "Sentinela",
    "Ceifeiro",
    "Escavador",
    "Pastor",
    "Remoedor",
    "Batedor",
    "Vigia",
    "Mordedor",
    "Bebedor",
    "Coletor",
    "Tecelão",
    "Carregador",
    "Farejador",
)
_MOCK_COMPLEMENTOS = (
    "de Cinza Fria",
    "de Sal Grosso",
    "do Poço Seco",
    "de Casca Parda",
    "da Lama Funda",
    "de Junta Torta",
    "do Fosso",
    "de Pele Rota",
)
_MOCK_PARTES = (
    ("mandíbula", "torta"),
    ("garras", "curtas"),
    ("olhos", "leitosos"),
    ("costelas", "aparentes"),
    ("cauda", "pelada"),
    ("dentes", "serrilhados"),
    ("patas", "nodosas"),
    ("ombros", "caídos"),
    ("pescoço", "comprido"),
    ("língua", "áspera"),
)


def _linha_de_eixos_do_prompt(system: str):
    """SPEC-374 R10: com <eixos_livres> numerado o mock escolhe a linha 1 (o motor escreve os
    eixos). Devolve ``escolha | None`` (com a chave ``linha``)."""
    import re

    from services import bestiary_lint as bl

    escolha = None
    livres_bloco = re.search(r"<eixos_livres>\n(.*?)\n</eixos_livres>", system, re.S)
    for linha in livres_bloco.group(1).splitlines() if livres_bloco else []:
        m_lin = re.match(r"(\d+)\. (.+)$", linha)
        vals = [v.strip() for v in m_lin.group(2).split(" / ")] if m_lin else []
        if len(vals) == 6:
            escolha = {
                "anatomia": dict(zip(bl.EIXOS_PADRAO_ENUM, vals[:5], strict=True)),
                "papel_tatico": vals[5],
                "linha": int(m_lin.group(1)),
            }
            break
    return escolha


def _ficha_criatura_gerada(model, messages):
    """SPEC-361 R31: ficha determinística (hash do pedido) que passa no gate U1-U13.

    Escolhe eixos livres contra as fichas da região (mesma fonte do gate) e contra as linhas
    de ``<ja_existem_na_regiao>`` do prompt; nunca gera número nem termo proibido."""
    import hashlib
    import itertools
    import re

    from services import bestiary_lint as bl
    from services import creature_gen as cg
    from services import enemy_decks
    from services.encounter_manifest import name_tokens

    system = next((str(m.content) for m in messages if m.__class__.__name__ == "SystemMessage"), "")
    pedido = _last_human(messages)
    m_reg = re.search(r"<regiao>\n[^\n]*\((\w+)\)", system)
    regiao = m_reg.group(1) if m_reg else ""
    h = int(hashlib.sha256(f"{pedido}|{regiao}".encode()).hexdigest(), 16)

    vizinhos = cg.fichas_da_regiao(regiao)
    bloco = re.search(r"<ja_existem_na_regiao>\n(.*?)\n</ja_existem_na_regiao>", system, re.S)
    for linha in bloco.group(1).splitlines() if bloco else []:
        parts = [p.strip() for p in re.split(r" — | / ", linha)]
        if len(parts) == 8:
            eixos = ("plano_corporal", "material", "escala", "locomocao", "percepcao")
            vizinhos.append(
                {
                    "nome": parts[0],
                    "anatomia": dict(zip(eixos, parts[2:7], strict=True)),
                    "papel_tatico": parts[7],
                }
            )
    nucleos = {bl.nucleo_nome(v.get("nome") or "") for v in vizinhos}
    triplas = {bl._triple(v) for v in vizinhos}

    def ordenado(eixo: str, salto: int) -> list[str]:
        vals = sorted(bl.ENUMS[eixo])
        k = (h >> salto) % len(vals)
        return vals[k:] + vals[:k]

    escolha = _linha_de_eixos_do_prompt(system)
    combos = itertools.product(
        ordenado("plano_corporal", 3),
        ordenado("material", 7),
        ordenado("papel_tatico", 11),
        ordenado("escala", 13),
        ordenado("locomocao", 17),
        ordenado("percepcao", 19),
    )
    for plano, mat, papel, esc, loc, perc in itertools.islice(combos, 0 if escolha else 20000):
        if plano == "sessil_ancorado" or loc == "ancorada":
            continue
        cand = {
            "anatomia": {
                "plano_corporal": plano,
                "material": mat,
                "escala": esc,
                "locomocao": loc,
                "percepcao": perc,
            },
            "papel_tatico": papel,
        }
        if bl._triple(cand) in triplas:
            continue
        if any(bl.eixos_iguais(cand, v) > bl.MAX_EIXOS_IGUAIS for v in vizinhos):
            continue
        escolha = cand
        break
    escolha = escolha or {
        "anatomia": {
            "plano_corporal": "radial",
            "material": "cera_sebo",
            "escala": "miuda",
            "locomocao": "rola",
            "percepcao": "respiracao",
        },
        "papel_tatico": "suporte",
    }
    bestiary_tokens = {
        tuple(sorted(set(name_tokens(e.get("name", ""))))) for e in (_bestiary_db() or {}).values()
    }
    nome = "Coisa Parda"
    for i in range(len(_MOCK_NUCLEOS) * len(_MOCK_COMPLEMENTOS)):
        nucleo = _MOCK_NUCLEOS[(h + i) % len(_MOCK_NUCLEOS)]
        comp = _MOCK_COMPLEMENTOS[(h // 7 + i) % len(_MOCK_COMPLEMENTOS)]
        cand_nome = f"{nucleo} {comp}"
        if bl.nucleo_nome(cand_nome) in nucleos:
            continue
        if tuple(sorted(set(name_tokens(cand_nome)))) in bestiary_tokens:
            continue
        nome = cand_nome
        break
    fam = cg.familia_alvo(pedido) or bl.FAMILIAS_VALORIA[h % 4]
    fonte = {"corpo_reescrito": "abismo", "besta_entropia": "abismo", "humanoide_preco": "eter"}
    demonio = sorted(bl.DEMONIOS)[h % len(bl.DEMONIOS)] if fam == "demonio_encarnado" else None
    cat_m = re.search(r"<categoria_pedida>(\w+)</categoria_pedida>", system)
    categoria = cat_m.group(1) if cat_m else "padrao"
    a_cada_n = cg.A_CADA_N.get(categoria, 3)
    usados = {
        (tuple(v.get("padrao") or []), v.get("a_cada_n")) for v in vizinhos if v.get("padrao")
    }
    slots = sorted(enemy_decks._SLOT_LABEL)
    padrao = ["ataque", "mover"]
    for a, b, c in itertools.product(slots, slots, slots):
        cand_p = [a, b, c] if (h >> 5) % 2 else [a, b]
        if (tuple(cand_p), a_cada_n) not in usados and len(set(cand_p)) > 1:
            padrao = cand_p
            break
    p = [_MOCK_PARTES[(h >> (2 * i)) % len(_MOCK_PARTES)] for i in range(6)]
    p = list(dict.fromkeys(p))[:3]
    while len(p) < 3:
        p.append(_MOCK_PARTES[len(p) + 3])
    anat = escolha["anatomia"]
    texto = (
        f"Corpo de {anat['material'].replace('_', ' ')} com {p[0][0]} {p[0][1]}. "
        f"Tem {p[1][0]} {p[1][1]} e {p[2][0]} {p[2][1]}. "
        f"{'Anda por ' + anat['locomocao'].replace('_', ' ') if anat['locomocao'] != 'nada' else 'Vive nadando, de nadadeiras moles'}"
        " e acha a presa pelo "
        f"{anat['percepcao'].replace('_', ' ')}."
    )
    return _fill(
        model,
        {
            "nome": nome,
            "familia": fam,
            "origem_fonte": fonte.get(fam, "demonio"),
            "demonio": demonio,
            "faccao": None,
            **anat,
            "linha_eixos": (escolha or {}).get("linha", 1),
            "anatomia_texto": texto,
            "silhueta": f"Vulto {anat['escala']} de {p[0][0]} à mostra, rente ao chão.",
            "comportamento": f"Ronda o lugar de onde veio e só ataca quem chega perto do {p[1][0]}.",
            "papel_tatico": escolha["papel_tatico"],
            "arquetipo": enemy_decks.FAMILIAS[h % len(enemy_decks.FAMILIAS)],
            "categoria": categoria,
            "estilo_ataque": "corpo_a_corpo",
            "nome_ataque": f"Golpe de {p[0][0].capitalize()}",
            "padrao": padrao,
            "telegrafo": f"{{nome}} encolhe {'as' if p[1][0].endswith('s') else 'a'} {p[1][0]} e range.",
            "mecanica_assinatura": "Fica firme e devolve o golpe seguinte.",
            "contra_jogo": f"Mirar {('as' if p[2][0].endswith('s') else 'a')} {p[2][0]} antes do resto.",
            "gancho": "Dizem na estrada que apareceu depois do último temporal.",
            "description": f"Criatura de {anat['material'].replace('_', ' ')} que ronda o lugar.",
            "aparencia": f"{p[0][0].capitalize()} {p[0][1]}, {p[1][0]} {p[1][1]}, couro sem brilho.",
            "arte_visual": f"Vulto de {p[0][0]} {p[0][1]} sob luz baixa de lanterna.",
            "arte_evitar": "Monstro de desenho animado, cores vivas.",
        },
    )


def _bestiary_db() -> dict:
    try:
        import gamedata

        return dict(gamedata.BESTIARY or {})
    except Exception:
        return {}


def _encounter_scanner(model, messages):
    hint = _last_human(messages) or "Inimigo"
    name = next((n for n in _ENEMY_NAMES if n.lower() in hint.lower()), random.choice(_ENEMY_NAMES))
    item_cls = _list_item_cls(model, "detected_enemies")
    detected = [_fill(item_cls, {"name": name, "count": random.randint(1, 2)})] if item_cls else []
    return _fill(
        model, {"detected_enemies": detected, "flavor_text": f"{name} surge das sombras, rosnando."}
    )


def _loot_schema(model, messages):
    item_cls = _list_item_cls(model, "items")
    items = []
    if item_cls:
        nm, iid, typ = random.choice(_ITEM_NAMES)
        items = [
            _fill(
                item_cls,
                {
                    "name": nm,
                    "item_id": iid,
                    "description": "Achado nas ruínas.",
                    "type": typ,
                    "rarity": "common",
                    "gold_value": random.randint(5, 40),
                    "combat_stats": {},
                    "mechanics": {},
                },
            )
        ]
    return _fill(
        model,
        {
            "items": items,
            "gold": random.randint(5, 50),
            "narrative": "Você vasculha os destroços e encontra algo de valor.",
        },
    )


def _item_generation(model, messages):
    nm, iid, typ = random.choice(_ITEM_NAMES)
    return _fill(
        model,
        {
            "name": nm,
            "item_id": iid,
            "description": "Item simulado.",
            "type": typ,
            "rarity": "common",
            "gold_value": random.randint(5, 40),
            "combat_stats": {},
            "mechanics": {},
        },
    )


def _transaction(model, messages):
    return _fill(
        model,
        {
            "success": True,
            "message": "O mercador resmunga, mas fecha negócio.",
            "items_to_remove": [],
            "gold_cost": 0,
            "new_item": None,
        },
    )


def _ruling(model, messages):
    return _fill(
        model,
        {
            "is_allowed": True,
            "dice_formula": "1d20+2",
            "mechanical_effect": "Efeito padrão (simulado).",
            "flavor_text": "Ação resolvida pelas regras.",
        },
    )


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
    card_id = ""
    try:
        from services.cards import all_cards

        for aid, a in all_cards().items():
            nm = str(a.get("name", "")).lower()
            if (aid.replace("_", " ") in txt) or (nm and nm in txt):
                card_id = aid
                break
    except Exception:
        pass
    return _fill(
        model, {"kind": "card" if card_id else "attack", "card_id": card_id, "target_id": ""}
    )


def _start_scenario(model, messages):
    """spec inicio-personalizado (R10): fixture fixa válida em pt-BR com 1 NPC
    semeado — a suíte offline exercita endpoint e seed de ponta a ponta."""
    prompt = "\n".join(str(getattr(m, "content", "")) for m in messages)
    threaded = _start_scenario_threaded(model, prompt)
    if threaded is not None:
        return threaded
    npc_cls = _list_item_cls(model, "seed_npcs")
    npcs = []
    if npc_cls:
        npcs = [
            _fill(
                npc_cls,
                {
                    "name": "Mestre Aldric",
                    "role": "mentor endividado",
                    "attitude": "aliado",
                    "persona": "Velho mercenário que deve um favor antigo à família do herói; "
                    "direto, protetor, fala pouco e cobra menos ainda.",
                },
            )
        ]
    return _fill(
        model,
        {
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
            "personal_npc": None,
        },
    )


def _start_scenario_threaded(model, prompt: str):
    """SPEC-351: com <PORTAS_DE_TRAMA> no prompt, devolve âncoras VÁLIDAS (1ª porta, 1º NPC)
    e 1 NPC pessoal com camada pública limpa — o offline exercita E1–E7."""
    import re

    doors = re.findall(r"^- id=(\S+) \| ([^—\n]+?)(?: —.*)?$", prompt, re.MULTILINE)
    if not doors or "personal_npc" not in model.model_fields:
        return None
    door_id, door_name = doors[0]
    npc_ids = re.findall(r"^- entity_id=(\S+) \| (.+?)(?: \(.*\))?$", prompt, re.MULTILINE)
    npc_cls = _list_item_cls(model, "seed_npcs")
    personal_cls = typing.get_args(model.model_fields["personal_npc"].annotation)[0]
    personal = _fill(
        personal_cls,
        {
            "name": "Mestre Aldric",
            "role_public": "mercenário aposentado",
            "persona_public": "Velho mercenário de fala curta, que cobra pouco e lembra de tudo.",
            "appearance": "Ombros largos, uma cicatriz cinza atravessando a sobrancelha.",
            "legend": "Dizem que nunca perdeu um contrato, só o sono.",
            "bond": "Deve um favor antigo à família do herói.",
            "attitude": "aliado",
        },
    )
    plot_id = npc_ids[0][0] if npc_ids else ""
    return _fill(
        model,
        {
            "prologue": f"Você chega a esta terra carregando uma dívida que não é sua. "
            f"Corre uma conversa baixa por aqui: {door_name.strip()}. "
            "Você quer saber a fundo o que há de verdade nisso, e o que isso vai custar. "
            "Alguém na cidade já sabe que você está procurando.",
            "opening_scene_brief": "O herói chega ao local inicial no fim da tarde, ouvindo "
            f"a conversa sobre {door_name.strip()}; um conhecido o aguarda com um aviso.",
            "arc_title": "Dívidas de Sangue",
            "beats": [
                "Apresente o conhecido e o aviso que ele carrega.",
                f"O herói encontra o primeiro sinal concreto de {door_name.strip()}.",
                "Uma escolha: seguir o rastro ou pagar a dívida antiga.",
            ],
            "climax": "Um acerto de contas na borda da história, em aço ou em palavras.",
            "seeking": "descobrir a verdade sobre a conversa que corre na cidade",
            "thread_refs": [door_id],
            "plot_npc_id": plot_id,
            "plot_npc_hook": "Cruza o caminho do herói quando ele começa a perguntar."
            if plot_id
            else "",
            "personal_npc": personal,
            "seed_npcs": [] if npc_cls is None else [],
        },
    )


_DISPATCH = {
    "RouterDecision": _route_decision,
    "StoryUpdate": _story_update,
    "StoryUpdateWithRumors": _story_update,  # SPEC-312 P2-1
    "WorldPulse": _world_pulse,
    "WorldDayNarration": _world_day_narration,
    "CampaignPlanModel": _campaign_plan,
    "MemoryUpdate": _memory_update,
    "PlayerStatsSchema": _player_stats,
    "NPCSchema": _npc_schema,
    "NPCResponse": _npc_response,
    "EnemySchema": _enemy_schema,
    "FichaCriaturaGerada": _ficha_criatura_gerada,  # SPEC-361 R31
    "FichaCriaturaGeradaEixosLivres": _ficha_criatura_gerada,  # SPEC-374 R10 (região saturada)
    "CorrecaoFicha": lambda model, messages: model(),  # SPEC-361 R16: correção vazia
    "CorrecaoFichaEixosLivres": lambda model, messages: model(),
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

    # SPEC-319 R9: mesmo resultado do invoke, com deltas fatiados a partir do MESMO texto.
    _DELTA_SIZES = (3, 7, 12, 5, 9)

    def stream_structured(self, messages, schema, *, on_delta=None, on_reset=None, key=None):
        result = _StructuredMock(schema).invoke(messages)
        if on_delta is not None:
            from services.partial_narrative import NarrativeExtractor

            extractor = NarrativeExtractor(key)
            raw = result.model_dump_json()
            pos = 0
            step = 0
            while pos < len(raw):
                size = self._DELTA_SIZES[step % len(self._DELTA_SIZES)]
                step += 1
                piece = extractor.feed(raw[pos : pos + size])
                pos += size
                if piece:
                    on_delta(piece)
        return result

    def stream_text(self, messages, *, on_delta=None, on_reset=None):
        result = self.invoke(messages)
        if on_delta is not None:
            text = str(result.content)
            for pos in range(0, len(text), 8):
                on_delta(text[pos : pos + 8])
        return result
