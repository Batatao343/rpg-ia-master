"""SPEC-361 Etapa 3 — decisão de caminho, teto, motivo de trama e few-shot (R1-R4, R9-R11)."""

import sys
import types

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents.bestiary import load_bestiary
from services import creature_gen as cg


def _p(**over) -> cg.PedidoCriatura:
    base = dict(
        pedido="um lacaio que seja uma mente-colmeia",
        regiao="deserto_zhur",
        location_id="deserto_zhur",
        categoria_sugerida="lacaio",
        motivo_trama="",
        encounter_level=1,
        game_id="g-361",
        turn=30,
    )
    return cg.PedidoCriatura(**{**base, **over})


@pytest.fixture
def best():
    return load_bestiary()


def test_ordem_existente_variante_nova_fallback(best):
    assert cg.decidir_caminho(_p(pedido="Saltador de Palafita"), bestiary=best).caminho == (
        "existente"
    )
    d = cg.decidir_caminho(_p(), bestiary=best)
    assert (d.caminho, d.base_id, d.modificador_id) == (
        "variante",
        "mon_saltador_de_palafita",
        "mente_unica",
    )
    nova = cg.decidir_caminho(_p(pedido="algo nos odres de água estragada"), bestiary=best)
    assert nova.caminho == "nova"
    cheio = cg.decidir_caminho(
        _p(pedido="algo nos odres de água estragada"), bestiary=best, contador={"novas": 6}
    )
    assert cheio.caminho == "fallback" and cheio.motivo == "teto"


def test_decisao_deterministica(best):
    assert len({repr(cg.decidir_caminho(_p(), bestiary=best)) for _ in range(3)}) == 1


def test_teto_novas(best, monkeypatch):
    assert cg.dentro_do_teto((0, 0), 1)
    assert not cg.dentro_do_teto((1, 20), 30)  # menos de 15 turnos
    assert cg.dentro_do_teto((1, 10), 30)
    assert not cg.dentro_do_teto((6, 0), 300)
    monkeypatch.setenv("RPG_CREATURE_NEW_PER_GAME", "2")
    assert not cg.dentro_do_teto((2, 0), 300)
    # save antigo sem `creature_gen` conta como zero
    p = cg.PedidoCriatura.from_spawn(
        "algo",
        "algo nos odres",
        state={"world": {"current_location_id": "deserto_zhur", "turn_count": 3}},
        encounter_level=1,
        location_id="",
    )
    assert p.contador == (0, 0) and p.regiao == "deserto_zhur"


def test_teto_acima_cai_em_variante_se_houver(best):
    d = cg.decidir_caminho(_p(), bestiary=best, contador={"novas": 9})
    assert d.caminho == "variante"


def test_forcar_so_com_flag_eval(best, monkeypatch):
    monkeypatch.delenv("RPG_CREATURE_GEN_EVAL", raising=False)
    assert cg.decidir_caminho(_p(forcar="nova"), bestiary=best).caminho == "variante"
    monkeypatch.setenv("RPG_CREATURE_GEN_EVAL", "1")
    assert cg.decidir_caminho(_p(forcar="nova"), bestiary=best).caminho == "nova"
    sem_mod = _p(pedido="algo nos odres", forcar="variante")
    assert cg.decidir_caminho(sem_mod, bestiary=best).caminho == "fallback"


def _state(**over):
    st = {
        "campaign_plan": {
            "arc_title": "A greve dos fundidores",
            "beats": [
                {"description": "Chegar ao Anel de Ferro."},
                {"description": "Descobrir quem acende os fornos de noite."},
            ],
            "current_step": 1,
        },
        "messages": [
            HumanMessage(content="eu entro na fundição"),
            AIMessage(content="O forno ronca sozinho. Alguma coisa se mexe atrás da escória."),
        ],
        "world": {"current_location_id": "na_anel_ferro", "turn_count": 7},
    }
    st.update(over)
    return st


def test_motivo_trama_sem_350(monkeypatch):
    monkeypatch.setitem(sys.modules, "services.plot_threads", None)  # import falha
    m = cg.motivo_trama(_state(), "nova_arcadia")
    assert m.startswith("Arco: A greve dos fundidores.")
    assert "quem acende os fornos" in m and "atrás da escória" in m
    assert len(m) <= 600
    assert cg.motivo_trama(None, "nova_arcadia") == ""


def test_motivo_trama_com_350(monkeypatch):
    fake = types.ModuleType("services.plot_threads")
    fake.mode = lambda: "on"
    fake.threads_for_region = lambda r: [types.SimpleNamespace(id=i) for i in ("t2", "t1", "t3")]
    fake.public_thread_brief = lambda thread_id: f"Trama pública {thread_id}."
    monkeypatch.setitem(sys.modules, "services.plot_threads", fake)
    m = cg.motivo_trama(_state(), "nova_arcadia")
    assert "Trama pública t1." in m and "Trama pública t2." in m and "t3" not in m
    assert m.index("t1") < m.index("t2") < m.index("Última cena")


