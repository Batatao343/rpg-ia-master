"""SPEC-361 Etapas 1 e 4 — materialização (R15), schema (R14), gate (R16/R17/R20) e mock (R31)."""

import json
import typing

import pytest
from langchain_core.messages import AIMessage

from agents.bestiary import _VIRTUDE_TEMPLATES, materialize_enemy_concept
from services import bestiary_lint as bl
from services import creature_gen as cg
from services import enemy_decks

# --------------------------------------------------------------------------
# Etapa 1 — materialização
# --------------------------------------------------------------------------


def test_materialize_aceita_familia_baralho():
    t = materialize_enemy_concept({"name": "X", "arquetipo": "predador", "categoria": "padrao"})
    agil = materialize_enemy_concept({"name": "X", "arquetipo": "agil", "categoria": "padrao"})
    assert t["virtudes"] == agil["virtudes"]
    assert t["arquetipo"] == "predador"
    assert enemy_decks.family_key(t) == "predador"
    assert t["tactical_profile"] == agil["tactical_profile"]


# Snapshot da materialização legada (antes da SPEC-361), nível 1 e nível 9.
_LEGADO = {
    "equilibrado": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 2, "carisma": 1},
    "bruto": {"forca": 3, "agilidade": 1, "corpo": 3, "mente": 1, "carisma": 1},
    "agil": {"forca": 1, "agilidade": 3, "corpo": 2, "mente": 2, "carisma": 1},
    "astuto": {"forca": 1, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2},
    "mistico": {"forca": 1, "agilidade": 2, "corpo": 1, "mente": 3, "carisma": 3},
}


@pytest.mark.parametrize("arq", sorted(_LEGADO))
def test_materialize_legado_identico(arq):
    assert _VIRTUDE_TEMPLATES[arq] == _LEGADO[arq]
    t = materialize_enemy_concept({"name": "Bicho", "arquetipo": arq, "categoria": "padrao"})
    assert t["arquetipo"] == arq and t["virtudes"] == _LEGADO[arq]
    desconhecido = materialize_enemy_concept({"name": "Bicho", "arquetipo": "inexistente"})
    assert desconhecido["arquetipo"] == "equilibrado"


