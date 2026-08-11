"""Gera o Acervo completo de Cartas de Valoria (spec conflito-14).

É a fonte autoral vigente que substituiu `data/player_abilities.json` (motor
removido) pelo schema de Carta da conflito-02, na ESCALA NOVA (2d10+Virtude,
dano-base flat 3/4/6/8 — doc 01 §19). Saída: um arquivo por classe em
`data/cards/` + o mapa de Cartas de Virtude sugeridas.

Roda uma vez; a saída é curada depois se preciso. Encoding UTF-8.

PRINCÍPIOS DE AUTORIA (R2/R3/R10):
- `efeito.kind` SEMPRE do catálogo fechado `services.cards.CARD_EFFECT_KINDS`.
- `dano` ancora `categoria_arma` -> `dano_base` = `DANO_BASE_ARMA[cat]` (+bônus
  pago em Entropia, nunca abaixo da base).
- Parity de dano puro custeado: `dano_base/custo` na banda 1.5–4.0 (mesmo método
  validado em `balanceamento-classes-pos-playtest`).
- Variedade: cada Carta é uma IDEIA de Valoria (a Postura diante do Abismo da
  classe), não um reskin de dano. Ruptura e Evolução A/B nas Cartas centrais.
"""
import json
import os

ROOT = os.environ.get("RPG_ROOT", ".")
DATA = os.path.join(ROOT, "data")
CARDS_DIR = os.path.join(DATA, "cards")

# Dano-base por categoria de arma (doc 01 §19) — precisa bater com services.cards.
BASE = {"leve": 3, "marcial": 4, "versatil": 6, "pesada": 8}


def dano(cat, bonus=0):
    """Efeito de dano ancorado na categoria de arma. `dano_base` = base + bônus."""
    return {"kind": "dano", "categoria_arma": cat, "dano_base": BASE[cat] + bonus}


# ==========================================================================
# Fonte autoral. Cada entrada: id, name, tipo, subclasse, patamar, custo,
# freq, virtudes permitidas, efeito, (ruptura), (evolucao), (gatilho).
# ==========================================================================
CARDS: dict = {}


def add(cid, name, classe, sub, patamar, tipo, efeito, *, custo=0,
        freq="livre", virt=None, ruptura=None, evolucao=None, gatilho=None,
        descricao="", central=False, mecanica=None, papel=None):
    c = {
        "id": cid, "name": name, "tipo": tipo, "origem": "conflito-14",
        "classe": classe, "subclasse": sub, "patamar": patamar,
        "custo_entropia": custo, "frequencia": freq,
        "virtude_permitida": virt or [], "efeito": efeito,
        "descricao": descricao,
    }
    if ruptura:
        c["ruptura"] = ruptura
    if evolucao:
        c["evolucao"] = evolucao
    if gatilho:
        c["gatilho"] = gatilho
    if central:
        c["central"] = True
    if mecanica:
        c["mecanica_classe"] = mecanica
    if papel:
        c["papel"] = papel
    CARDS[cid] = c


# ======================================================================
# DEVOTO DO ABISMO — tank que AMA a incerteza. Convite, muralha, luto.
# Virtude de arma: forca (pesada) / corpo. Postura: puxar o golpe para si.
# ======================================================================
D = "Devoto do Abismo"
# -- tronco --
add("dev_golpe_convite", "Golpe do Convite", D, "", "inicial", "ativa",
    dano("marcial"), virt=["forca"], descricao="Abre a guarda de propósito: o "
    "aço convida o inimigo a se aproximar do que ele deveria temer.")
add("dev_muralha_viva", "Muralha Viva", D, "", "inicial", "ativa",
    {"kind": "protecao", "valor": 3}, custo=2, freq="cena", virt=["corpo"],
    descricao="Planta os pés e vira anteparo de carne para os que estão atrás.")
add("dev_conviccao", "Convicção", D, "", "inicial", "passiva",
    {"kind": "buff_defesa", "valor": 1}, descricao="Quem não teme o Abismo não "
    "recua um passo — a guarda nunca abre por susto.")
add("dev_aguentar", "Aguentar", D, "", "inicial", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "suportar esforço/dor prolongada sem ceder"},
    freq="descanso_curto", descricao="O corpo aprende a hospedar sofrimento.")
add("dev_provocacao", "Provocação do Abismo", D, "", "avancado", "ativa",
    {"kind": "taunt", "valor": 2}, custo=2, freq="cena", virt=["carisma"],
    descricao="Chama o perigo pelo nome, e ele atende.")
add("dev_encaixe", "Encaixe do Golpe", D, "", "avancado", "reacao",
    {"kind": "contra_ataque", "dano_base": 4}, custo=1, freq="turno",
    gatilho="ao_ser_atacado", virt=["corpo"],
    descricao="Recebe o golpe no ombro certo e devolve com o cotovelo.")
add("dev_sentinela", "Sentinela do Fim", D, "", "superior", "ativa",
    dano("pesada", bonus=4), custo=3, freq="cena", virt=["forca"],
    descricao="Um único mandobre que sela a brecha e quebra a linha inimiga.")

# -- O Consagrado: ritualiza o amor ao Abismo; marca o corpo antes da luta --
add("dev_cons_marca", "Marca de Sangue Frio", D, "consagrado", "inicial", "ativa",
    {"kind": "marca", "valor": 1}, custo=1, freq="turno", virt=["carisma"],
    descricao="Risca no próprio antebraço o nome do inimigo — agora é pessoal.")
add("dev_cons_liturgia", "Liturgia da Espera", D, "consagrado", "avancado", "ativa",
    {"kind": "protecao", "valor": 4, "principal": True}, custo=3, freq="cena",
    virt=["corpo"], central=True,
    descricao="Cada respiração é um verso; a carne endurece no ritmo do cântico.",
    ruptura={"caminho_a": {"kind": "protecao", "valor": 8},
             "caminho_b": {"kind": "taunt", "valor": 4}},
    evolucao={"caminho_a": {"efeito": {"kind": "protecao", "valor": 6},
                            "ruptura": {"kind": "protecao", "valor": 10}},
              "caminho_b": {"efeito": {"kind": "protecao", "valor": 4},
                            "ruptura": {"kind": "taunt", "valor": 6}}})
add("dev_cons_estigma", "Estigma", D, "consagrado", "avancado", "passiva",
    {"kind": "buff_defesa", "valor": 2}, descricao="As cicatrizes rituais "
    "distribuem o impacto — o corpo virou relicário.")

# -- O Zeloso: amor possessivo; puxa aggro por ciúme --
add("dev_zel_ciume", "Ciúme do Abismo", D, "zeloso", "inicial", "ativa",
    {"kind": "taunt", "valor": 3}, custo=2, freq="turno", virt=["carisma"],
    descricao="Ninguém mais toca no que é dele — nem o inimigo, nem o aliado.")
add("dev_zel_possessao", "Não é Seu", D, "zeloso", "avancado", "ativa",
    {"kind": "taunt", "valor": 4, "principal": True}, custo=3, freq="cena",
    virt=["carisma"], central=True,
    descricao="Arranca a atenção de todos os inimigos de uma vez, com fúria de amante.",
    ruptura={"caminho_a": {"kind": "taunt", "valor": 8},
             "caminho_b": {"kind": "contra_ataque", "dano_base": 8}},
    evolucao={"caminho_a": {"efeito": {"kind": "taunt", "valor": 6},
                            "ruptura": {"kind": "taunt", "valor": 10}},
              "caminho_b": {"efeito": {"kind": "taunt", "valor": 4},
                            "ruptura": {"kind": "contra_ataque", "dano_base": 12}}})
add("dev_zel_vigilia", "Vigília Ciumenta", D, "zeloso", "inicial", "passiva",
    {"kind": "buff_iniciativa", "valor": 1}, descricao="Dorme de olho aberto "
    "para que nada leve o que ama antes dele.")

# -- O Enlutado: amou quem o Abismo levou; tom melancólico --
add("dev_enl_lamento", "Lamento", D, "enlutado", "inicial", "ativa",
    {"kind": "aplicar_condicao", "condicao": "desmoralizado", "duracao": 2},
    custo=1, freq="turno", virt=["carisma"],
    descricao="Uma dor tão nua que o inimigo hesita em continuar de pé.")