def test_motivo_sem_secret(monkeypatch):
    from services import shared_pool_validators as spv

    monkeypatch.setattr(spv, "_secret_names", lambda: frozenset({"pacto de valerius"}))
    st = _state(
        campaign_plan={
            "arc_title": "Sombras",
            "beats": [{"description": "Revelar o Pacto de Valerius. Fugir pelo esgoto."}],
            "current_step": 0,
        }
    )
    m = cg.motivo_trama(st, "nova_arcadia")
    assert "valerius" not in m.lower() and "Fugir pelo esgoto." in m


def test_exemplos_deterministicos():
    a = cg.escolher_exemplos("deserto_zhur", "besta_entropia", "lacaio de bando", "", k=3)
    b = cg.escolher_exemplos("deserto_zhur", "besta_entropia", "lacaio de bando", "", k=3)
    assert [f["id"] for f in a] == [f["id"] for f in b] and len(a) == 3


def test_exemplos_contraste_papel():
    ex = cg.escolher_exemplos("deserto_zhur", "besta_entropia", "lacaio de bando", "", k=2)
    assert ex[0]["papel_tatico"] != ex[1]["papel_tatico"]
    assert all(f["familia"] == "besta_entropia" and f["regiao"] == "deserto_zhur" for f in ex)
    sem = cg.escolher_exemplos("deserto_zhur", None, "algo", "", k=2)
    assert sem[0]["familia"] != sem[1]["familia"]


def test_exemplos_fallback_outra_regiao():
    fichas = {k: v for k, v in cg._todas_fichas().items() if v["regiao"] != "ophidia"}
    ex = cg.escolher_exemplos("ophidia", "corpo_reescrito", "praga", "", k=2, fichas=fichas)
    # região sem ficha -> mesma família, na ordem da esteira (pântano é a primeira onda)
    assert all(f["familia"] == "corpo_reescrito" for f in ex)
    ordem = cg._ordem_esteira()
    assert ordem.index(ex[0]["regiao"]) <= ordem.index(ex[1]["regiao"])


def test_exemplos_so_aprovadas():
    fichas = dict(cg._todas_fichas())
    fid = next(
        k for k, v in fichas.items() if v["regiao"] == "deserto_zhur" and v["status"] == "nova"
    )
    fichas[fid] = {**fichas[fid], "revisao": "pendente"}
    for fam in (None, "besta_entropia", "corpo_reescrito", "demonio_encarnado"):
        ex = cg.escolher_exemplos("deserto_zhur", fam, fichas[fid]["nome"], "", k=3, fichas=fichas)
        assert fid not in {f["id"] for f in ex}
        assert all(f["revisao"] == "aprovada" and f["status"] != "retro" for f in ex)


def test_projecao_compacta():
    f = cg._todas_fichas()["mon_saltador_de_palafita"]
    txt = cg.projetar_exemplo(f)
    assert len(txt) <= 1400
    assert "Saltador de Palafita" in txt and "telegrafo:" in txt and "arte_evitar:" in txt
    for fora in ("lore:", "como_se_luta", "composicao", "refs", "inspiracao", "revisor"):
        assert fora not in txt


def test_mais_proxima(best):
    p = _p(pedido="algo que guarda a duna", categoria_sugerida="lacaio")
    bid = cg.mais_proxima(p, bestiary=best)
    assert bid and cg._todas_fichas()[bid]["categoria"] == "lacaio"
    assert cg.mais_proxima(_p(regiao="nenhuma"), bestiary=best) is None


def test_resolver_nome_igual_resolve_bestiary_name(best):
    from services.encounter_manifest import resolve_bestiary_name

    textos = ["Saltador de Palafita", "saltadores de palafita", "Arame Vivo", "lacaio", "", "x"]
    textos += [str(e.get("name")) for e in list(best.values())[:40]]
    for t in textos:
        assert cg.resolver_nome(t, best) == resolve_bestiary_name(t, best), t


@pytest.mark.parametrize("modo", ["on", "off"])
def test_motivo_trama_com_plot_threads_real(monkeypatch, modo):
    """R9 com a SPEC-350 de verdade: `on` traz o resumo público das tramas da região
    (nunca segredo); `off` cai no caminho só-campaign_plan."""
    from services import plot_threads

    monkeypatch.setenv("RPG_PLOT_THREADS", modo)
    regiao = next((t.region_id for t in plot_threads.catalog().threads), "nova_arcadia")
    briefs = [
        plot_threads.public_thread_brief(t.id) for t in plot_threads.threads_for_region(regiao)[:2]
    ]
    m = cg.motivo_trama(_state(), regiao)
    assert m.startswith("Arco: A greve dos fundidores.")
    tem = any(b[:40] in m for b in briefs if b)
    assert tem is (modo == "on" and bool(briefs))
    for t in plot_threads.threads_for_region(regiao):
        for segredo in t.secret_ids:
            assert segredo not in m
