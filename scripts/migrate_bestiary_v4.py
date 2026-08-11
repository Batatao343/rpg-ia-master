"""Migra data/bestiary.json para o schema de Conflitos v2 (spec conflito-15).

ADITIVO até o cutover (conflito-13): mantém os campos antigos (hp/ac/attacks/
behavior) para o combate atual seguir rodando, e ACRESCENTA os campos novos —
`categoria`, `virtudes`, Vitalidade/Ferimento por Corpo (conflito-01), armadura/
resistências tipadas (conflito-05), `cartas` (com pelo menos 1 Carta assinatura
OCULTA, conflito-08 R7-R9) e um `tactical_profile` RICO por arquétipo
(conflito-08), não mais 1 de 4 perfis fixos.

Automatiza o que é inferível (categoria, Virtudes das attributes, arquétipo do
perfil/tipo/nome); a autoria de julgamento (biblioteca de arquétipos + Cartas de
inimigo) vive AQUI, curada, não como placeholder. Só toca o arquivo CURADO
(data/bestiary.json), nunca o overlay runtime (isolar-cache-runtime).

Uso: uv run python scripts/migrate_bestiary_v4.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.environ.get("RPG_ROOT", ".")
DATA = os.path.join(ROOT, "data")
BEST = os.path.join(DATA, "bestiary.json")

# Tipos de dano válidos (conflito-05 / gamedata) — resistências só usam estes.
DANO_FISICO = ("cortante", "perfurante", "impactante")
DANO_SOBRENATURAL = ("igneo", "gelido", "eletrico", "arcano", "corrosivo", "abissal")
DANO_VALIDO = set(DANO_FISICO + DANO_SOBRENATURAL)

# Categorias canônicas (death_flow.FULL_FLOW_CATEGORIES etc.).
TYPE_TO_CATEGORIA = {
    "Minion": "lacaio", "Elite": "elite", "BOSS": "chefe",
    "Monstrosidade (Gigante)": "chefe", "Humanoid (Human)": "nomeado",
}
# Piso de Corpo por categoria (garante Vitalidade coerente com o papel).
CORPO_FLOOR = {"lacaio": 0, "padrao": 2, "elite": 3, "chefe": 4, "nomeado": 3}


# ==========================================================================
# Cartas de inimigo (data/cards/bestiario.json). origem=conflito-15.
# Toda criatura recebe a Carta ASSINATURA do seu arquétipo (oculta até o 1º
# uso) + Cartas temáticas por palavra-chave. Catálogo fechado de efeito.
# ==========================================================================
def _ecard(cid, name, efeito, *, tipo="ativa", custo=0, freq="cena",
           oculta=False, desc=""):
    c = {"id": cid, "name": name, "origem": "conflito-15", "classe": "Inimigo",
         "subclasse": "", "tipo": tipo, "patamar": "inicial",
         "custo_entropia": custo, "frequencia": freq, "virtude_permitida": [],
         "efeito": efeito, "descricao": desc}
    if oculta:
        c["oculta"] = True  # revelada só no 1º uso (conflito-08 R7-R9)
    return c


ENEMY_CARDS = [
    _ecard("bst_defesa_instintiva", "Defesa Instintiva",
           {"kind": "protecao", "valor": 1}, tipo="reacao", custo=0,
           freq="cena", desc="Um reflexo curto desvia o golpe que chegaria limpo."),
    # --- assinaturas de arquétipo (ocultas) ---
    _ecard("bst_bote_certeiro", "Bote Certeiro",
           {"kind": "dano", "categoria_arma": "leve", "dano_base": 8}, freq="cena",
           oculta=True, desc="O predador encontra a jugular exposta."),
    _ecard("bst_golpe_sombras", "Golpe das Sombras",
           {"kind": "dano", "categoria_arma": "leve", "dano_base": 6}, freq="cena",
           oculta=True, desc="Ataque vindo do escuro, antes de qualquer reação."),
    _ecard("bst_pancada_esmagadora", "Pancada Esmagadora",
           {"kind": "dano", "categoria_arma": "pesada", "dano_base": 10}, custo=2,
           freq="cena", oculta=True, desc="Um golpe que rebenta a guarda."),
    _ecard("bst_ordem_foco", "Ordem de Foco",
           {"kind": "marca", "valor": 2}, freq="cena", oculta=True,
           desc="Aponta o alvo a abater; o bando converge."),
    _ecard("bst_fuga_suja", "Fuga Suja",
           {"kind": "esconder", "valor": 1}, freq="cena", oculta=True,
           desc="Joga terra nos olhos e some na confusão."),
    _ecard("bst_furia_final", "Fúria Final",
           {"kind": "buff_dano", "valor": 4}, freq="cena", oculta=True,
           desc="Sem recuo possível, entrega tudo num último acesso."),
    _ecard("bst_uivo_comando", "Uivo de Comando",
           {"kind": "taunt", "valor": 3}, freq="cena", oculta=True,
           desc="Um brado que reorganiza a matilha em torno da presa."),
    _ecard("bst_descarga_arcana", "Descarga Arcana",
           {"kind": "dano", "categoria_arma": "marcial", "dano_base": 8}, custo=2,
           freq="cena", oculta=True, desc="Libera de uma vez a energia contida."),
    _ecard("bst_postura_muralha", "Postura de Muralha",
           {"kind": "protecao", "valor": 6}, freq="cena", oculta=True,
           desc="Fecha a passagem com o próprio corpo."),
    _ecard("bst_toque_gelido", "Toque Gélido da Morte",
           {"kind": "dot", "dano_base": 5, "duracao": 3}, freq="cena", oculta=True,
           desc="O frio do outro lado drena a vida devagar."),
    _ecard("bst_golpe_mestre", "Golpe de Mestre",
           {"kind": "dano", "categoria_arma": "pesada", "dano_base": 14}, custo=3,
           freq="cena", oculta=True, desc="O ápice de um predador que já matou muitos."),
    # --- temáticas por palavra-chave (algumas ocultas) ---
    _ecard("bst_sopro_gelido", "Sopro Gélido",
           {"kind": "dot", "dano_base": 4, "duracao": 3, "dano_tipo": "gelido"},
           freq="cena", oculta=True, desc="Uma lufada que congela os pulmões."),
    _ecard("bst_baforada_ignea", "Baforada Ígnea",
           {"kind": "dano", "categoria_arma": "marcial", "dano_base": 8, "dano_tipo": "igneo"},
           custo=2, freq="cena", oculta=True, desc="Fogo cuspido em arco."),
    _ecard("bst_mordida_infecciosa", "Mordida Infecciosa",
           {"kind": "dot", "dano_base": 3, "duracao": 4, "dano_tipo": "corrosivo"},
           freq="turno", desc="A ferida apodrece antes de fechar."),
    _ecard("bst_teia", "Teia Prendedora",
           {"kind": "aplicar_condicao", "condicao": "enraizado", "duracao": 2},
           freq="cena", desc="Prende a presa no lugar."),
    _ecard("bst_bafo_acido", "Bafo Ácido",
           {"kind": "dano", "categoria_arma": "marcial", "dano_base": 6, "dano_tipo": "corrosivo"},
           freq="turno", desc="Cospe uma gosma que corrói metal e carne."),
    _ecard("bst_petrificar", "Olhar que Endurece",
           {"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 1},
           freq="cena", oculta=True, desc="Por um instante o corpo vira pedra."),
    _ecard("bst_grito_terror", "Grito de Terror",
           {"kind": "aplicar_condicao", "condicao": "amedrontado", "duracao": 2},
           freq="cena", oculta=True, desc="Um som que não deveria existir."),
    # --- conflito-17: assinaturas regionais ---
    _ecard("bst_fuligem_arcadia", "Pulmão de Fuligem",
           {"kind": "aplicar_condicao", "condicao": "cego", "duracao": 1},
           freq="turno", oculta=True, desc="A fuligem de Nova Arcádia apaga olhos e lampiões."),
    _ecard("bst_lodo_melancolia", "Lodo da Melancolia",
           {"kind": "dot", "dano_base": 2, "duracao": 4, "dano_tipo": "corrosivo"},
           freq="cena", oculta=True, desc="O pântano continua corroendo mesmo depois do contato."),
    _ecard("bst_vidro_zhur", "Estilhaço de Zhur",
           {"kind": "dano", "categoria_arma": "versatil", "dano_base": 9, "dano_tipo": "perfurante"},
           custo=2, freq="cena", oculta=True, desc="Vidro solar atravessa juntas antes de se partir."),
    _ecard("bst_sussurro_thessavar", "Sussurro de Thessavar",
           {"kind": "marca", "valor": 4}, freq="cena", oculta=True,
           desc="A floresta escolhe uma presa e passa seu nome de folha em folha."),
    _ecard("bst_esporo_xylos", "Nuvem Hospedeira",
           {"kind": "aplicar_condicao", "condicao": "enraizado", "duracao": 2},
           custo=1, freq="cena", oculta=True, desc="Esporos de Xylos costuram pés, solo e vontade."),
    _ecard("bst_noite_skallgard", "Noite no Sangue",
           {"kind": "buff_dano", "valor": 5}, custo=2, freq="cena", oculta=True,
           desc="A noite de Skallgard endurece a fome e o golpe."),
    _ecard("bst_eter_aethelgard", "Vazamento de Aethelgard",
           {"kind": "dot", "dano_base": 5, "duracao": 2, "dano_tipo": "arcano"},
           custo=2, freq="cena", oculta=True, desc="Éter destilado escapa por uma fissura que não estava ali."),
    _ecard("bst_mare_ophidia", "Maré de Ophidia",
           {"kind": "empurrao", "valor": 3}, freq="cena", oculta=True,
           desc="Uma onda curta arrasta a formação para onde o recife quer."),
    _ecard("bst_osso_costa", "Rosário de Ossos",
           {"kind": "protecao", "valor": 5}, custo=1, freq="cena", oculta=True,
           desc="Ossos da Costa Negra se fecham como uma segunda caixa torácica."),
    _ecard("bst_eco_montanhas", "Eco Cortante",
           {"kind": "dano", "categoria_arma": "marcial", "dano_base": 7, "dano_tipo": "cortante"},
           custo=1, freq="turno", oculta=True, desc="A montanha devolve o golpe por um ângulo impossível."),
    _ecard("bst_poeira_pradaria", "Passo na Poeira Antiga",
           {"kind": "reposicionar", "valor": 2}, freq="turno", oculta=True,
           desc="Ruínas e capim escondem uma rota que só a criatura reconhece."),
    _ecard("bst_sino_brekmar", "Sino de Dívida",
           {"kind": "taunt", "valor": 5}, custo=1, freq="cena", oculta=True,
           desc="O som de Brekmar faz cada credor olhar para o mesmo devedor."),
    # --- conflito-17: variação tática por arquétipo/elemento ---
    _ecard("bst_sangrar_alcateia", "Sangrar para a Alcateia",
           {"kind": "marca", "valor": 3}, freq="turno", oculta=True,
           desc="O primeiro corte vira cheiro e o cheiro vira ordem de caça."),
    _ecard("bst_casca_reativa", "Casca Reativa",
           {"kind": "contra_ataque", "dano_base": 3}, tipo="reacao", freq="turno",
           oculta=True, desc="A carapaça estilhaça contra quem golpeia de perto."),
    _ecard("bst_saliva_paralisante", "Saliva Paralisante",
           {"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 1},
           custo=1, freq="turno", oculta=True, desc="A mordida entrega um segundo de paralisia absoluta."),
    _ecard("bst_coro_colmeia", "Coro da Colmeia",
           {"kind": "buff_acerto", "valor": 4}, custo=2, freq="cena", oculta=True,
           desc="Muitas vozes ajustam o ataque como se fossem uma mente."),
    _ecard("bst_carregar_ruina", "Carregar pela Ruína",
           {"kind": "reposicionar", "valor": 3}, custo=1, freq="cena", oculta=True,
           desc="A criatura atravessa cobertura e leva a presa junto."),
    _ecard("bst_mimetismo_morto", "Mimetismo Morto",
           {"kind": "esconder", "valor": 3}, freq="turno", oculta=True,
           desc="Imita matéria sem vida até o instante da emboscada."),
    _ecard("bst_fenda_sonica", "Fenda Sônica",
           {"kind": "dano", "categoria_arma": "leve", "dano_base": 5, "dano_tipo": "impactante"},
           custo=1, freq="turno", oculta=True, desc="Um estalo abre dor por dentro da armadura."),
    _ecard("bst_roubar_calor", "Roubar Calor",
           {"kind": "buff_defesa", "valor": 4}, custo=1, freq="cena", oculta=True,
           desc="O calor drenado endurece a criatura e deixa o alvo tremendo."),
    _ecard("bst_ordem_quebrar", "Ordem: Quebrar a Linha",
           {"kind": "empurrao", "valor": 4}, custo=2, freq="cena", oculta=True,
           desc="Um comando curto transforma o bando numa cunha viva."),
]


# ==========================================================================
# Biblioteca de arquétipos táticos (conflito-08). Cada um: priorities ORDENADAS
# (a 1ª cujo gatilho vale prevalece) cobrindo alvo/recuo/fuga/rendição, +
# cartas assinatura, + resistências/imunidades temáticas opcionais.
# Gatilhos = flags que a fiação do cutover-13 computa no scene_state.
# ==========================================================================
def P(trigger, hint, tipo="obrigatorio", resistance="flexivel", blocks=None):
    return {"trigger": trigger, "tipo": tipo, "action_hint": hint,
            "resistance": resistance, "blocks": blocks or []}


ARQUETIPOS = {
    "predador": {
        "priorities": [
            P("alvo_vulneravel", "Persegue e abate o alvo mais ferido ou isolado."),
            P("muito_ferido", "A caçada virou risco de morte: recua e foge."),
            P("sempre", "Avança sobre o inimigo mais próximo com fúria animal."),
        ],
        "cartas": ["bst_bote_certeiro"],
    },
    "emboscador": {
        "priorities": [
            P("descoberto", "Descoberto, recua para a ocultação antes de atacar de novo."),
            P("muito_ferido", "Foge pelas sombras se ferido demais."),
            P("sempre", "Ataca da ocultação o alvo desprevenido e some."),
        ],
        "cartas": ["bst_golpe_sombras"],
    },
    "bruto": {
        "priorities": [
            P("muito_ferido", "Só recua à beira da morte; caso contrário avança.", resistance="resistente"),
            P("sempre", "Investe no inimigo mais próximo e o esmaga corpo a corpo."),
        ],
        "cartas": ["bst_pancada_esmagadora"],
    },
    "tatico": {
        "priorities": [
            P("cercado", "Cercado e ferido, recua em ordem ou tenta render-se."),
            P("alvo_vulneravel", "Concentra fogo no alvo mais perigoso ou já ferido."),
            P("muito_ferido", "Recua para posição defensável e reagrupa."),
            P("sempre", "Usa o terreno e ataca o alvo mais ameaçador."),
        ],
        "cartas": ["bst_ordem_foco"],
    },
    "covarde_oportunista": {
        "priorities": [
            P("sozinho", "Sem aliados, rende-se ou implora pela vida."),
            P("muito_ferido", "Foge assim que ferido — não morre por ninguém."),
            P("alvo_vulneravel", "Ataca só com vantagem numérica ou pelas costas."),
            P("sempre", "Hesita e mantém distância, buscando a saída."),
        ],
        "cartas": ["bst_fuga_suja"],
    },
    "fanatico": {
        "priorities": [
            P("sempre", "Luta até a morte; não foge, não se rende.", resistance="absoluta"),
        ],
        "cartas": ["bst_furia_final"],
    },
    "lider_matilha": {
        "priorities": [
            P("matilha_quebrada", "Se a matilha quebra, recua e reagrupa ou foge."),
            P("alvo_vulneravel", "Aponta e concentra o bando no alvo mais frágil."),
            P("sempre", "Coordena os aliados e chama reforço quando pode."),
        ],
        "cartas": ["bst_uivo_comando"],
    },
    "conjurador": {
        "priorities": [
            P("cercado", "Engajado corpo a corpo, recua para retomar a distância."),
            P("muito_ferido", "Foge se a linha de frente cair e ficar exposto."),
            P("sempre", "Mantém distância e controla o campo à distância."),
        ],
        "cartas": ["bst_descarga_arcana"],
    },
    "guardiao": {
        "priorities": [
            P("muito_ferido", "Defende o posto até cair; recua um passo, nunca o abandona.", resistance="resistente"),
            P("sempre", "Ataca quem se aproxima do que guarda; não persegue além do posto."),
        ],
        "cartas": ["bst_postura_muralha"],
    },
    "morto_vivo_implacavel": {
        "priorities": [
            P("sempre", "Avança sem medo nem hesitação; não foge, não se rende.", resistance="absoluta"),
        ],
        "cartas": ["bst_toque_gelido"],
    },
    "predador_apice": {
        "priorities": [
            P("plano_falhou", "Se o plano ruir e estiver à beira da morte, recua para lutar outro dia."),
            P("alvo_vulneravel", "Abate primeiro quem sustenta o grupo (curador/conjurador)."),
            P("sempre", "Comanda a cena e guarda a Carta assinatura para o momento decisivo."),
        ],
        "cartas": ["bst_golpe_mestre"],
    },
}

# Resistências/imunidades temáticas por palavra-chave (conflito-05 R3).
TEMA_RESIST = [
    (("gelo", "gélid", "gelid", "geleira", "yeti", "titã de gelo", "tita de gelo",
      "verme do gelo", "vidro"), {"immunities": ["gelido"]}),
    (("chama", "ígne", "igne", "fogo", "elemental de fogo"), {"immunities": ["igneo"]}),
    (("esqueleto", "múmia", "mumia", "zumbi", "afogado", "espectro", "fantasma",
      "carniçal", "carnical", "eco", "os que voltaram", "sereia", "espectro élfico"),
     {"resistances": {"perfurante": "resistencia"}}),
    (("golem", "constructo", "gárgula", "gargula", "sentinela de ferro", "blindado",
      "cristal", "casco"), {"resistances": {"cortante": "resistencia"}}),
    (("ooze", "esgoto", "ácido", "acido", "lodo", "gosma", "fungo", "fúngico", "fungico"),
     {"resistances": {"corrosivo": "resistencia"}}),
]

# Cartas temáticas extras por palavra-chave (variedade, R8).
TEMA_CARTA = [
    (("gelo", "gélid", "gelid", "geleira", "yeti", "titã de gelo"), "bst_sopro_gelido"),
    (("chama", "ígne", "igne", "fogo", "wyvern", "djinn"), "bst_baforada_ignea"),
    (("rato", "peste", "canibal", "carniçal", "sanguessuga", "morcego"), "bst_mordida_infecciosa"),
    (("aranha", "teia", "vinha", "estrangul", "raiz", "flora"), "bst_teia"),
    (("ácido", "acido", "sapo", "polvo", "ooze", "esgoto", "lixo"), "bst_bafo_acido"),
    (("basilisco", "gazer", "observador", "olhar"), "bst_petrificar"),
    (("espectro", "fantasma", "lamento", "névoa", "nevoa", "arauto", "fumaça", "fumaca"),
     "bst_grito_terror"),
]


# ==========================================================================
# Inferência
# ==========================================================================
UNDEAD = ("esqueleto", "múmia", "mumia", "zumbi", "afogado", "espectro", "fantasma",
          "carniçal", "carnical", "morto", "cadáver", "cadaver", "eco", "os que voltaram",
          "minotauro esqueleto", "sereia de ophidia")
CONSTRUCT = ("golem", "constructo", "gárgula", "gargula", "sentinela de ferro",
             "sentinela hospedeiro", "blindado", "estátua", "estatua")
CASTER_NAME = ("necromante", "arcanista", "druida", "cultista", "djinn", "sereia",
               "iniciado da chama", "destilação", "destilacao")
AMBUSH = ("assassino", "sombra", "espreitadora", "silenciador", "saqueador", "ladra",
          "mergulhador")
GUARD_NAME = ("sentinela", "guardião", "guardiao", "protetor", "capturador", "muralha")
BEAST = ("lobo", "urso", "aranha", "verme", "morcego", "sapo", "tubarão", "tubarao",
         "caranguej", "cabra", "gaivota", "polvo", "escorpião", "escorpiao", "yeti",
         "wyvern", "basilisco", "troll", "serpente", "víbora", "vibora", "sanguessuga",
         "predador", "carangue", "raiz", "flora", "vinha", "come nas praias")


def _has(name, needles):
    n = name.lower()
    return any(x in n for x in needles)


def infer_archetype(cre) -> str:
    name = cre.get("name", "")
    ctype = cre.get("type", "")
    prof = (cre.get("behavior") or {}).get("profile", "")
    atk_types = {a.get("type") for a in (cre.get("attacks") or [])}
    is_caster = bool({"magic", "ranged"} & atk_types) or _has(name, CASTER_NAME)

    if ctype == "BOSS" or ctype.startswith("Monstrosidade"):
        return "predador_apice"
    if _has(name, UNDEAD) and prof == "implacavel":
        return "morto_vivo_implacavel"
    if _has(name, CONSTRUCT) or _has(name, GUARD_NAME):
        return "guardiao"
    if prof == "covarde":
        return "covarde_oportunista"
    if prof == "tatico":
        if is_caster:
            return "conjurador"
        if _has(name, AMBUSH):
            return "emboscador"
        if _has(name, ("soldado", "capitão", "capitao", "legião", "legiao", "pirata",
                       "bandido", "orc", "arpoador", "renegado", "nômade", "nomade")):
            return "lider_matilha"
        return "tatico"
    if prof == "implacavel":
        if is_caster:
            return "conjurador"
        return "bruto"
    if prof == "feroz":
        if _has(name, BEAST):
            return "predador"
        return "bruto"
    return "bruto"


def _virt_bucket(a) -> int:
    a = int(a or 0)
    return 0 if a <= 5 else 1 if a <= 8 else 2 if a <= 11 else 3 if a <= 14 else 4 if a <= 17 else 5


def infer_virtudes(cre, categoria) -> dict:
    at = cre.get("attributes") or {}
    v = {
        "forca": _virt_bucket(at.get("str", 10)),
        "agilidade": _virt_bucket(at.get("dex", 10)),
        "corpo": _virt_bucket(at.get("con", 10)),
        "mente": _virt_bucket((int(at.get("int", 10)) + int(at.get("wis", 10))) // 2),
        "carisma": _virt_bucket(at.get("cha", 10)),
    }
    floor = CORPO_FLOOR.get(categoria, 0)
    if v["corpo"] < floor:
        v["corpo"] = floor
    return v


def theme_resist(name):
    out = {"resistances": {}, "vulnerabilities": [], "immunities": []}
    for needles, spec in TEMA_RESIST:
        if _has(name, needles):
            for t, src in (spec.get("resistances") or {}).items():
                if t in DANO_VALIDO:
                    out["resistances"][t] = src
            for t in spec.get("immunities", []):
                if t in DANO_VALIDO and t not in out["immunities"]:
                    out["immunities"].append(t)
    return out


def theme_cards(name):
    return [cid for needles, cid in TEMA_CARTA if _has(name, needles)]


# ==========================================================================
# conflito-17 — 40 criaturas novas, todas ancoradas a uma região/hub do Codex.
# A tabela compacta é a fonte autoral; `_build_new_creatures` só materializa o
# schema legado mínimo antes de a MESMA pipeline v4 abaixo completar a ficha.
# ==========================================================================
REGION_CARD = {
    "nova_arcadia": "bst_fuligem_arcadia",
    "pantano_melancolia": "bst_lodo_melancolia",
    "deserto_zhur": "bst_vidro_zhur",
    "floresta_sussurros": "bst_sussurro_thessavar",
    "selva_xylos": "bst_esporo_xylos",
    "skallgard": "bst_noite_skallgard",
    "aethelgard": "bst_eter_aethelgard",
    "ophidia": "bst_mare_ophidia",
    "costa_negra": "bst_osso_costa",
    "montanhas_afiadas": "bst_eco_montanhas",
    "pradaria_ruinas": "bst_poeira_pradaria",
    "brekmar": "bst_sino_brekmar",
}
TACTIC_CARDS = (
    "bst_sangrar_alcateia", "bst_casca_reativa", "bst_saliva_paralisante",
    "bst_coro_colmeia", "bst_carregar_ruina", "bst_mimetismo_morto",
    "bst_fenda_sonica", "bst_roubar_calor", "bst_ordem_quebrar",
)

# id, nome, região, categoria, arquétipo, ataque, potência, âncora de lore
NEW_CREATURE_SPECS = [
    ("mon_rato_caldeira", "Rato de Caldeira", "nova_arcadia", "lacaio", "emboscador", "Mordida de Rebite", "1d4", "Nidifica sob as caldeiras do Anel de Ferro e mastiga rebites ainda quentes."),
    ("mon_cao_rebite", "Cão de Rebite", "nova_arcadia", "padrao", "predador", "Mandíbula de Aço", "1d8", "Fareja óleo e sangue nas vielas fabris patrulhadas pela Legião de Ferro."),
    ("mon_automato_fundicao", "Autômato de Fundição", "nova_arcadia", "elite", "guardiao", "Malho Hidráulico", "2d8", "Um molde de guerra abandonado pelos Encapuzados da Fornalha ainda guarda seu forno."),
    ("mon_mosquito_eter", "Mosquito de Éter", "pantano_melancolia", "lacaio", "covarde_oportunista", "Ferrão Translúcido", "1d4", "Enxames bebem o Éter que aflora entre raízes e cadáveres do Pântano da Melancolia."),
    ("mon_viuva_lodo", "Viúva do Lodo", "pantano_melancolia", "padrao", "emboscador", "Quelíceras de Turfa", "1d8", "Tece ninhos nos marcos afundados dos druidas do Ciclo Cinzento."),
    ("mon_cervo_afogado", "Cervo Afogado", "pantano_melancolia", "elite", "morto_vivo_implacavel", "Galhada Encharcada", "2d8", "Carrega nos chifres oferendas de peregrinos que nunca voltaram da água negra."),
    ("mon_escaravelho_vidro", "Escaravelho de Vidro", "deserto_zhur", "lacaio", "guardiao", "Pinça Solar", "1d4", "Seu casco nasce dos cacos que as tempestades de Zhur vitrificam nas dunas."),
    ("mon_hiena_sol", "Hiena do Sol Partido", "deserto_zhur", "padrao", "lider_matilha", "Riso Mordente", "1d8", "Segue as caravanas dos Devoradores de Sol esperando a última sombra desaparecer."),
    ("mon_colosso_duna", "Colosso de Duna Oca", "deserto_zhur", "elite", "bruto", "Punho de Areia", "2d10", "Uma armadura vazia movida pelo vento que sopra da Borda do Vazio."),
    ("mon_mariposa_sussurro", "Mariposa do Sussurro", "floresta_sussurros", "lacaio", "covarde_oportunista", "Pó de Sono", "1d4", "Repete em suas asas palavras que Thessavar ainda não pronunciou."),
    ("mon_cacador_casca", "Caçador de Casca", "floresta_sussurros", "padrao", "emboscador", "Lança-Raiz", "1d8", "Fica imóvel entre troncos até a floresta decidir quem atravessou sem permissão."),
    ("mon_ent_dormindo", "Ent que Sonha Acordado", "floresta_sussurros", "elite", "guardiao", "Braço de Carvalho", "2d8", "Suas raízes guardam um sonho anterior à escuridão que cobriu a floresta."),
    ("mon_larva_hospedeira", "Larva Hospedeira", "selva_xylos", "lacaio", "predador", "Incisão de Esporo", "1d4", "Procura um corpo para levar até as cidades suspensas da Colmeia."),
    ("mon_macaco_esporo", "Macaco de Esporo", "selva_xylos", "padrao", "tatico", "Pedra Micelial", "1d8", "Aprendeu a imitar os sinais manuais dos Hospedeiros e arma emboscadas nas copas."),
    ("mon_rainha_cipo", "Rainha-Cipó", "selva_xylos", "elite", "conjurador", "Chicote de Seiva", "2d8", "Uma planta consciente que negocia corpos com a Colmeia em troca de luz."),
    ("mon_corvo_gelo", "Corvo de Gelo Negro", "skallgard", "lacaio", "covarde_oportunista", "Bico de Geada", "1d4", "Rouba lascas de memória dos mortos deixados na noite eterna de Skallgard."),
    ("mon_lobo_aurora", "Lobo da Aurora Morta", "skallgard", "padrao", "predador", "Mordida Boreal", "1d8", "Caça sob uma aurora que os clãs tecnológicos juram ter desligado décadas atrás."),
    ("mon_jotun_cinza", "Jötunn de Cinza", "skallgard", "elite", "bruto", "Machado de Gelo", "2d10", "Um gigante coberto pela cinza das máquinas térmicas soterradas no gelo."),
    ("mon_faisca_destilacao", "Faísca da Destilação", "aethelgard", "lacaio", "conjurador", "Arco Instável", "1d4", "Fragmento vivo do experimento que derrubou Aethelgard e ainda procura um recipiente."),
    ("mon_vigia_caco", "Vigia de Caco", "aethelgard", "padrao", "guardiao", "Lâmina Prismática", "1d8", "Patrulha corredores élficos quebrados repetindo a última ordem do Conselho."),
    ("mon_quimera_cristal", "Quimera de Cristal Destilado", "aethelgard", "elite", "predador_apice", "Três Gargantas", "2d10", "Três animais fundidos pelo Éter de Aethelgard disputam o mesmo esqueleto transparente."),
    ("mon_caranguejo_cinza", "Caranguejo de Cinza", "ophidia", "lacaio", "guardiao", "Pinça Vulcânica", "1d4", "Reveste a carapaça com cinza das ilhas vulcânicas de Ophidia."),
    ("mon_moreia_vulcanica", "Moreia Vulcânica", "ophidia", "padrao", "emboscador", "Bote de Enxofre", "1d8", "Vive em tubos de lava inundados e ataca barcos pelo calor dos remos."),
    ("mon_oraculo_coral", "Oráculo de Coral", "ophidia", "elite", "conjurador", "Canto de Maré", "2d8", "Uma colônia que responde perguntas com correntes capazes de afogar o consulente."),
    ("mon_carrapato_osso", "Carrapato de Osso", "costa_negra", "lacaio", "predador", "Broca Calcária", "1d4", "Escava as ossadas titânicas da Costa Negra e veste fragmentos dos antigos donos."),
    ("mon_saqueador_marfim", "Saqueador de Marfim", "costa_negra", "padrao", "tatico", "Arpão Serrilhado", "1d8", "Segue mapas Osshari gravados em presas que ninguém admite ter vendido."),
    ("mon_baleia_ossario", "Filhote de Baleia-Ossário", "costa_negra", "elite", "bruto", "Cauda de Costela", "2d10", "Nada sob areia e ossos, emergindo quando o Éter faz a maré recuar."),
    ("mon_goblin_eco", "Goblin de Eco", "montanhas_afiadas", "lacaio", "covarde_oportunista", "Picareta Ressonante", "1d4", "Mineradores goblins o criaram para encontrar túneis; ele aprendeu a fechá-los."),
    ("mon_cabra_labirinto", "Cabra do Labirinto", "montanhas_afiadas", "padrao", "predador", "Chifrada Angular", "1d8", "Conhece passagens nas Montanhas Afiadas que não existem no mesmo lugar duas vezes."),
    ("mon_guardiao_basalto", "Guardião de Basalto", "montanhas_afiadas", "elite", "guardiao", "Punho Sísmico", "2d10", "Uma sentinela anã sem mestre protege a estrada para o reino subterrâneo perdido."),
    ("mon_gafanhoto_runa", "Gafanhoto de Runa", "pradaria_ruinas", "lacaio", "tatico", "Mandíbula Inscrita", "1d4", "Devora inscrições das cidades caídas e carrega fragmentos de magia no casco."),
    ("mon_cavaleiro_sem_rosto", "Cavaleiro sem Rosto", "pradaria_ruinas", "padrao", "morto_vivo_implacavel", "Lança sem Brasão", "1d8", "Ainda patrulha a fronteira de uma cidade-estado cujo nome foi apagado."),
    ("mon_auroque_ruinas", "Auroque das Ruínas", "pradaria_ruinas", "elite", "lider_matilha", "Investida de Coluna", "2d10", "Seu rebanho derruba colunas antigas para lamber o sal das fundações."),
    ("mon_rato_cais_brekmar", "Rato de Cais de Brekmar", "brekmar", "lacaio", "covarde_oportunista", "Dente de Moeda", "1d4", "Reconhece moedas falsas pelo gosto e morde primeiro quem as carrega."),
    ("mon_cobrador_gancho", "Cobrador do Gancho", "brekmar", "padrao", "tatico", "Gancho de Cobrança", "1d8", "Uma criatura treinada pelos sindicatos para trazer devedores vivos ao Porto Sem Lei."),
    ("mon_capita_corda", "Capitã da Corda Molhada", "brekmar", "elite", "lider_matilha", "Sabre de Convés", "2d8", "Pirata afogada que ainda comanda uma tripulação presa às próprias amarras."),
    ("mon_locomotiva_penitente", "Locomotiva Penitente", "nova_arcadia", "chefe", "predador_apice", "Ariete de Fornalha", "3d10", "Uma máquina da Legião de Ferro que ganhou fome ao transportar minério abissal."),
    ("mon_mae_micelio", "Mãe do Micélio Errante", "selva_xylos", "chefe", "conjurador", "Parto de Esporos", "3d8", "A memória coletiva da Colmeia rejeitou esta matriz, que agora cria hospedeiros próprios."),
    ("mon_leviata_caldeira", "Leviatã da Caldeira Azul", "ophidia", "chefe", "predador_apice", "Mandíbula de Maré", "3d10", "Dorme sob uma caldeira vulcânica de Ophidia e desperta quando a chama fica azul."),
    ("mon_eclipse_caminhante", "Eclipse Caminhante", "deserto_zhur", "chefe", "conjurador", "Sombra Solar", "3d8", "Os Devoradores do Sol o chamam de profecia; as caravanas chamam de fim da rota."),
]


def _build_new_creatures() -> dict:
    type_by_category = {
        "lacaio": "Minion", "padrao": "Standard", "elite": "Elite",
        "chefe": "BOSS",
    }
    creatures = {}
    for index, (cid, name, region, category, archetype, attack, damage, lore) in enumerate(NEW_CREATURE_SPECS):
        # Faixas diferentes geram Virtudes variadas sem escapar do domínio 0-5.
        attrs = {
            "str": 7 + (index % 4) * 3,
            "dex": 8 + ((index + 1) % 4) * 3,
            "con": 8 + ((index + 2) % 4) * 3,
            "int": 7 + ((index + 3) % 4) * 3,
            "wis": 8 + (index % 3) * 3,
            "cha": 6 + ((index + 2) % 4) * 3,
        }
        creatures[cid] = {
            "id": cid,
            "name": name,
            "description": lore,
            "type": type_by_category[category],
            "categoria": category,
            "arquetipo": archetype,
            "attributes": attrs,
            "attacks": [{"name": attack, "type": "melee", "damage": damage}],
            "abilities": [f"Assinatura regional: {lore}"],
            "loot": [f"Vestígio de {name}"],
            "regions": [region],
            "origem": "conflito-17",
            "cartas_autorais": [REGION_CARD[region], TACTIC_CARDS[index % len(TACTIC_CARDS)]],
        }
    return creatures


NEW_CREATURES = _build_new_creatures()


# ==========================================================================
# Migração
# ==========================================================================
def migrate_creature(cre) -> dict:
    import gamedata
    name = cre.get("name", "")
    categoria = (cre.get("categoria") if cre.get("categoria") in CORPO_FLOOR
                 else TYPE_TO_CATEGORIA.get(cre.get("type", ""), "padrao"))
    arche = (cre.get("arquetipo") if cre.get("arquetipo") in ARQUETIPOS
             else infer_archetype(cre))
    lib = ARQUETIPOS[arche]
    virtudes = infer_virtudes(cre, categoria)
    corpo = virtudes["corpo"]

    cre["categoria"] = categoria
    cre["arquetipo"] = arche
    cre["virtudes"] = virtudes
    cre["max_vitalidade"] = gamedata.vitalidade_para_corpo(corpo)
    cre["vitalidade"] = cre["max_vitalidade"]
    cre["ferimento_espacos"] = gamedata.espacos_ferimento_para_corpo(corpo)
    cre["ferimentos"] = {"leve": [], "grave": [], "critico": []}

    res = theme_resist(name)
    for damage_type, source in (cre.get("resistances_autorais") or {}).items():
        if damage_type in DANO_VALIDO:
            res["resistances"][damage_type] = source
    cre["resistances"] = res["resistances"]
    cre["vulnerabilities"] = res["vulnerabilities"]
    cre["immunities"] = res["immunities"]

    cartas = list(dict.fromkeys(
        lib["cartas"] + theme_cards(name) + list(cre.get("cartas_autorais") or [])
    ))
    cre["cartas"] = cartas

    cre["tactical_profile"] = {"priorities": [dict(p) for p in lib["priorities"]]}
    return cre


def main() -> int:
    import gamedata  # noqa: F401 (garante DATA_DIR/tabelas carregadas)
    with open(BEST, encoding="utf-8") as f:
        best = json.load(f)

    # Conteúdo aditivo: IDs existentes nunca são removidos nem sobrescritos.
    for cid, creature in NEW_CREATURES.items():
        if cid not in best or best[cid].get("origem") == "conflito-17":
            best[cid] = creature

    for cid, cre in best.items():
        cre.setdefault("id", cid)
        migrate_creature(cre)

    with open(BEST, "w", encoding="utf-8") as f:
        json.dump(best, f, ensure_ascii=False, indent=2)
    print(f"migradas {len(best)} criaturas -> schema v4")

    # cartas de inimigo
    os.makedirs(os.path.join(DATA, "cards"), exist_ok=True)
    ecpath = os.path.join(DATA, "cards", "bestiario.json")
    with open(ecpath, "w", encoding="utf-8") as f:
        json.dump({"_meta": "spec conflito-15: Cartas de inimigo (assinaturas de "
                            "arquétipo + temáticas). Gerado por scripts/migrate_bestiary_v4.py.",
                   "cards": ENEMY_CARDS}, f, ensure_ascii=False, indent=2)
    print(f"escrito {ecpath}: {len(ENEMY_CARDS)} cartas de inimigo")

    from collections import Counter
    ca = Counter(c["arquetipo"] for c in best.values())
    print("arquétipos:", dict(ca))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