add("dev_enl_luto", "Peso do Luto", D, "enlutado", "avancado", "ativa",
    dano("versatil", bonus=2), custo=2, freq="cena", virt=["forca"], central=True,
    descricao="Golpe carregado com o nome de um morto — pesa mais que o aço.",
    ruptura={"caminho_a": {"kind": "dano", "categoria_arma": "versatil", "dano_base": 14},
             "caminho_b": {"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 1}},
    evolucao={"caminho_a": {"efeito": {"kind": "dano", "categoria_arma": "versatil", "dano_base": 10},
                            "ruptura": {"kind": "dano", "categoria_arma": "versatil", "dano_base": 18}},
              "caminho_b": {"efeito": {"kind": "dano", "categoria_arma": "versatil", "dano_base": 8},
                            "ruptura": {"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 2}}})
add("dev_enl_memoria", "Memória Viva", D, "enlutado", "inicial", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "reconhecer um morto/relíquia/local de perda"},
    freq="descanso_curto", descricao="O luto é um mapa dos que já se foram.")

# ======================================================================
# SANGROMANTE — negocia com o Abismo em sangue. Auto-dano vira Entropia.
# Virtude de arma: agilidade (adaga/rapieira) / corpo. Postura: pagar à vista.
# ======================================================================
S = "Sangromante"
add("san_corte_troca", "Corte de Troca", S, "", "inicial", "ativa",
    dano("leve"), virt=["agilidade", "forca"],
    descricao="Um talho rápido; o preço do sangue já está embutido.",
    mecanica={"auto_dano": 3})
add("san_finta", "Finta de Sangue", S, "", "inicial", "ativa",
    {"kind": "buff_acerto", "valor": 2}, custo=1, freq="turno", virt=["agilidade"],
    descricao="Oferece o pulso, retira a garganta — engana lendo o próprio corte.")
add("san_esquiva", "Esquiva Calculada", S, "", "inicial", "reacao",
    {"kind": "buff_esquiva", "valor": 2}, custo=1, freq="turno",
    gatilho="ao_ser_atacado", virt=["agilidade"],
    descricao="Cede o couro que pode perder para salvar o que não pode.")
add("san_pacto", "Pacto Rápido", S, "", "inicial", "passiva",
    {"kind": "buff_dano", "valor": 1}, descricao="A dor recente afia o gesto "
    "seguinte — cada gota cobrada rende juros.")
add("san_passo", "Passo Leve", S, "", "inicial", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "mover-se em silêncio/passar despercebido"},
    freq="descanso_curto", descricao="Anda como quem não quer dever passagem.")
add("san_hemorragia", "Hemorragia", S, "", "avancado", "ativa",
    {"kind": "dot", "dano_base": 3, "duracao": 3}, custo=2, freq="turno",
    virt=["agilidade"], descricao="Abre a veia certa; o inimigo se esvai sozinho.")
add("san_ultimo_lance", "Último Lance", S, "", "superior", "ativa",
    dano("leve", bonus=9), custo=4, freq="cena", virt=["agilidade"],
    descricao="Aposta tudo num só golpe pago com o próprio fôlego.",
    mecanica={"auto_dano": 4, "pico": True})

# -- O Exposto: faz espetáculo da dor; a cicatriz é credencial --
add("san_exp_espetaculo", "Espetáculo", S, "exposto", "inicial", "ativa",
    {"kind": "taunt", "valor": 2}, custo=1, freq="turno", virt=["carisma"],
    descricao="Sangra em público de propósito — todos os olhos, todas as lâminas.",
    mecanica={"auto_dano": 2})
add("san_exp_credencial", "Credencial de Dor", S, "exposto", "avancado", "ativa",
    {"kind": "dano", "categoria_arma": "leve", "dano_base": 8, "principal": True},
    custo=3, freq="cena", virt=["agilidade"], central=True,
    descricao="Reabre a pior cicatriz para pagar um golpe que ninguém esquece.",
    mecanica={"auto_dano": 4, "pico": True},
    ruptura={"caminho_a": {"kind": "dano", "categoria_arma": "leve", "dano_base": 14},
             "caminho_b": {"kind": "aplicar_condicao", "condicao": "sangrando", "duracao": 3}},
    evolucao={"caminho_a": {"efeito": {"kind": "dano", "categoria_arma": "leve", "dano_base": 11},
                            "ruptura": {"kind": "dano", "categoria_arma": "leve", "dano_base": 18}},
              "caminho_b": {"efeito": {"kind": "dano", "categoria_arma": "leve", "dano_base": 8},
                            "ruptura": {"kind": "aplicar_condicao", "condicao": "sangrando", "duracao": 5}}})
add("san_exp_plateia", "Plateia", S, "exposto", "inicial", "passiva",
    {"kind": "buff_dano", "valor": 1}, descricao="Quanto mais gente olha, mais "
    "fundo ele corta — a dor exibida vira força.")

# -- O Avaro: acumula Entropia de sangue para um golpe único --
add("san_ava_reserva", "Reserva de Sangue", S, "avaro", "inicial", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "guardar/estancar recursos p/ mais tarde"},
    freq="descanso_curto", descricao="Não gasta uma gota que não renda em dobro.")
add("san_ava_juros", "Cobrança com Juros", S, "avaro", "avancado", "ativa",
    {"kind": "dano", "categoria_arma": "versatil", "dano_base": 6, "principal": True},
    custo=2, freq="cena", virt=["forca"], central=True,
    descricao="Desconta de uma vez tudo o que o inimigo deve — o golpe cobra a dívida inteira.",
    mecanica={"pico": True},
    ruptura={"caminho_a": {"kind": "dano", "categoria_arma": "versatil", "dano_base": 16},
             "caminho_b": {"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 1}},
    evolucao={"caminho_a": {"efeito": {"kind": "dano", "categoria_arma": "versatil", "dano_base": 10},
                            "ruptura": {"kind": "dano", "categoria_arma": "versatil", "dano_base": 22}},
              "caminho_b": {"efeito": {"kind": "dano", "categoria_arma": "versatil", "dano_base": 6},
                            "ruptura": {"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 2}}})
add("san_ava_sovinice", "Sovinice", S, "avaro", "inicial", "passiva",
    {"kind": "buff_dano", "valor": 1}, descricao="Cada Entropia poupada torna o "
    "golpe guardado mais pesado.")

# -- O Silencioso: corte exato, economia de dor --
add("san_sil_exato", "Corte Exato", S, "silencioso", "inicial", "ativa",
    dano("leve", bonus=1), custo=1, freq="turno", virt=["agilidade"],
    descricao="Nem uma gota a mais do que o necessário — cirurgia com adaga.",
    mecanica={"auto_dano": 1})
add("san_sil_veia", "Veia Justa", S, "silencioso", "avancado", "ativa",
    {"kind": "dot", "dano_base": 4, "duracao": 3, "principal": True}, custo=2,
    freq="turno", virt=["agilidade"], central=True,
    descricao="Encontra o vaso que sangra devagar e não estanca.",
    ruptura={"caminho_a": {"kind": "dot", "dano_base": 8, "duracao": 3},
             "caminho_b": {"kind": "dot", "dano_base": 4, "duracao": 6}},
    evolucao={"caminho_a": {"efeito": {"kind": "dot", "dano_base": 6, "duracao": 3},
                            "ruptura": {"kind": "dot", "dano_base": 10, "duracao": 3}},
              "caminho_b": {"efeito": {"kind": "dot", "dano_base": 4, "duracao": 4},
                            "ruptura": {"kind": "dot", "dano_base": 4, "duracao": 8}}})
add("san_sil_frieza", "Frieza", S, "silencioso", "inicial", "passiva",
    {"kind": "buff_esquiva", "valor": 1}, descricao="Sem espetáculo, sem susto: "
    "economiza o próprio sangue tanto quanto o do outro.")

# ======================================================================
# CORRUPTOR — trabalha JUNTO com o Abismo: acelera a decadência que já existe.
# Virtude de arma: mente (cajado/toque). Postura: chegar mais cedo.
# ======================================================================
C = "Corruptor"
add("cor_toque", "Toque da Decadência", C, "", "inicial", "ativa",
    {"kind": "dot", "dano_base": 2, "duracao": 2}, virt=["mente"],
    descricao="O que ele encosta começa a apodrecer no tempo devido.",
    mecanica={"decadencia": "any"})
add("cor_esporos", "Esporos", C, "", "inicial", "ativa",
    {"kind": "dot", "dano_base": 2, "duracao": 3}, custo=1, freq="turno",
    virt=["mente"], descricao="Solta uma nuvem fina que se aloja nos pulmões.",
    mecanica={"decadencia": "any"})
add("cor_carne_docil", "Carne Dócil", C, "", "inicial", "passiva",
    {"kind": "buff_dot", "valor": 1}, descricao="A matéria já quer ceder; ele "
    "só precisa pedir com jeito.")
add("cor_farejar", "Farejar Praga", C, "", "inicial", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "rastrear doença/decomposição/podridão"},
    freq="descanso_curto", descricao="Segue o cheiro do que já está morrendo.")
add("cor_semear", "Semear Praga", C, "", "avancado", "ativa",
    {"kind": "dot", "dano_base": 4, "duracao": 4}, custo=3, freq="cena",
    virt=["mente"], descricao="Planta a ruína e deixa que ela faça o trabalho lento.",
    mecanica={"decadencia": "any"})
add("cor_simbiose", "Simbiose", C, "", "avancado", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "aproveitar decomposição próxima a seu favor"},
    freq="descanso_curto", descricao="Faz da podridão alheia um aliado silencioso.")
add("cor_colapso", "Colapso", C, "", "superior", "ativa",
    {"kind": "dot", "dano_base": 8, "duracao": 3}, custo=4, freq="cena",
    virt=["mente"], descricao="Adianta anos de deterioração em três respirações.",
    mecanica={"decadencia": "any"})

# -- Biologia: carne que apodrece --
add("cor_bio_gangrena", "Gangrena", C, "biologia", "inicial", "ativa",
    {"kind": "dot", "dano_base": 3, "duracao": 3}, custo=1, freq="turno",
    virt=["mente"], descricao="A carne escurece e o cheiro chega antes da dor.",
    mecanica={"decadencia": "flesh"})
add("cor_bio_metastase", "Metástase", C, "biologia", "avancado", "ativa",
    {"kind": "dot", "dano_base": 5, "duracao": 3, "principal": True}, custo=2,
    freq="cena", virt=["mente"], central=True,
    descricao="A doença não fica onde nasceu — busca o próximo corpo em cena.",
    mecanica={"decadencia": "flesh"},
    ruptura={"caminho_a": {"kind": "dot", "dano_base": 10, "duracao": 3},
             "caminho_b": {"kind": "aplicar_condicao", "condicao": "enfraquecido", "duracao": 3}},
    evolucao={"caminho_a": {"efeito": {"kind": "dot", "dano_base": 7, "duracao": 3},
                            "ruptura": {"kind": "dot", "dano_base": 12, "duracao": 4}},
              "caminho_b": {"efeito": {"kind": "dot", "dano_base": 5, "duracao": 4},
                            "ruptura": {"kind": "aplicar_condicao", "condicao": "enfraquecido", "duracao": 5}}})
add("cor_bio_necrose", "Necrose Útil", C, "biologia", "inicial", "passiva",
    {"kind": "buff_dot", "valor": 1}, descricao="Cada tecido morto vira adubo "
    "para o próximo.")

# -- Alma: vontade que rui --
add("cor_alm_duvida", "Semente da Dúvida", C, "alma", "inicial", "ativa",
    {"kind": "aplicar_condicao", "condicao": "desmoralizado", "duracao": 2},
    custo=1, freq="turno", virt=["mente", "carisma"],
    descricao="Sussurra a pergunta que apodrece qualquer coragem por dentro.",
    mecanica={"decadencia": "morale"})
add("cor_alm_desespero", "Desespero", C, "alma", "avancado", "ativa",
    {"kind": "aplicar_condicao", "condicao": "amedrontado", "duracao": 2, "principal": True},
    custo=3, freq="cena", virt=["carisma"], central=True,
    descricao="Deixa o inimigo ver, por um instante, exatamente como tudo termina.",
    mecanica={"decadencia": "morale"},
    ruptura={"caminho_a": {"kind": "aplicar_condicao", "condicao": "amedrontado", "duracao": 4},
             "caminho_b": {"kind": "aplicar_condicao", "condicao": "dominado", "duracao": 1}},
    evolucao={"caminho_a": {"efeito": {"kind": "aplicar_condicao", "condicao": "amedrontado", "duracao": 3},
                            "ruptura": {"kind": "aplicar_condicao", "condicao": "amedrontado", "duracao": 6}},
              "caminho_b": {"efeito": {"kind": "aplicar_condicao", "condicao": "desmoralizado", "duracao": 3},
                            "ruptura": {"kind": "aplicar_condicao", "condicao": "dominado", "duracao": 2}}})
add("cor_alm_erosao", "Erosão de Vontade", C, "alma", "inicial", "passiva",
    {"kind": "buff_dot", "valor": 1}, descricao="Onde a moral já range, ele "
    "empurra o alicerce.")

# -- Inorgânica: metal e pedra que cedem --
add("cor_ino_ferrugem", "Ferrugem", C, "inorganica", "inicial", "ativa",
    {"kind": "aplicar_condicao", "condicao": "desarmado_risco", "duracao": 2},
    custo=1, freq="turno", virt=["mente"],
    descricao="A arma e a armadura do inimigo envelhecem décadas num toque.",
    mecanica={"decadencia": "gear"})
add("cor_ino_fadiga", "Fadiga do Material", C, "inorganica", "avancado", "ativa",
    {"kind": "dano", "categoria_arma": "marcial", "dano_base": 6, "principal": True},
    custo=2, freq="cena", virt=["mente"], central=True,
    descricao="Encontra a microfratura no escudo e faz a cena inteira ceder ali.",
    mecanica={"decadencia": "gear"},
    ruptura={"caminho_a": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 12},
             "caminho_b": {"kind": "aplicar_condicao", "condicao": "armadura_comprometida", "duracao": 3}},
    evolucao={"caminho_a": {"efeito": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 8},
                            "ruptura": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 16}},
              "caminho_b": {"efeito": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 6},
                            "ruptura": {"kind": "aplicar_condicao", "condicao": "armadura_comprometida", "duracao": 5}}})
add("cor_ino_corrosao", "Corrosão Paciente", C, "inorganica", "inicial", "passiva",
    {"kind": "buff_dano", "valor": 1}, descricao="Cada arranhão no metal alheio "
    "vira uma alavanca para o próximo.")

# ======================================================================
# ARCANISTA CINZENTO — manipula o Abismo por um instrumento. Caldeira/descarga.
# Virtude de arma: mente (magia). Postura: a ferramenta segura o que a mão não deve.
# ======================================================================
A = "Arcanista Cinzento"
add("arc_descarga", "Descarga do Instrumento", A, "", "inicial", "ativa",
    {"kind": "dano", "categoria_arma": "marcial", "dano_base": 4}, custo=1,
    freq="livre", virt=["mente"],
    descricao="Libera a Entropia canalizada num raio cinza pelo cajado.",
    mecanica={"resfria_caldeira": True})
add("arc_faisca", "Faísca Cinzenta", A, "", "inicial", "ativa",
    {"kind": "dano", "categoria_arma": "leve", "dano_base": 3}, virt=["mente"],
    descricao="Um estalo menor, de graça, para manter a caldeira aquecida.")
add("arc_vazao", "Vazão Controlada", A, "", "inicial", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "descarregar Entropia com segurança/ler éter"},
    freq="descanso_curto", descricao="Sangra a pressão antes que o instrumento estoure.")
add("arc_olho", "Olho Arcano", A, "", "inicial", "passiva",
    {"kind": "perception", "valor": 1}, descricao="Enxerga a corrente de éter "
    "que os outros só sentem como arrepio.")
add("arc_empuxo", "Empuxo Arcano", A, "", "avancado", "ativa",
    {"kind": "empurrao", "valor": 2}, custo=2, freq="turno", virt=["mente"],
    descricao="Uma onda muda de pressão joga o inimigo para longe.")
add("arc_manto", "Manto de Bruma", A, "", "avancado", "ativa",
    {"kind": "esconder", "valor": 1}, custo=2, freq="cena", virt=["mente"],
    descricao="Condensa éter cinzento em névoa e some dentro dela.")
add("arc_torrente", "Torrente Cinzenta", A, "", "superior", "ativa",
    {"kind": "dano", "categoria_arma": "pesada", "dano_base": 12}, custo=4,
    freq="cena", virt=["mente"], descricao="Esvazia a caldeira inteira num só jato.",
    mecanica={"resfria_caldeira": True})

# -- O Calibrado: segurança acima de potência --
add("arc_cal_valvula", "Válvula de Segurança", A, "calibrado", "inicial", "reacao",
    {"kind": "buff_esquiva", "valor": 2}, custo=1, freq="turno",
    gatilho="ao_ser_atacado", virt=["mente"],
    descricao="Redireciona a descarga para se proteger sem risco de estouro.")
add("arc_cal_feixe", "Feixe Calibrado", A, "calibrado", "avancado", "ativa",
    {"kind": "dano", "categoria_arma": "marcial", "dano_base": 6, "principal": True},
    custo=2, freq="cena", virt=["mente"], central=True,
    descricao="Dano medido ao grama — nunca estoura, nunca desperdiça.",
    mecanica={"resfria_caldeira": True},
    ruptura={"caminho_a": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 12},
             "caminho_b": {"kind": "protecao", "valor": 5}},
    evolucao={"caminho_a": {"efeito": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 8},
                            "ruptura": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 16}},
              "caminho_b": {"efeito": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 6},
                            "ruptura": {"kind": "protecao", "valor": 8}}})
