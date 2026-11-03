"""SPEC-374 Etapas 1 e 3 — eixos fechados (R10), reparo de eixos (R13) e lint_primeira (D3)."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from services import creature_gen as cg
from services.card_lint import Issue

REGIAO = "deserto_zhur"
SEIS = ("plano_corporal", "material", "escala", "locomocao", "percepcao", "papel_tatico")


def _gen(**over) -> dict:
    base = {
        "nome": "Coro de Quitina",
        "familia": "besta_entropia",
        "origem_fonte": "abismo",
        "linha_eixos": 1,
        "anatomia_texto": "Besouro de casca fosca com seis patas finas e mandíbula curva. "
        "Os olhos ficam no topo da cabeça.",
        "silhueta": "Um besouro achatado de mandíbula aberta.",
        "comportamento": "Vive em bando dentro das rachas e sai quando sente passos.",
        "arquetipo": "lider_matilha",
        "categoria": "lacaio",
        "estilo_ataque": "corpo_a_corpo",
        "nome_ataque": "Mordida de Quitina",
        "padrao": ["reforco_proprio", "ataque"],
        "telegrafo": "{nome} bate a mandíbula contra a pedra.",
        "mecanica_assinatura": "Chama o resto do bando.",
        "contra_jogo": "Pisar firme espanta o bando.",
        "gancho": "Os caravaneiros dormem com os pés para cima.",
        "description": "Besouro de bando que mora nas rachas do vidro.",
        "aparencia": "Besouro fosco de seis patas finas.",
        "arte_visual": "Besouro fosco sobre vidro rachado ao luar.",
        "arte_evitar": "Escaravelho egípcio dourado.",
    }
    base.update(over)
    return base


def _livres(regiao: str = REGIAO, seed: str = "pedido|g") -> list[dict]:
    return cg.eixos_livres(regiao, [], seed)


def _p(**over) -> cg.PedidoCriatura:
    base = dict(
        pedido="algo que vive dentro dos odres de água estragada",
        regiao=REGIAO,
        location_id=REGIAO,
        categoria_sugerida=None,
        motivo_trama="",
        encounter_level=1,
        game_id="g-374",
        turn=4,
    )
    return cg.PedidoCriatura(**{**base, **over})


class _Script:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.schemas: list[str] = []
        self.prompts: list[str] = []

    def with_structured_output(self, schema, **_k):
        outer = self

        class _B:
            def invoke(self, messages):
                outer.schemas.append(schema.__name__)
                outer.prompts.append("\n".join(str(m.content) for m in messages))
                r = outer.respostas.pop(0)
                return r() if callable(r) else r

        return _B()


def _usar(monkeypatch, llm):
    import llm_setup

    monkeypatch.setattr(llm_setup, "get_llm", lambda *a, **k: llm)


# --------------------------------------------------------------------------
def test_schema_sem_eixos_livres():
    props = cg.FichaCriaturaGerada.model_json_schema()["properties"]
    assert "linha_eixos" in props
    assert not set(SEIS) & set(props)
    assert "linha_eixos" in cg.FichaCriaturaGerada.model_json_schema()["required"]
    # a correção curta pode trocar a linha, mas também não tem os eixos
    corr = cg.CorrecaoFicha.model_json_schema()["properties"]
    assert "linha_eixos" in corr and not set(SEIS) & set(corr)


def test_ficha_runtime_preenche_eixos_da_linha():
    livres = _livres()
    assert len(livres) >= 3
    for n in (1, 2, 3):
        gen = cg.FichaCriaturaGerada(**_gen(linha_eixos=n))
        f = cg.ficha_runtime(gen, regiao=REGIAO, fid="mon_x_rt_abcdef", livres=livres)
        alvo = livres[n - 1]
        assert {e: f["anatomia"][e] for e in SEIS[:5]} == {e: alvo[e] for e in SEIS[:5]}
        assert f["papel_tatico"] == alvo["papel_tatico"]


@pytest.mark.parametrize("ruim", [0, 99, -3, "x", None, 9])
def test_linha_fora_vira_um(ruim):
    livres = _livres()
    gen = cg.FichaCriaturaGerada(**_gen(linha_eixos=ruim))
    assert gen.linha_eixos == 1
    f = cg.ficha_runtime(gen, regiao=REGIAO, fid="mon_x_rt_abcdef", livres=livres)
    assert f["anatomia"]["plano_corporal"] == livres[0]["plano_corporal"]
    # linha dentro de 1..8 mas além da lista curta: também a primeira
    curta = livres[:2]
    f2 = cg.ficha_runtime(
        {**_gen(linha_eixos=7)}, regiao=REGIAO, fid="mon_x_rt_abcdef", livres=curta
    )
    assert f2["anatomia"]["material"] == curta[0]["material"]


@pytest.mark.parametrize("regiao", ["deserto_zhur", "nova_arcadia", "skallgard", "costa_negra"])
def test_linha_escolhida_passa_u2_u3(regiao):
    livres = _livres(regiao)
    assert livres, regiao
    for n in range(1, len(livres) + 1):
        gen = cg.FichaCriaturaGerada(**_gen(linha_eixos=n))
        f = cg.ficha_runtime(gen, regiao=regiao, fid="mon_coro_rt_abcdef", livres=livres)
        codigos = {i.code for i in cg.lint_runtime(f, regiao, runtime=[])}
        assert not codigos & {"U2", "U3"}, (regiao, n, codigos)


def test_regiao_saturada_usa_schema_alternativo(monkeypatch):
    monkeypatch.setattr(cg, "eixos_livres", lambda *a, **k: [])
    eixos = {
        "plano_corporal": "radial",
        "material": "cera_sebo",
        "escala": "miuda",
        "locomocao": "escala_paredes",
        "percepcao": "vibracao",
        "papel_tatico": "suporte",
    }
    llm = _Script([cg.FichaCriaturaGeradaEixosLivres(**_gen(**eixos))])
    _usar(monkeypatch, llm)
    ficha, info = cg.gerar_nova(_p(), cg.Decisao("nova"), bestiary={}, runtime=[], lore="")
    assert llm.schemas == ["FichaCriaturaGeradaEixosLivres"]
    assert ficha is not None or info["codigos"]  # o lint decide; o schema é o que importa aqui
    if ficha:
        assert ficha["anatomia"]["plano_corporal"] == "radial"
        assert ficha["papel_tatico"] == "suporte"
    assert "<eixos_livres>\n" not in llm.prompts[0]
    assert "escreva os seis eixos" in llm.prompts[0]


def test_regiao_saturada_correcao_mescla_eixos():
    ant = cg.FichaCriaturaGeradaEixosLivres(
        **_gen(
            plano_corporal="radial",
            material="cera_sebo",
            escala="miuda",
            locomocao="escala_paredes",
            percepcao="vibracao",
            papel_tatico="suporte",
        )
    ).model_dump()
    corr = cg.CorrecaoFichaEixosLivres(material="vidro_cristal")
    nova = cg._resposta_para_ficha(corr, ant)
    assert isinstance(nova, cg.FichaCriaturaGeradaEixosLivres)
    assert nova.material == "vidro_cristal" and nova.plano_corporal == "radial"


def test_guard_fallback(monkeypatch):
    _usar(monkeypatch, _Script([AIMessage(content="erro"), AIMessage(content="erro")]))
    ficha, info = cg.gerar_nova(_p(), cg.Decisao("nova"), bestiary={}, runtime=[], lore="")
    assert ficha is None
    assert "SCHEMA" in info["codigos"] and info["lint_primeira"] is False


def test_template_antigo_com_eixos_carrega():
    # ficha runtime da 361 (seis eixos gravados) segue válida para o gate e o template
    antiga = cg.ficha_runtime(
        {**_gen(), **{e: v for e, v in _livres()[0].items()}},
        regiao=REGIAO,
        fid="mon_coro_rt_abcdef",
    )
    assert antiga["anatomia"]["plano_corporal"] == _livres()[0]["plano_corporal"]
    tpl = cg.ficha_para_template(json.loads(json.dumps(antiga)), encounter_level=1)
    assert tpl["id"] == "mon_coro_rt_abcdef"


def test_prompt_numera_as_linhas_e_pede_o_numero():
    livres = _livres()
    msgs = cg.montar_prompt(_p(), [], lore="", ocupados="", eixos=livres)
    sistema = str(msgs[0].content)
    bloco = sistema.split("<eixos_livres>\n")[1].split("</eixos_livres>")[0]
    for n, c in enumerate(livres, 1):
        assert f"\n{n}. {cg._linha_eixos_livres(c)}" in bloco
    assert "linha_eixos" in sistema and "copie os seis" not in sistema
    assert "se mudar algum valor" not in sistema.lower()


# --------------------------------------------------------------------------
# Etapa 3 — reparo de eixos e correção curta (R13) e fronteira do lint_primeira (D3)
# --------------------------------------------------------------------------
def test_reparo_eixos_troca_linha():
    livres = _livres()
    ficha = cg.ficha_runtime(_gen(), regiao=REGIAO, fid="mon_x_rt_abcdef", livres=livres)
    u3 = [Issue("error", "U3", "a/mon_x_rt_abcdef: 4 de 6 eixos iguais")]
    chamadas: list[str] = []

    def lint(f):
        chamadas.append(f["anatomia"]["plano_corporal"])
        return [] if f["anatomia"]["plano_corporal"] == livres[2]["plano_corporal"] else u3

    nova = cg.reparar_eixos(ficha, u3, livres, lint)
    assert nova is not None
    assert nova["anatomia"]["plano_corporal"] == livres[2]["plano_corporal"]
    assert nova["papel_tatico"] == livres[2]["papel_tatico"]
    assert nova["anatomia"]["texto"] == ficha["anatomia"]["texto"]  # a prosa fica
    # outro erro: não é reparável aqui
    r20 = [Issue("error", "R20", "x tem número")]
    assert cg.reparar_eixos(ficha, u3 + r20, livres, lambda f: []) is None
    assert cg.reparar_eixos(ficha, u3, [], lambda f: []) is None


def test_reparo_eixos_nao_conta_lint_primeira(monkeypatch):
    """A ficha da 1ª tentativa reprova em U3; o motor troca a linha e aprova. O
    ``lint_primeira`` segue sendo o resultado cru (False)."""
    livres = cg.eixos_livres(REGIAO, [], "algo|g-374")
    primeira = livres[0]
    orig = cg.lint_runtime

    def lint(ficha, regiao, **kw):
        eixos = {e: ficha["anatomia"][e] for e in SEIS[:5]}
        if all(primeira[e] == eixos[e] for e in SEIS[:5]):  # força U3 só na linha 1
            return [Issue("error", "U3", f"x/{ficha['id']}: 4 de 6 eixos iguais")]
        return orig(ficha, regiao, **kw)

    monkeypatch.setattr(cg, "lint_runtime", lint)
    monkeypatch.setattr(cg, "eixos_livres", lambda *a, **k: livres)
    llm = _Script([cg.FichaCriaturaGerada(**_gen(linha_eixos=1))])
    _usar(monkeypatch, llm)
    ficha, info = cg.gerar_nova(_p(), cg.Decisao("nova"), bestiary={}, runtime=[], lore="")
    assert ficha is not None
    assert info["lint_primeira"] is False  # cru, antes do reparo
    assert "U2U3-eixos-reparados" in info["codigos"]
    assert info["tentativas"] == 1 and len(llm.prompts) == 1


def test_correcao_recebe_linhas():
    livres = _livres()
    msgs = cg.montar_prompt_correcao(
        _p(),
        _gen(),
        [Issue("error", "U3", "a/x: 4 de 6 eixos iguais")],
        ocupados="",
        eixos=livres,
    )
    sistema = str(msgs[0].content)
    assert "1. " + cg._linha_eixos_livres(livres[0]) in sistema
    assert "linha_eixos" in sistema


def test_lint_primeira_conta_linha_e_forma(monkeypatch):
    """D3: linha->eixos e `{nome}` no telegrafo rodam ANTES do lint e contam no lint_primeira."""
    livres = cg.eixos_livres(REGIAO, [], "algo|g-374")
    monkeypatch.setattr(cg, "eixos_livres", lambda *a, **k: livres)
    gen = cg.FichaCriaturaGerada(**_gen(telegrafo="O Coro de Quitina bate a mandíbula na pedra."))
    _usar(monkeypatch, _Script([gen]))
    ficha, info = cg.gerar_nova(_p(), cg.Decisao("nova"), bestiary={}, runtime=[], lore="")
    assert ficha is not None and info["lint_primeira"] is True
    assert ficha["telegrafo"].startswith("{nome} bate")