def _ficha_ok(**over) -> dict:
    base = {
        "nome": "Coro de Quitina",
        "familia": "besta_entropia",
        "origem_fonte": "abismo",
        "plano_corporal": "radial",
        "material": "cera_sebo",
        "escala": "miuda",
        "locomocao": "escala_paredes",
        "percepcao": "vibracao",
        "anatomia_texto": "Besouro de casca fosca com seis patas finas e mandíbula curva. "
        "Os olhos ficam no topo da cabeça.",
        "silhueta": "Um besouro achatado de mandíbula aberta.",
        "comportamento": "Vive em bando dentro das rachas e sai quando sente passos.",
        "papel_tatico": "suporte",
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


def test_ficha_para_template_sem_numero_do_llm():
    ficha = cg.ficha_runtime(
        cg.FichaCriaturaGerada(**_ficha_ok()), regiao="deserto_zhur", fid="mon_coro_rt_abcdef"
    )
    ficha_suja = {**ficha, "hp": 999, "virtudes": {"forca": 5}, "max_vitalidade": 999}
    t = cg.ficha_para_template(ficha_suja, encounter_level=1)
    limpo = cg.ficha_para_template(ficha, encounter_level=1)
    assert t["max_vitalidade"] == limpo["max_vitalidade"] != 999
    assert t["virtudes"] == limpo["virtudes"]
    assert t["arquetipo"] == "lider_matilha" and t["id"] == "mon_coro_rt_abcdef"
    assert t["appearance"] == "Besouro fosco de seis patas finas."


def test_schema_rejeita_numero_extra():
    with pytest.raises(ValueError):
        cg.FichaCriaturaGerada(**_ficha_ok(hp=10))


def test_assinatura_da_familia():
    ficha = cg.ficha_runtime(
        cg.FichaCriaturaGerada(**_ficha_ok(categoria="elite")),
        regiao="deserto_zhur",
        fid="mon_coro_rt_abcdef",
    )
    t = cg.ficha_para_template(ficha)
    sig = enemy_decks.family_signature(t)
    ass = t["tactical_profile"]["assinatura"]
    assert ass["carta"] == sig["carta"]
    assert ass["a_cada_n"] == cg.A_CADA_N["elite"] == 2
    assert ass["telegrafo"] == "{nome} bate a mandíbula contra a pedra."
    assert t["tactical_profile"]["padrao"] == ["reforco_proprio", "ataque"]


def _lit(field: str) -> set:
    return set(typing.get_args(cg.FichaCriaturaGerada.model_fields[field].annotation))


def test_schema_literals_iguais_enums():
    for eixo in ("plano_corporal", "material", "escala", "locomocao", "percepcao", "papel_tatico"):
        assert _lit(eixo) == set(bl.ENUMS[eixo]), eixo
    assert _lit("familia") == set(bl.FAMILIAS_VALORIA)
    assert _lit("arquetipo") == set(enemy_decks.FAMILIAS)
    opcional = typing.get_args(cg.FichaCriaturaGerada.model_fields["demonio"].annotation)
    lit = next(a for a in opcional if a is not type(None))
    assert set(typing.get_args(lit)) == set(bl.DEMONIOS)
    nums = [
        n for n, f in cg.FichaCriaturaGerada.model_fields.items() if f.annotation in (int, float)
    ]
    assert nums == []


def test_schema_apara_texto_longo():
    f = cg.FichaCriaturaGerada(**_ficha_ok(description="Frase curta. " + "palavra " * 60))
    assert len(f.description) <= 200


# --------------------------------------------------------------------------
# Etapa 4 — gate, retry, prazo, guard, mock
# --------------------------------------------------------------------------
PEDIDO = dict(
    pedido="algo que vive dentro dos odres de água estragada",
    regiao="deserto_zhur",
    location_id="deserto_zhur",
    categoria_sugerida=None,
    motivo_trama="",
    encounter_level=1,
    game_id="g-361",
    turn=4,
)


def _p(**over) -> cg.PedidoCriatura:
    return cg.PedidoCriatura(**{**PEDIDO, **over})


def test_lint_runtime_sem_u11_u12():
    ficha = cg.ficha_runtime(
        cg.FichaCriaturaGerada(**_ficha_ok()), regiao="deserto_zhur", fid="mon_coro_rt_abcdef"
    )
    issues = cg.lint_runtime(ficha, "deserto_zhur", runtime=[])
    codes = {i.code for i in issues}
    assert "U11" not in codes and "U12" not in codes
    assert all("mon_coro_rt_abcdef" in i.message for i in issues)


def test_digito_reprova():
    ficha = cg.ficha_runtime(
        cg.FichaCriaturaGerada(**_ficha_ok(contra_jogo="Acertar 3 vezes na casca.")),
        regiao="deserto_zhur",
        fid="mon_coro_rt_abcdef",
    )
    assert "R20" in {i.code for i in cg.lint_runtime(ficha, "deserto_zhur", runtime=[])}
    ficha2 = {**ficha, "contra_jogo": "Bater de lado.", "gancho": "Ganha +2 quando sangra."}
    assert "R20" in {i.code for i in cg.lint_runtime(ficha2, "deserto_zhur", runtime=[])}


class _ScriptLLM:
    """LLM falso: devolve a sequência dada e guarda os prompts."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.prompts: list[str] = []

    def with_structured_output(self, schema, **_k):
        outer = self

        class _B:
            def invoke(self, messages):
                outer.prompts.append("\n".join(str(m.content) for m in messages))
                r = outer.respostas.pop(0)
                return r() if callable(r) else r

        return _B()


def _usar_llm(monkeypatch, llm):
    import llm_setup

    monkeypatch.setattr(llm_setup, "get_llm", lambda *a, **k: llm)


def _colidente() -> cg.FichaCriaturaGerada:
    # mesma tripla do Saltador de Palafita (bipede_curvado / vidro_cristal / batedor_rapido)
    return cg.FichaCriaturaGerada(
        **_ficha_ok(
            plano_corporal="bipede_curvado",
            material="vidro_cristal",
            papel_tatico="batedor_rapido",
        )
    )


def test_colisao_retry_com_feedback(monkeypatch):
    llm = _ScriptLLM([_colidente(), cg.FichaCriaturaGerada(**_ficha_ok())])
    _usar_llm(monkeypatch, llm)
    res = cg.gerar(_p(), lore="")
    assert len(llm.prompts) == 2
    assert "U2" in llm.prompts[1] and "mon_saltador_de_palafita" in llm.prompts[1]
    assert "<corrigir>" in llm.prompts[1] and "<corrigir>" not in llm.prompts[0]
    assert res.caminho == "nova" and res.tentativas == 2 and res.lint_primeira is False
    assert res.ficha["revisao"] == "pendente" and res.ficha["autor"] == "runtime"


def test_colisao_dupla_fallback_mais_proxima(monkeypatch):
    llm = _ScriptLLM([_colidente(), _colidente()])
    _usar_llm(monkeypatch, llm)
    p = _p()
    res = cg.gerar(p, lore="")
    assert res.caminho == "fallback"
    from agents.bestiary import load_bestiary

    assert res.template["id"] == cg.mais_proxima(p, bestiary=load_bestiary())
    assert res.template["geracao"]["pedido"] == p.pedido


def test_prazo_estourado_fallback(monkeypatch):
    relogio = iter([0.0, 0.0, 7.0, 7.0, 7.0, 7.0])
    monkeypatch.setattr(cg, "_relogio", lambda: next(relogio, 20.0))
    llm = _ScriptLLM([_colidente(), cg.FichaCriaturaGerada(**_ficha_ok())])
    _usar_llm(monkeypatch, llm)
    res = cg.gerar(_p(), lore="")
    assert len(llm.prompts) == 1  # 7 s > 12 s × 0,5: a 2ª tentativa não começa
    assert res.caminho == "fallback" and "PRAZO" in res.codigos


def test_prazo_real_por_thread(monkeypatch):
    import time as _t

    monkeypatch.setenv("RPG_CREATURE_GEN_DEADLINE_S", "0.2")

    def lento():
        _t.sleep(0.6)
        return cg.FichaCriaturaGerada(**_ficha_ok())

    _usar_llm(monkeypatch, _ScriptLLM([lento]))
    t0 = _t.perf_counter()
    res = cg.gerar(_p(), lore="")
    assert res.caminho == "fallback"
    assert _t.perf_counter() - t0 < 0.55


def test_fallbackllm_guard(monkeypatch):
    from llm_setup import FallbackLLM

    _usar_llm(monkeypatch, FallbackLLM("sem provider"))
    res = cg.gerar(_p(), lore="")
    assert res.caminho == "fallback" and res.template


def test_aimessage_guard(monkeypatch):
    _usar_llm(monkeypatch, _ScriptLLM([AIMessage(content="erro"), AIMessage(content="erro")]))
    res = cg.gerar(_p(), lore="")
    assert res.caminho == "fallback" and "SCHEMA" in res.codigos


def test_mock_builder_passa_no_gate():
    # conftest força RPG_FORCE_MOCK=1: get_llm() é o MockLLM
    for regiao, loc, pedido in (
        ("deserto_zhur", "deserto_zhur", "algo nos odres"),
        ("nova_arcadia", "na_anel_ferro", "a coisa da fundição"),
        ("skallgard", "skallgard", "um mago cobrado"),
    ):
        res = cg.gerar(_p(regiao=regiao, location_id=loc, pedido=pedido), lore="")
        assert res.caminho == "nova", (regiao, res.codigos)
        assert res.lint_primeira is True
        assert res.template["appearance"]
    a = cg.gerar(_p(), lore="").ficha
    b = cg.gerar(_p(), lore="").ficha
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