add("arc_cal_regulagem", "Regulagem", A, "calibrado", "inicial", "passiva",
    {"kind": "buff_defesa", "valor": 1}, descricao="Margem de segurança em tudo "
    "— sobra fôlego para aparar o imprevisto.")

# -- O Descoberto: toca o éter sem instrumento; alto dano, alto risco --
add("arc_des_mao_nua", "Mão Nua no Éter", A, "descoberto", "inicial", "ativa",
    {"kind": "dano", "categoria_arma": "versatil", "dano_base": 6}, custo=2,
    freq="turno", virt=["mente"],
    descricao="Sem cajado entre a carne e o Abismo — dói, mas queima o dobro.",
    mecanica={"auto_dano": 4})
add("arc_des_sobrecarga", "Sobrecarga", A, "descoberto", "avancado", "ativa",
    {"kind": "dano", "categoria_arma": "pesada", "dano_base": 8, "principal": True},
    custo=3, freq="cena", virt=["mente"], central=True,
    descricao="Deixa a Entropia passar direto pela pele — relâmpago sem para-raios.",
    mecanica={"auto_dano": 2},
    ruptura={"caminho_a": {"kind": "dano", "categoria_arma": "pesada", "dano_base": 18},
             "caminho_b": {"kind": "dano", "categoria_arma": "pesada", "dano_base": 8, "alvo": "area"}},
    evolucao={"caminho_a": {"efeito": {"kind": "dano", "categoria_arma": "pesada", "dano_base": 11},
                            "ruptura": {"kind": "dano", "categoria_arma": "pesada", "dano_base": 24}},
              "caminho_b": {"efeito": {"kind": "dano", "categoria_arma": "pesada", "dano_base": 8},
                            "ruptura": {"kind": "dano", "categoria_arma": "pesada", "dano_base": 12, "alvo": "area"}}})
