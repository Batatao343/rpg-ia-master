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
# Migração
# ==========================================================================
def migrate_creature(cre) -> dict:
    import gamedata
    name = cre.get("name", "")
    categoria = TYPE_TO_CATEGORIA.get(cre.get("type", ""), "padrao")
    arche = infer_archetype(cre)
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
    cre["resistances"] = res["resistances"]
    cre["vulnerabilities"] = res["vulnerabilities"]
    cre["immunities"] = res["immunities"]

    cartas = list(dict.fromkeys(lib["cartas"] + theme_cards(name)))
    cre["cartas"] = cartas

    cre["tactical_profile"] = {"priorities": [dict(p) for p in lib["priorities"]]}
    return cre


def main() -> int:
    import gamedata  # noqa: F401 (garante DATA_DIR/tabelas carregadas)
    with open(BEST, encoding="utf-8") as f:
        best = json.load(f)

    for cid, cre in best.items():
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
