"""Gera o Acervo completo de Cartas de Valoria (spec conflito-14).

Substitui o conteúdo de `data/player_abilities.json` (motor antigo) pelo schema
de Carta da conflito-02, na ESCALA NOVA (2d10+Virtude, dano-base flat 3/4/6/8 —
doc 01 §19). Saída: um arquivo por classe em `data/cards/` + o mapa de Cartas de
Virtude sugeridas + `data/classes.json.starting_abilities` reescrito p/ Cartas.

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
        descricao="", central=False):
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
    descricao="Um talho rápido; o preço do sangue já está embutido.")
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
    descricao="Aposta tudo num só golpe pago com o próprio fôlego.")

# -- O Exposto: faz espetáculo da dor; a cicatriz é credencial --
add("san_exp_espetaculo", "Espetáculo", S, "exposto", "inicial", "ativa",
    {"kind": "taunt", "valor": 2}, custo=1, freq="turno", virt=["carisma"],
    descricao="Sangra em público de propósito — todos os olhos, todas as lâminas.")
add("san_exp_credencial", "Credencial de Dor", S, "exposto", "avancado", "ativa",
    {"kind": "dano", "categoria_arma": "leve", "dano_base": 8, "principal": True},
    custo=3, freq="cena", virt=["agilidade"], central=True,
    descricao="Reabre a pior cicatriz para pagar um golpe que ninguém esquece.",
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
    descricao="Nem uma gota a mais do que o necessário — cirurgia com adaga.")
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
    descricao="O que ele encosta começa a apodrecer no tempo devido.")
add("cor_esporos", "Esporos", C, "", "inicial", "ativa",
    {"kind": "dot", "dano_base": 2, "duracao": 3}, custo=1, freq="turno",
    virt=["mente"], descricao="Solta uma nuvem fina que se aloja nos pulmões.")
add("cor_carne_docil", "Carne Dócil", C, "", "inicial", "passiva",
    {"kind": "buff_dot", "valor": 1}, descricao="A matéria já quer ceder; ele "
    "só precisa pedir com jeito.")
add("cor_farejar", "Farejar Praga", C, "", "inicial", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "rastrear doença/decomposição/podridão"},
    freq="descanso_curto", descricao="Segue o cheiro do que já está morrendo.")
add("cor_semear", "Semear Praga", C, "", "avancado", "ativa",
    {"kind": "dot", "dano_base": 4, "duracao": 4}, custo=3, freq="cena",
    virt=["mente"], descricao="Planta a ruína e deixa que ela faça o trabalho lento.")
add("cor_simbiose", "Simbiose", C, "", "avancado", "utilitaria",
    {"kind": "utilitaria", "prompt_hint": "aproveitar decomposição próxima a seu favor"},
    freq="descanso_curto", descricao="Faz da podridão alheia um aliado silencioso.")
add("cor_colapso", "Colapso", C, "", "superior", "ativa",
    {"kind": "dot", "dano_base": 8, "duracao": 3}, custo=4, freq="cena",
    virt=["mente"], descricao="Adianta anos de deterioração em três respirações.")

# -- Biologia: carne que apodrece --
add("cor_bio_gangrena", "Gangrena", C, "biologia", "inicial", "ativa",
    {"kind": "dot", "dano_base": 3, "duracao": 3}, custo=1, freq="turno",
    virt=["mente"], descricao="A carne escurece e o cheiro chega antes da dor.")
add("cor_bio_metastase", "Metástase", C, "biologia", "avancado", "ativa",
    {"kind": "dot", "dano_base": 5, "duracao": 3, "principal": True}, custo=2,
    freq="cena", virt=["mente"], central=True,
    descricao="A doença não fica onde nasceu — busca o próximo corpo em cena.",
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
    descricao="Sussurra a pergunta que apodrece qualquer coragem por dentro.")
add("cor_alm_desespero", "Desespero", C, "alma", "avancado", "ativa",
    {"kind": "aplicar_condicao", "condicao": "amedrontado", "duracao": 2, "principal": True},
    custo=3, freq="cena", virt=["carisma"], central=True,
    descricao="Deixa o inimigo ver, por um instante, exatamente como tudo termina.",
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
    descricao="A arma e a armadura do inimigo envelhecem décadas num toque.")
add("cor_ino_fadiga", "Fadiga do Material", C, "inorganica", "avancado", "ativa",
    {"kind": "dano", "categoria_arma": "marcial", "dano_base": 6, "principal": True},
    custo=2, freq="cena", virt=["mente"], central=True,
    descricao="Encontra a microfratura no escudo e faz a cena inteira ceder ali.",
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
    descricao="Libera a Entropia canalizada num raio cinza pelo cajado.")
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
    freq="cena", virt=["mente"], descricao="Esvazia a caldeira inteira num só jato.")

# -- O Calibrado: segurança acima de potência --
add("arc_cal_valvula", "Válvula de Segurança", A, "calibrado", "inicial", "reacao",
    {"kind": "buff_esquiva", "valor": 2}, custo=1, freq="turno",
    gatilho="ao_ser_atacado", virt=["mente"],
    descricao="Redireciona a descarga para se proteger sem risco de estouro.")
add("arc_cal_feixe", "Feixe Calibrado", A, "calibrado", "avancado", "ativa",
    {"kind": "dano", "categoria_arma": "marcial", "dano_base": 6, "principal": True},
    custo=2, freq="cena", virt=["mente"], central=True,
    descricao="Dano medido ao grama — nunca estoura, nunca desperdiça.",
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
    descricao="Sem cajado entre a carne e o Abismo — dói, mas queima o dobro.")
add("arc_des_sobrecarga", "Sobrecarga", A, "descoberto", "avancado", "ativa",
    {"kind": "dano", "categoria_arma": "pesada", "dano_base": 8, "principal": True},
    custo=3, freq="cena", virt=["mente"], central=True,
    descricao="Deixa a Entropia passar direto pela pele — relâmpago sem para-raios.",
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