add("arc_des_nervo", "Nervo Exposto", A, "descoberto", "inicial", "passiva",
    {"kind": "buff_dano", "valor": 2}, descricao="Sentir o éter na pele afia "
    "cada descarga — ao custo da própria segurança.")

# -- O Improvisador: monta ferramenta na hora a partir de sucata --
add("arc_imp_geringonca", "Geringonça", A, "improvisador", "inicial", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "montar/consertar instrumento a partir de sucata"},
    freq="descanso_curto", descricao="Um cano velho e um prego viram condutor de éter.")
add("arc_imp_bomba", "Bomba de Sucata", A, "improvisador", "avancado", "ativa",
    {"kind": "dano", "categoria_arma": "marcial", "dano_base": 6, "principal": True, "alvo": "area"},
    custo=2, freq="cena", virt=["mente"], central=True,
    descricao="Improviso instável que espalha faíscas por toda a zona.",
    ruptura={"caminho_a": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 12, "alvo": "area"},
             "caminho_b": {"kind": "aplicar_condicao", "condicao": "cego", "duracao": 1, "alvo": "area"}},
    evolucao={"caminho_a": {"efeito": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 8, "alvo": "area"},
                            "ruptura": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 16, "alvo": "area"}},
              "caminho_b": {"efeito": {"kind": "dano", "categoria_arma": "marcial", "dano_base": 6, "alvo": "area"},
                            "ruptura": {"kind": "aplicar_condicao", "condicao": "cego", "duracao": 2, "alvo": "area"}}})
add("arc_imp_remendo", "Remendo Esperto", A, "improvisador", "inicial", "passiva",
    {"kind": "buff_iniciativa", "valor": 1}, descricao="Sempre tem uma peça "
    "sobrando para a próxima virada.")

# ======================================================================
# MÉDICO DE CAMPO — nega o Abismo: mantém vivo o que ele quer levar.
# Virtude de arma: mente (precisão). Postura: enquanto eu respirar, você respira.
# ======================================================================
M = "Médico de Campo"
add("med_sutura", "Sutura de Campo", M, "", "inicial", "ativa",
    {"kind": "cura", "valor": 4}, custo=1, freq="turno", virt=["mente"],
    descricao="Fecha o corte sob fogo — mãos firmes onde as balas passam.")
add("med_torniquete", "Torniquete", M, "", "inicial", "ativa",
    {"kind": "cura", "valor": 3}, custo=1, freq="turno", virt=["mente"],
    descricao="Corta a hemorragia antes que o corpo perceba a perda.")
add("med_estabilizar", "Estabilizar", M, "", "avancado", "ativa",
    {"kind": "estabilizar", "valor": 1}, custo=2, freq="cena", virt=["mente"],
    descricao="Traz de volta do umbral quem o Abismo já reclamava.")
add("med_mao_firme", "Mão Firme", M, "", "inicial", "passiva",
    {"kind": "buff_cura", "valor": 1}, descricao="Não treme nem quando o mundo "
    "treme — cada ponto rende mais.")
add("med_triagem", "Triagem", M, "", "inicial", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "avaliar ferimentos/prioridade de socorro"},
    freq="descanso_curto", descricao="Num olhar, sabe quem espera e quem não pode.")
add("med_antitoxina", "Antitoxina", M, "", "avancado", "ativa",
    {"kind": "purga_condicao"}, custo=2, freq="cena", virt=["mente"],
    descricao="Neutraliza veneno, praga ou maldição com o composto certo.")
add("med_ultima_hora", "Última Hora", M, "", "superior", "ativa",
    {"kind": "cura", "valor": 10}, custo=4, freq="cena", virt=["mente"],
    descricao="Gasta tudo para arrancar um aliado das mãos do fim.")

# -- Cirurgião de Trincheira: intervenção imediata sob fogo --
add("med_tri_reflexo", "Reflexo de Trincheira", M, "cirurgiao_trincheira", "inicial", "reacao",
    {"kind": "cura", "valor": 3}, custo=1, freq="turno", gatilho="aliado_cai",
    virt=["mente"], descricao="Chega ao caído antes do segundo tiro.")
add("med_tri_intervencao", "Intervenção Imediata", M, "cirurgiao_trincheira", "avancado", "ativa",
    {"kind": "cura", "valor": 6, "principal": True}, custo=2, freq="cena",
    virt=["mente"], central=True,
    descricao="Opera no meio do fogo cruzado, sem hesitar um segundo.",
    ruptura={"caminho_a": {"kind": "cura", "valor": 12},
             "caminho_b": {"kind": "estabilizar", "valor": 2}},
    evolucao={"caminho_a": {"efeito": {"kind": "cura", "valor": 8},
                            "ruptura": {"kind": "cura", "valor": 16}},
              "caminho_b": {"efeito": {"kind": "cura", "valor": 6},
                            "ruptura": {"kind": "estabilizar", "valor": 3}}})
