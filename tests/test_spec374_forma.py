"""SPEC-374 Etapa 2 — normalização de forma (R11) e orçamento do prompt (R12)."""

from __future__ import annotations

import pytest

from services import creature_gen as cg

NOME = "Coro de Quitina"


@pytest.mark.parametrize(
    "tel",
    [
        "Coro de Quitina bate a mandíbula contra a pedra.",
        "O Coro de Quitina bate a mandíbula contra a pedra.",
        "o coro de quitina bate a mandíbula contra a pedra.",
        "  Um Coro de Quitina bate a mandíbula contra a pedra.",
    ],
)
def test_telegrafo_nome_vira_placeholder(tel):
    out = cg.normalizar_forma({"telegrafo": tel}, nome=NOME)
    assert out["telegrafo"] == "{nome} bate a mandíbula contra a pedra."


def test_telegrafo_com_placeholder_ou_sem_nome_fica():
    ok = {"telegrafo": "{nome} bate a mandíbula."}
    assert cg.normalizar_forma(ok, nome=NOME)["telegrafo"] == ok["telegrafo"]
    outro = {"telegrafo": "A criatura bate a mandíbula."}
    assert cg.normalizar_forma(outro, nome=NOME)["telegrafo"] == outro["telegrafo"]
    # nome só no meio da frase: não é "começa pelo nome"
    meio = {"telegrafo": "Diante do Coro de Quitina, o chão treme."}
    assert cg.normalizar_forma(meio, nome=NOME)["telegrafo"] == meio["telegrafo"]
    # prefixo de outra palavra não casa
    assert cg.normalizar_forma({"telegrafo": "Coro de Quitinas ri."}, nome=NOME)["telegrafo"] == (
        "Coro de Quitinas ri."
    )


def test_espacos_aspas_e_pontuacao():
    out = cg.normalizar_forma(
        {
            "gancho": "  “Chegou  depois   do temporal!!”  ",
            "contra_jogo": "Mirar a casca,, de lado..",
            "silhueta": "“Vulto” baixo.",
        },
        nome=NOME,
    )
    assert out["gancho"] == "Chegou depois do temporal!"
    assert out["contra_jogo"] == "Mirar a casca, de lado."
    assert out["silhueta"] == '"Vulto" baixo.'


def test_normalizar_nao_mexe_em_digito_nem_jargao():
    gen = {
        "contra_jogo": "Acertar 3 vezes na casca.",
        "gancho": "Ganha +2 quando sangra, um tank de osso.",
        "telegrafo": "{nome} ruge.",
    }
    out = cg.normalizar_forma(gen, nome=NOME)
    assert out == gen  # nada de converter dígito nem trocar palavra proibida


def test_normalizar_lista_fechada():
    gen = {
        "nome_extra": "  “x”  ",
        "padrao": ["ataque", "mover"],
        "categoria": "  lacaio ",
        "linha_eixos": 3,
        "demonio": None,
    }
    assert cg.normalizar_forma(gen, nome=NOME) == gen  # só os campos de texto da lista
    assert set(cg._FORMA_CAMPOS) <= set(cg.FichaCriaturaGerada.model_fields)


@pytest.mark.parametrize(
    "regiao,loc",
    [
        ("deserto_zhur", "deserto_zhur"),
        ("nova_arcadia", "na_anel_ferro"),
        ("skallgard", "skallgard"),
        ("costa_negra", "costa_negra"),
        ("pantano_melancolia", "pantano_melancolia"),
    ],
)
def test_prompt_ate_14000(regiao, loc):
    p = cg.PedidoCriatura(
        pedido="uma coisa que vive no fundo da cisterna e conta os passos de quem desce",
        regiao=regiao,
        location_id=loc,
        categoria_sugerida=None,
        motivo_trama="",
        encounter_level=1,
        game_id="g-374",
        turn=3,
    )
    ex = cg.escolher_exemplos(regiao, None, p.pedido, "", k=3)
    oc = cg.eixos_ocupados(regiao, [])
    livres = cg.eixos_livres(regiao, [], "x|g")
    msgs = cg.montar_prompt(p, ex, lore="lore " * 800, ocupados=oc, eixos=livres)
    assert cg.prompt_chars(msgs) <= cg.PROMPT_MAX_CHARS
    corr = cg.montar_prompt_correcao(p, {"nome": "x"}, [], ocupados=oc, eixos=livres)
    assert cg.prompt_chars(corr) <= cg.PROMPT_MAX_CHARS


def test_linha_nucleos_lista_a_primeira_palavra_das_listadas():
    oc = cg.eixos_ocupados("deserto_zhur", [])
    linha = cg.linha_nucleos(oc)
    assert linha.startswith("Já começam nome na região")
    primeiro = oc.splitlines()[0].split(" — ")[0]
    palavra = next(
        w for w in primeiro.split() if cg.bl.nucleo_nome(w) == cg.bl.nucleo_nome(primeiro)
    )
    if len(cg.bl.nucleo_nome(primeiro)) >= 4:
        assert palavra in linha  # como está escrita no nome, com acento
    assert cg.linha_nucleos("") == ""


def test_padroes_livres_nao_repetem_os_da_regiao():
    linha = cg.padroes_livres("deserto_zhur", [], "x|g")
    usados = {
        (tuple(f.get("padrao") or []), f.get("a_cada_n"))
        for f in cg.fichas_da_regiao("deserto_zhur")
    }
    rotulos = [
        (r, c) for r, c in (("lacaio ou padrao: ", 3), ("elite ou chefe: ", 2)) if r in linha
    ]
    if not rotulos:  # nada colide: lista única (sem repetir ~170 caracteres)
        assert linha.startswith("qualquer categoria: ")
        rotulos = [("qualquer categoria: ", 3), ("qualquer categoria: ", 2)]
    for rotulo, cad in rotulos:
        trecho = linha.split(rotulo)[1].split(";")[0]
        for pad in trecho.split(" | "):
            slots = tuple(pad.split(","))
            assert (slots, cad) not in usados
            assert {"ataque", "ataque_multiplo"} & set(slots)
    assert linha == cg.padroes_livres("deserto_zhur", [], "x|g")  # determinístico


def test_padroes_livres_lista_unica_quando_iguais():
    linha = cg.padroes_livres("costa_negra", [], "s")
    if "qualquer categoria: " in linha:
        assert "elite ou chefe" not in linha and linha.count(" | ") <= 3


def test_aspas_so_caem_quando_embrulham_o_campo_inteiro():
    f = cg._limpar_forma
    assert f('"Abre" e depois "fecha"') == '"Abre" e depois "fecha"'
    assert f('"Vulto baixo."') == "Vulto baixo."


def test_nome_sujo_vira_placeholder():
    nome = cg._limpar_forma("Coro de   Quitina")
    out = cg.normalizar_forma({"telegrafo": "Coro de Quitina bate."}, nome=nome)
    assert out["telegrafo"] == "{nome} bate."