add("med_tri_sangue_frio", "Sangue Frio", M, "cirurgiao_trincheira", "inicial", "passiva",
    {"kind": "buff_cura", "valor": 1}, descricao="O caos ao redor não entra nas "
    "mãos — cura mais quem está pior.")

# -- Boticário: compostos, buffs e purga da Carga alheia --
add("med_bot_composto", "Composto Estimulante", M, "boticario", "inicial", "ativa",
    {"kind": "buff_dano", "valor": 2}, custo=1, freq="turno", virt=["mente"],
    descricao="Uma dose que faz o aliado bater mais forte por um tempo.")
add("med_bot_purga", "Purga da Carga", M, "boticario", "avancado", "ativa",
    {"kind": "reduzir_carga_aliado", "valor": 1, "principal": True}, custo=3,
    freq="cena", virt=["mente"], central=True,
    descricao="Extrai do aliado um pouco do Abismo que ele carrega — só o Médico sabe.",
    ruptura={"caminho_a": {"kind": "reduzir_carga_aliado", "valor": 2},
             "caminho_b": {"kind": "cura", "valor": 8}},
    evolucao={"caminho_a": {"efeito": {"kind": "reduzir_carga_aliado", "valor": 2},
                            "ruptura": {"kind": "reduzir_carga_aliado", "valor": 3}},
              "caminho_b": {"efeito": {"kind": "reduzir_carga_aliado", "valor": 1},
                            "ruptura": {"kind": "cura", "valor": 12}}})
add("med_bot_reagente", "Reagente Certo", M, "boticario", "inicial", "passiva",
    {"kind": "buff_cura", "valor": 1}, descricao="Conhece o antídoto de cada "
    "veneno de Valoria de cor.")

# -- Cirurgião de Ferro: próteses e reforço físico de aliados --
add("med_fer_talas", "Talas de Ferro", M, "cirurgiao_ferro", "inicial", "ativa",
    {"kind": "protecao", "valor": 3}, custo=1, freq="turno", virt=["mente"],
    descricao="Amarra ferro à carne para que o aliado aguente mais um round.")
add("med_fer_protese", "Prótese de Batalha", M, "cirurgiao_ferro", "avancado", "ativa",
    {"kind": "buff_dano", "valor": 3, "principal": True}, custo=2, freq="cena",
    virt=["mente"], central=True,
    descricao="Encaixa uma peça de guerra no aliado ferido — dor vira arma.",
    ruptura={"caminho_a": {"kind": "buff_dano", "valor": 6},
             "caminho_b": {"kind": "protecao", "valor": 8}},
    evolucao={"caminho_a": {"efeito": {"kind": "buff_dano", "valor": 4},
                            "ruptura": {"kind": "buff_dano", "valor": 8}},
              "caminho_b": {"efeito": {"kind": "buff_dano", "valor": 3},
                            "ruptura": {"kind": "protecao", "valor": 12}}})
add("med_fer_solda", "Solda Viva", M, "cirurgiao_ferro", "inicial", "passiva",
    {"kind": "buff_defesa", "valor": 1}, descricao="O metal que enxerta protege "
    "tanto quanto sustenta.")


# ==========================================================================
# conflito-17 — expansão autoral de volume. São 14 Cartas por classe:
# 2 por subclasse (incluindo uma Superior) + 8 de tronco. `papel` explicita a
# diferença tática para a guarda anti-reskin e para o relatório de curadoria.
# ==========================================================================
def v(cid, name, classe, sub, patamar, tipo, efeito, papel, descricao, *,
      custo=0, freq="livre", virt=None, gatilho=None):
    if cid in CARDS:
        raise ValueError(f"ID de Carta de volume colide com o acervo: {cid}")
    add(cid, name, classe, sub, patamar, tipo, efeito, custo=custo, freq=freq,
        virt=virt, gatilho=gatilho, descricao=descricao, papel=papel)
    CARDS[cid]["origem"] = "conflito-17"


# Devoto — novas liturgias, vigílias e técnicas de luto.
v("dev_cons_relicario", "Corpo-Relicário", D, "consagrado", "avancado", "ativa",
  {"kind": "protecao", "valor": 5}, "proteger aliado marcado",
  "Consagra uma cicatriz e recebe no próprio corpo o impacto destinado a outro.", custo=2, freq="turno", virt=["corpo"])
v("dev_cons_comunhao", "Comunhão do Último Fôlego", D, "consagrado", "superior", "ativa",
  {"kind": "estabilizar", "valor": 1}, "estabilização ritual à distância",
  "Pronuncia o nome verdadeiro de um aliado terminal e ancora sua alma à carne.", custo=3, freq="descanso_longo", virt=["carisma"])
v("dev_zel_interdito", "Interdito Ciumento", D, "zeloso", "avancado", "ativa",
  {"kind": "marca", "valor": 3}, "impedir troca de alvo",
  "O olhar do Devoto transforma qualquer desvio do inimigo em afronta pessoal.", custo=2, freq="turno", virt=["carisma"])
v("dev_zel_retorno", "Todo Golpe Retorna", D, "zeloso", "superior", "ativa",
  {"kind": "contra_ataque", "dano_base": 10}, "retaliação contra agressor marcado",
  "A violência que buscava um aliado volta inteira ao agressor.", custo=4, freq="cena", virt=["forca"])
v("dev_enl_cortejo", "Cortejo dos Ausentes", D, "enlutado", "avancado", "ativa",
  {"kind": "dot", "dano_base": 4, "duracao": 2, "dano_tipo": "abissal"}, "pressão abissal por luto",
  "Sombras com nomes esquecidos atravessam o alvo em procissão silenciosa.", custo=2, freq="turno", virt=["carisma"])
v("dev_enl_testemunho", "Testemunho dos Mortos", D, "enlutado", "superior", "ativa",
  {"kind": "vantagem", "valor": 2}, "vantagem coletiva contra assassino",
  "Os mortos testemunham através do Devoto e guiam o grupo contra quem os levou.", custo=3, freq="cena", virt=["mente"])
v("dev_reflexo_bastiao", "Reflexo de Bastião", D, "", "avancado", "reacao",
  {"kind": "buff_defesa", "valor": 3}, "fechar brecha ao ser flanqueado",
  "Gira o escudo no instante exato em que a linha ameaça romper.", custo=1, freq="turno", gatilho="ao_ser_flanqueado", virt=["corpo"])
v("dev_ombro_porta", "Ombro na Porta", D, "", "inicial", "reacao",
  {"kind": "empurrao", "valor": 1}, "interromper avanço inimigo",
  "Recebe a investida de lado e devolve o invasor para a zona anterior.", custo=1, freq="cena", gatilho="ao_inimigo_engajar", virt=["forca"])
v("dev_vigiar_ruina", "Vigiar a Ruína", D, "", "inicial", "utilitaria",
  {"kind": "perception", "valor": 2}, "detectar ameaça em vigília",
  "Lê nas paredes os sinais de que algo tentou entrar durante a noite.", freq="descanso_curto", virt=["mente"])
v("dev_carregar_caido", "Carregar o Caído", D, "", "avancado", "utilitaria",
  {"kind": "utilitaria", "prompt_hint": "transportar ferido ou peso extremo sem abandonar a guarda"}, "resgate sob carga",
  "Faz do próprio dorso uma muralha móvel para retirar alguém do perigo.", freq="descanso_curto", virt=["corpo"])
v("dev_passo_interposto", "Passo Interposto", D, "", "inicial", "ativa",
  {"kind": "reposicionar", "valor": 1}, "trocar posição com aliado exposto",
  "Um passo basta para colocar a própria carne entre o perigo e o companheiro.", custo=1, freq="turno", virt=["agilidade"])
v("dev_nome_proibido", "Nome Proibido", D, "", "avancado", "ativa",
  {"kind": "aplicar_condicao", "condicao": "amedrontado", "duracao": 1}, "quebrar coragem pelo nome",
  "Sussurra ao inimigo o nome que o Abismo usa quando sonha com ele.", custo=2, freq="cena", virt=["carisma"])
v("dev_martelo_penitente", "Martelo Penitente", D, "", "superior", "ativa",
  dano("pesada", 1), "golpe pesado contra alvo que feriu aliado",
  "Cada ferida do grupo acrescenta peso à descida do martelo.", custo=3, freq="cena", virt=["forca"])
v("dev_promessa_imovel", "Promessa Imóvel", D, "", "avancado", "passiva",
  {"kind": "bonus_vitalidade_por_estagio", "valor": 1}, "vitalidade por juramento mantido",
  "Enquanto sustenta a palavra dada, o corpo se recusa a ceder.")

# Sangromante — dívida, espetáculo e precisão cirúrgica do sangue.
v("san_exp_aplausos", "Aplausos da Cicatriz", S, "exposto", "avancado", "ativa",
  {"kind": "taunt", "valor": 5}, "atrair plateia hostil",
  "Exibe a ferida como desafio e faz cada inimigo disputar o próximo golpe.", custo=2, freq="cena", virt=["carisma"])
v("san_exp_bis", "Bis Sangrento", S, "exposto", "superior", "ativa",
  {"kind": "contra_ataque", "dano_base": 9}, "retaliação depois de sobreviver crítico",
  "Quando todos esperam a queda, retorna ao palco com a lâmina já em movimento.", custo=3, freq="cena", virt=["agilidade"])
v("san_ava_juros_carne", "Juros de Carne", S, "avaro", "avancado", "ativa",
  {"kind": "buff_dano", "valor": 5}, "capitalizar auto-dano acumulado",
  "Cada gota paga antes volta como força emprestada ao golpe seguinte.", custo=2, freq="turno", virt=["corpo"])
v("san_ava_falencia", "Falência Rubra", S, "avaro", "superior", "ativa",
  dano("pesada", 4), "liquidar reserva de sangue",
  "Fecha todas as contas numa pancada que cobra corpo, aço e testemunhas.", custo=4, freq="descanso_longo", virt=["forca"])
v("san_sil_fio", "Fio sem Testemunha", S, "silencioso", "avancado", "ativa",
  {"kind": "marca", "valor": 2}, "marcar artéria sem revelar ataque",
  "Um risco quase invisível indica exatamente onde a próxima lâmina deve entrar.", custo=1, freq="turno", virt=["mente"])
v("san_sil_pulso", "Silêncio do Pulso", S, "silencioso", "superior", "ativa",
  {"kind": "aplicar_condicao", "condicao": "silenciado", "duracao": 2}, "interromper conjuração pelo pulso",
  "Corta a cadência do sangue e, com ela, qualquer palavra de poder.", custo=3, freq="cena", virt=["agilidade"])
v("san_desvio_arterial", "Desvio Arterial", S, "", "inicial", "reacao",
  {"kind": "buff_esquiva", "valor": 3}, "esquiva após prever fluxo",
  "Prevê a trajetória do golpe pelo pulso do agressor e sai por um fio.", custo=1, freq="turno", gatilho="ao_ser_atacado", virt=["agilidade"])
v("san_troco_carmesim", "Troco Carmesim", S, "", "avancado", "reacao",
  {"kind": "contra_ataque", "dano_base": 5}, "contra-ataque após auto-dano",
  "A ferida recém-aberta paga imediatamente um corte no cobrador.", custo=2, freq="cena", gatilho="apos_auto_dano", virt=["forca"])
v("san_ouvir_veias", "Ouvir as Veias", S, "", "inicial", "utilitaria",
  {"kind": "perception", "valor": 3}, "rastrear vida por pulsação",
  "No silêncio, distingue medo, febre e mentira pela música sob a pele.", freq="descanso_curto", virt=["mente"])
v("san_assinar_sangue", "Assinar em Sangue", S, "", "avancado", "utilitaria",
  {"kind": "utilitaria", "prompt_hint": "selar pacto verificável ou autenticar identidade pelo sangue"}, "pacto e autenticação",
  "Uma gota torna contratos e identidades impossíveis de falsificar sem deixar cicatriz.", freq="descanso_longo", virt=["carisma"])
v("san_sangria_lenta", "Sangria Lenta", S, "", "inicial", "ativa",
  {"kind": "dot", "dano_base": 2, "duracao": 4}, "dano prolongado econômico",
  "Um corte pequeno continua cobrando muito depois de a lâmina partir.", custo=1, freq="turno", virt=["agilidade"])
v("san_transfusao_hostil", "Transfusão Hostil", S, "", "avancado", "ativa",
  {"kind": "cura", "valor": 4}, "converter ferida causada em cura",
  "Rouba do impacto a força suficiente para fechar a própria lesão.", custo=2, freq="cena", virt=["corpo"])
v("san_passo_capilar", "Passo Capilar", S, "", "superior", "ativa",
  {"kind": "reposicionar", "valor": 2}, "atravessar linha pelo menor espaço",
  "Escorre pela formação inimiga como sangue entre dedos cerrados.", custo=3, freq="cena", virt=["agilidade"])
v("san_conta_memorizada", "Conta Memorizada", S, "", "avancado", "passiva",
  {"kind": "buff_iniciativa", "valor": 2}, "iniciativa contra quem já feriu",
  "Nunca esquece quem deve sangue e sempre age antes do segundo pagamento.")

# Corruptor — anatomia, alma e matéria tratadas como falhas editáveis.
v("cor_bio_micelio", "Micélio de Guerra", C, "biologia", "avancado", "ativa",
  {"kind": "dot", "dano_base": 4, "duracao": 3, "dano_tipo": "corrosivo"}, "contágio entre corpos próximos",
  "Esporos aprendem a distância entre os corpos e atravessam a formação.", custo=2, freq="cena", virt=["mente"])
v("cor_bio_raiz", "Raiz sob a Pele", C, "biologia", "superior", "ativa",
  {"kind": "aplicar_condicao", "condicao": "enraizado", "duracao": 3}, "imobilização orgânica duradoura",
  "Fibras novas confundem carne com solo e recusam qualquer passo.", custo=4, freq="cena", virt=["corpo"])
v("cor_alm_eco", "Eco da Culpa", C, "alma", "avancado", "ativa",
  {"kind": "marca", "valor": 4}, "marcar culpa para ataques mentais",
  "A pior lembrança do alvo ganha voz e denuncia cada hesitação.", custo=2, freq="turno", virt=["carisma"])
v("cor_alm_vazio", "Sala sem Voz", C, "alma", "superior", "ativa",
  {"kind": "aplicar_condicao", "condicao": "amedrontado", "duracao": 3}, "isolamento psíquico",
  "Fecha a alma do alvo numa sala onde só o Abismo responde.", custo=4, freq="descanso_longo", virt=["mente"])
v("cor_ino_geometria_ferrugem", "Geometria da Ferrugem", C, "inorganica", "avancado", "ativa",
  {"kind": "protecao", "valor": 2}, "converter armadura corroída em cobertura",
  "Dobra metal cansado até formar um abrigo de arestas famintas.", custo=1, freq="turno", virt=["mente"])
v("cor_ino_colapso", "Colapso de Estrutura", C, "inorganica", "superior", "ativa",
  {"kind": "empurrao", "valor": 3}, "derrubar formação e cenário",
  "Encontra a única linha que mantém tudo de pé e a apaga.", custo=4, freq="cena", virt=["forca"])
v("cor_membrana", "Membrana Reflexa", C, "", "inicial", "reacao",
  {"kind": "protecao", "valor": 2}, "absorver projétil em tecido mutado",
  "Uma película translúcida cresce antes que o projétil alcance a carne.", custo=1, freq="turno", gatilho="ao_ser_alvo_distancia", virt=["corpo"])
v("cor_chao_morde", "O Chão Morde", C, "", "avancado", "reacao",
  {"kind": "empurrao", "valor": 2}, "repelir quem invade zona",
  "Pedra e raiz fecham a mandíbula sob quem se aproxima demais.", custo=2, freq="cena", gatilho="ao_inimigo_engajar", virt=["mente"])
v("cor_ler_cicatriz", "Ler Cicatriz", C, "", "inicial", "utilitaria",
  {"kind": "perception", "valor": 4}, "deduzir história biológica",
  "Cada marca no corpo revela idade, hábito, medo e sobrevivências.", freq="descanso_curto", virt=["mente"])
v("cor_modelar_chave", "Modelar Chave", C, "", "avancado", "utilitaria",
  {"kind": "utilitaria", "prompt_hint": "remodelar matéria pequena para abrir, reparar ou sabotar mecanismo"}, "engenharia orgânica improvisada",
  "Convence osso, metal ou madeira a lembrar uma forma que nunca tiveram.", freq="descanso_curto", virt=["mente"])
v("cor_acido_memoria", "Ácido de Memória", C, "", "inicial", "ativa",
  {"kind": "dot", "dano_base": 3, "duracao": 2, "dano_tipo": "corrosivo"}, "corrosão que apaga técnica",
  "A substância corrói primeiro o gesto treinado e só depois a matéria.", custo=1, freq="turno", virt=["mente"])
v("cor_fratura_util", "Fratura Útil", C, "", "avancado", "ativa",
  dano("marcial", 3), "dano que cria objeto de cobertura",
  "Quebra a parte certa do cenário e usa os estilhaços como nova anatomia.", custo=2, freq="cena", virt=["forca"])
v("cor_nome_invertido", "Nome Invertido", C, "", "superior", "ativa",
  {"kind": "aplicar_condicao", "condicao": "desmoralizado", "duracao": 3}, "desfazer identidade social",
  "Pronuncia o nome do alvo ao contrário até suas certezas perderem forma.", custo=3, freq="cena", virt=["carisma"])
v("cor_adaptacao_residual", "Adaptação Residual", C, "", "avancado", "passiva",
  {"kind": "buff_defesa", "valor": 2}, "defesa após sofrer novo dano",
  "O corpo registra cada agressão e não oferece duas vezes a mesma fraqueza.")

# Arcanista — medição, improviso e exposição consciente ao Éter.
v("arc_cal_malha", "Malha de Calibração", A, "calibrado", "avancado", "ativa",
  {"kind": "buff_acerto", "valor": 3}, "calibrar disparos do grupo",
  "Projeta uma malha cinzenta que corrige ângulo e distância para todos.", custo=2, freq="cena", virt=["mente"])
v("arc_cal_zero", "Zero Absoluto do Cálculo", A, "calibrado", "superior", "ativa",
  {"kind": "aplicar_condicao", "condicao": "atordoado", "duracao": 2}, "paralisar ao fechar todas as variáveis",
  "Por um instante não sobra possibilidade estatística de movimento.", custo=4, freq="descanso_longo", virt=["mente"])
v("arc_des_nervo_exposto", "Nervo Descoberto", A, "descoberto", "avancado", "ativa",
  {"kind": "vantagem", "valor": 3}, "vantagem em canalização sem foco",
  "Encosta o próprio sistema nervoso no Éter e aceita cada resposta.", custo=2, freq="turno", virt=["corpo"])
v("arc_des_horizonte", "Horizonte sem Isolante", A, "descoberto", "superior", "ativa",
  dano("pesada", 5), "descarga máxima com risco corporal",
  "Abre no peito uma janela pela qual a tempestade inteira atravessa.", custo=5, freq="descanso_longo", virt=["mente"])
v("arc_imp_grampo", "Grampo de Éter", A, "improvisador", "avancado", "ativa",
  {"kind": "marca", "valor": 3}, "fixar fenômeno instável em objeto",
  "Prende o impossível a um pedaço de sucata até que alguém possa usá-lo.", custo=1, freq="turno", virt=["agilidade"])
v("arc_imp_maquina", "Máquina que Só Funciona Uma Vez", A, "improvisador", "superior", "ativa",
  {"kind": "empurrao", "valor": 4}, "explosão direcional descartável",
  "Monta um artefato absurdo, aponta a saída certa e não guarda as peças.", custo=4, freq="cena", virt=["mente"])
v("arc_aterramento", "Aterramento de Emergência", A, "", "inicial", "reacao",
  {"kind": "buff_defesa", "valor": 2}, "dissipar descarga recebida",
  "Desvia energia hostil pelo metal mais próximo antes que ela encontre os ossos.", custo=1, freq="turno", gatilho="ao_sofrer_dano_sobrenatural", virt=["mente"])
v("arc_refracao", "Refração Cinzenta", A, "", "avancado", "reacao",
  {"kind": "buff_esquiva", "valor": 4}, "deslocar imagem sob mira",
  "Quebra a própria silhueta em três futuros e deixa o ataque escolher errado.", custo=2, freq="cena", gatilho="ao_ser_alvo_distancia", virt=["agilidade"])
v("arc_auscultar_eter", "Auscultar o Éter", A, "", "inicial", "utilitaria",
  {"kind": "perception", "valor": 5}, "detectar magia residual",
  "Escuta o ruído que toda alteração arcana deixa preso na matéria.", freq="descanso_curto", virt=["mente"])
v("arc_ponte_curta", "Ponte de Um Minuto", A, "", "avancado", "utilitaria",
  {"kind": "utilitaria", "prompt_hint": "alimentar ou contornar mecanismo arcano por poucos instantes"}, "bypass arcano temporário",
  "Mantém uma máquina impossível viva pelo tempo exato de atravessar.", freq="descanso_longo", virt=["mente"])
v("arc_vetor_quebrado", "Vetor Quebrado", A, "", "inicial", "ativa",
  {"kind": "reposicionar", "valor": 2}, "teleporte curto desalinhado",
  "Corta o caminho em dois e reaparece onde a geometria não esperava.", custo=1, freq="turno", virt=["agilidade"])
v("arc_pulso_inverso", "Pulso Inverso", A, "", "avancado", "ativa",
  {"kind": "purga_condicao", "valor": 1}, "remover condição por inversão",
  "Reproduz o padrão nocivo ao contrário até que ele se desfaça.", custo=2, freq="cena", virt=["mente"])
v("arc_raio_cinza", "Raio Cinza Longitudinal", A, "", "superior", "ativa",
  dano("versatil", 5), "dano arcano em linha",
  "Comprime o Éter numa linha tão fina que a distância deixa de protegê-la.", custo=4, freq="cena", virt=["mente"])
v("arc_equacao_persistente", "Equação Persistente", A, "", "avancado", "passiva",
  {"kind": "buff_iniciativa", "valor": 3}, "iniciativa após estudar cena",
  "A primeira observação continua resolvendo possibilidades enquanto a luta muda.")

# Médico — triagem, química de campo e engenharia protética.
v("med_tri_corredor", "Corredor de Triagem", M, "cirurgiao_trincheira", "avancado", "ativa",
  {"kind": "reposicionar", "valor": 2}, "retirar ferido sob fogo",
  "Abre com ordens curtas um corredor humano até a zona protegida.", custo=1, freq="turno", virt=["carisma"])
v("med_tri_segundo", "Segundo Coração", M, "cirurgiao_trincheira", "superior", "ativa",
  {"kind": "estabilizar", "valor": 2}, "estabilizar múltiplos terminais",
  "Alterna compressões e comandos até dois ritmos perdidos voltarem a responder.", custo=4, freq="descanso_longo", virt=["mente"])
v("med_bot_nevoa", "Névoa Antisséptica", M, "boticario", "avancado", "ativa",
  {"kind": "purga_condicao", "valor": 2}, "purga em zona",
  "Quebra um frasco cuja névoa limpa veneno, esporo e pânico da mesma área.", custo=2, freq="cena", virt=["mente"])
v("med_bot_panacea", "Panaceia Improvável", M, "boticario", "superior", "ativa",
  {"kind": "cura", "valor": 14}, "cura superior com reagentes raros",
  "Combina três substâncias que deveriam se anular e as obriga a salvar uma vida.", custo=4, freq="descanso_longo", virt=["mente"])
v("med_fer_ancora", "Âncora Protética", M, "cirurgiao_ferro", "avancado", "ativa",
  {"kind": "protecao", "valor": 5}, "fixar aliado contra deslocamento",
  "Crava a prótese ao chão e transforma recuo em escolha, nunca consequência.", custo=2, freq="turno", virt=["corpo"])
v("med_fer_colosso", "Prótese de Colosso", M, "cirurgiao_ferro", "superior", "ativa",
  {"kind": "buff_dano", "valor": 7}, "amplificar força de aliado",
  "Acopla pistões de campo que dão a um braço humano a memória de um gigante.", custo=4, freq="cena", virt=["mente"])
v("med_placa_reflexa", "Placa Reflexa", M, "", "inicial", "reacao",
  {"kind": "protecao", "valor": 3}, "interpor tala contra crítico",
  "Arranca uma placa do estojo e a encaixa entre golpe e órgão vital.", custo=1, freq="turno", gatilho="ao_aliado_ser_atacado", virt=["agilidade"])
v("med_dose_choque", "Dose de Choque", M, "", "avancado", "reacao",
  {"kind": "buff_iniciativa", "valor": 4}, "reativar aliado que hesita",
  "Uma agulha no ponto certo devolve o próximo segundo a quem o perderia.", custo=2, freq="cena", gatilho="ao_aliado_perder_acao", virt=["mente"])
v("med_autopsia_campo", "Autópsia de Campo", M, "", "inicial", "utilitaria",
  {"kind": "perception", "valor": 4}, "diagnosticar causa e fraqueza",
  "Um minuto de exame revela como algo morreu — e como o semelhante pode morrer.", freq="descanso_curto", virt=["mente"])
v("med_hospital_improviso", "Hospital de Improviso", M, "", "avancado", "utilitaria",
  {"kind": "utilitaria", "prompt_hint": "montar enfermaria segura com sucata, tecido e água limpa"}, "criar refúgio médico",
  "Transforma qualquer ruína com teto em um lugar onde a morte precisa esperar.", freq="descanso_longo", virt=["mente"])
v("med_corte_descompressao", "Corte de Descompressão", M, "", "inicial", "ativa",
  {"kind": "purga_condicao", "valor": 1}, "remover condição física aguda",
  "Abre espaço onde pressão, veneno ou Éter ameaçam esmagar por dentro.", custo=1, freq="turno", virt=["agilidade"])
v("med_marca_triagem", "Marca de Triagem", M, "", "avancado", "ativa",
  {"kind": "marca", "valor": 5}, "priorizar cura e proteção",
  "Um traço de giz vermelho faz o grupo inteiro reconhecer quem não pode cair.", custo=2, freq="cena", virt=["carisma"])
v("med_serra_ossea", "Serra Óssea", M, "", "superior", "ativa",
  dano("marcial", 4), "dano preciso contra armadura orgânica",
  "A ferramenta de amputação encontra juntas que espadas ignoram.", custo=3, freq="cena", virt=["agilidade"])
v("med_protocolo_retornar", "Protocolo: Retornar", M, "", "avancado", "passiva",
  {"kind": "bonus_cura_por_estagio", "valor": 2}, "cura crescente após estabilizar",
  "Cada vida estabilizada melhora o protocolo aplicado à próxima.")

# Três Cartas de fecho repõem curadorias que existiam apenas no JSON gerado e
# garantem o alvo simétrico de 30 Cartas por classe.
v("san_pulso_reserva", "Pulso de Reserva", S, "avaro", "superior", "passiva",
  {"kind": "bonus_esquiva_por_estagio", "valor": 1}, "esquiva alimentada por sangue poupado",
  "O sangue que não foi gasto mantém o corpo meio passo à frente da lâmina.")
v("cor_matriz_rejeicao", "Matriz de Rejeição", C, "inorganica", "superior", "passiva",
  {"kind": "bonus_vitalidade_por_estagio", "valor": 1},
  "vitalidade de formas assimiladas", "Cada transformação descartada deixa uma camada útil sob a pele.")
v("arc_constante_cinza", "Constante Cinza", A, "descoberto", "superior", "passiva",
  {"kind": "bonus_percepcao_por_estagio", "valor": 2}, "percepção crescente de anomalias",
  "Depois de medir o impossível tantas vezes, o olho passa a esperá-lo.")


# ==========================================================================
# Cartas de Virtude sugeridas por combinação (R6): as 2 Virtudes de topo de
# cada classe/subclasse, mapeadas às Cartas de Virtude base (data/cards/exemplos).
# ==========================================================================
VC = {"forca": "vc_forca_bruta", "mente": "vc_mente_lucida",
      "corpo": "vc_corpo_rijo", "agilidade": "vc_agil_reflexo",
      "carisma": "vc_lingua_afiada"}

# top-2 Virtudes por classe (de base_stats) + tempero por subclasse.
SUGEST = {
    "Devoto do Abismo/consagrado": ["corpo", "carisma"],
    "Devoto do Abismo/zeloso": ["carisma", "forca"],
    "Devoto do Abismo/enlutado": ["forca", "carisma"],
    "Sangromante/exposto": ["agilidade", "carisma"],
    "Sangromante/avaro": ["forca", "corpo"],
    "Sangromante/silencioso": ["agilidade", "corpo"],
    "Corruptor/biologia": ["mente", "corpo"],
    "Corruptor/alma": ["mente", "carisma"],
    "Corruptor/inorganica": ["mente", "agilidade"],
    "Arcanista Cinzento/calibrado": ["mente", "corpo"],
    "Arcanista Cinzento/descoberto": ["mente", "agilidade"],
    "Arcanista Cinzento/improvisador": ["mente", "agilidade"],
    "Médico de Campo/cirurgiao_trincheira": ["mente", "agilidade"],
    "Médico de Campo/boticario": ["mente", "carisma"],
    "Médico de Campo/cirurgiao_ferro": ["mente", "corpo"],
}
SUGESTOES = {combo: [VC[v] for v in virts] for combo, virts in SUGEST.items()}


# ==========================================================================
# Escrita: um arquivo por classe + virtude_sugeridas.json.
# ==========================================================================
SLUG = {
    "Devoto do Abismo": "devoto", "Sangromante": "sangromante",
    "Corruptor": "corruptor", "Arcanista Cinzento": "arcanista",
    "Médico de Campo": "medico",
}


def main() -> int:
    os.makedirs(CARDS_DIR, exist_ok=True)
    by_class: dict = {c: [] for c in SLUG}
    for card in CARDS.values():
        card.pop("efeito_note", None)  # limpeza de kwargs acidentais
        by_class[card["classe"]].append(card)

    for classe, slug in SLUG.items():
        path = os.path.join(CARDS_DIR, f"{slug}.json")
        payload = {
            "_meta": f"spec conflito-14: Acervo autoral de {classe} (escala nova "
                     "2d10+Virtude). Gerado por scripts/gen_cards_v4.py.",
            "cards": by_class[classe],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"escrito {path}: {len(by_class[classe])} cartas")

    sug_path = os.path.join(CARDS_DIR, "virtude_sugeridas.json")
    with open(sug_path, "w", encoding="utf-8") as f:
        json.dump({"_meta": "spec conflito-14 R6: 2 Cartas de Virtude sugeridas "
                            "por combinação classe/subclasse.",
                   "sugestoes": SUGESTOES}, f, ensure_ascii=False, indent=2)
    print(f"escrito {sug_path}: {len(SUGESTOES)} combinações")
    print(f"total: {len(CARDS)} cartas autorais")
    # R9 (classes.json.starting_abilities -> Cartas) é AÇÃO DE CUTOVER (conflito-13):
    # trocar agora quebraria o caminho antigo `known_abilities`. As Cartas iniciais
    # recomendadas por classe ficam registradas em STARTING_RECOMENDADO p/ o cutover.
    return 0


# Cartas iniciais recomendadas por classe — consumidas no cutover-13 (R9).
STARTING_RECOMENDADO = {
    "Devoto do Abismo": ["dev_golpe_convite", "dev_muralha_viva"],
    "Sangromante": ["san_corte_troca", "san_finta"],
    "Corruptor": ["cor_toque", "cor_esporos"],
    "Arcanista Cinzento": ["arc_descarga", "arc_faisca"],
    "Médico de Campo": ["med_sutura", "med_torniquete"],
}


if __name__ == "__main__":
    raise SystemExit(main())
