"""SPEC-358: protocolo ``lote-v2`` do sim.py e prova de equivalência do v1."""

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gold():
    return _load_path(
        "gerar_golden_v1_358", os.path.join(ROOT, "docs", "spec358", "gerar_golden_v1.py")
    )


@pytest.fixture(scope="module")
def sim():
    return _load_path("cards_sim_358", os.path.join(ROOT, "scripts", "cards", "sim.py"))


def test_v1_equivale_a_referencia_no_motor_atual(gold, sim):
    """Garantia estrutural, imune a drift de motor: o ramo v1 do `sim.py` editado produz o
    MESMO resultado que a cópia congelada do `sim.py` original, rodando os dois agora."""
    ref = gold.load_sim(
        os.path.join(ROOT, "tests", "fixtures", "spec358_sim_v1_ref.py.txt"), "sim_ref"
    )
    assert gold.compute(sim) == gold.compute(ref)


def test_v1_reproduz_golden(gold, sim):
    """Números fixos: só valem enquanto o motor é o mesmo do golden (hash dos arquivos de
    motor). Com o motor alterado por outra spec, o teste acima cobre a garantia."""
    with open(gold.GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)
    if golden["_meta"].get("motor_hash") != gold.motor_hash():
        pytest.skip("motor mudou desde o golden: vale o teste estrutural (regenere o golden)")
    atual = gold.compute(sim)
    assert atual["simulate_batch"] == golden["simulate_batch"]
    assert atual["simulate_protocolo_lote"] == golden["simulate_protocolo_lote"]
    assert atual["main"] == golden["main"]


# --------------------------------------------------------------------------
# lote-v2
# --------------------------------------------------------------------------
import copy  # noqa: E402
from collections import Counter  # noqa: E402

from services import card_effects as fx  # noqa: E402
from services import cards  # noqa: E402


@pytest.fixture(scope="module")
def mk(gold):
    return gold._card


def _ataque(mk, i=5, **over):
    return mk(i, efeitos=[{"kind": "dano", "dano_base": 5, "categoria_arma": "leve"}], **over)


def test_referencia_mesmo_custo_tier_e_dentro_do_orcamento(sim, mk):
    for card in (
        _ataque(mk, tier=2, level_req=3),
        mk(6, efeitos=[{"kind": "protecao", "valor": 3}]),
    ):
        ref = sim.referencia(card)
        assert ref is not None
        assert ref["id"] == f"{card['id']}~ref"
        assert ref["custo_folego"] == fx.custo_folego(card) == fx.custo_folego(ref)
        for k in ("tier", "patamar", "level_req", "classe", "subclasse", "frequencia", "raridade"):
            assert ref[k] == card[k]
        assert fx.budget_error(ref) is None
        assert len(fx.normalize(ref)) == 1


def test_referencia_familia_segue_o_bot(sim, mk):
    assert sim.referencia(_ataque(mk))["efeito"]["kind"] == "dano"
    assert sim.referencia(_ataque(mk))["efeito"]["categoria_arma"] == "leve"
    assert sim.referencia(mk(7, efeitos=[{"kind": "cura", "valor": 3}]))["efeito"]["kind"] == "cura"
    for k in ("protecao", "vigilia"):
        r = sim.referencia(mk(8, efeitos=[{"kind": k, "valor": 2}]))
        assert r["efeito"]["kind"] == "protecao"
    dot = sim.referencia(mk(9, efeitos=[{"kind": "dot", "valor": 2, "duracao": 2}]))
    assert dot is not None
    assert dot["efeito"]["kind"] == "dano"


def test_referencia_none_para_reacao_passiva_e_isentas(sim, mk):
    assert (
        sim.referencia(mk(10, tipo="reacao", efeitos=[{"kind": "contra_ataque", "dano_base": 4}]))
        is None
    )
    assert sim.referencia(mk(11, tipo="passiva")) is None
    assert sim.referencia(mk(12, tipo="utilitaria")) is None


def test_referencia_ocupa_a_mesma_posicao_no_baralho_ordenado(sim, mk):
    card = _ataque(mk, 13)
    with sim.injected([card]):
        base, com, ref_deck, ref = sim.build_arms_v2(card, 1, "boticario")
    assert ref_deck is not None and ref["id"] == "med_lote_13~ref"
    assert sorted(com).index(card["id"]) == sorted(ref_deck).index(ref["id"])


def test_v2_bracos_diferem_so_na_carta_ou_referencia(sim, mk):
    card = _ataque(mk, 14, patamar="comum")
    with sim.injected([card]):
        base, com, ref_deck, ref = sim.build_arms_v2(card, 1, "boticario")
    copies = 2 if card["patamar"] in cards._COMMON_PATAMARES else 1
    assert Counter(com) - Counter(base) == Counter({card["id"]: copies})
    assert Counter(ref_deck) - Counter(base) == Counter({ref["id"]: copies})
    assert not Counter(base) - Counter(com) and not Counter(base) - Counter(ref_deck)


def test_carta_identica_a_referencia_da_delta_zero(sim, mk):
    ref = sim.referencia(_ataque(mk, 15))
    card = dict(copy.deepcopy(ref), id="med_lote_77", name="Idêntica")
    rep = sim.simulate_batch([card], [1, 3], ["padrao"], 2, [0, 1, 2], protocolo="v2")[
        "med_lote_77"
    ]
    assert rep["referencia"] is not None
    assert rep["vitoria_com"] == rep["vitoria_ref"]
    assert rep["delta_pp"] == 0.0 and rep["delta_base"] == "substituicao"


def test_v2_uso_vira_aviso(sim, mk):
    nunca = mk(
        9, custo_entropia=99, efeitos=[{"kind": "cura", "valor": 1}], frequencia="descanso_longo"
    )
    r = sim.simulate_batch([nunca], [1, 3], ["padrao"], 3, [0, 1, 2, 3], protocolo="v2")[
        "med_lote_9"
    ]
    assert "uso_baixo" in r["avisos"] or "amostra_insuficiente" in r["avisos"]
    assert r["bandeiras"] == []
    assert r["protocolo"] == "lote-v2"


def test_v2_dominante_so_por_delta(sim, gold):
    batch = [dict(gold.synthetic_batch()[0], level_req=5)]
    r = sim.simulate_batch(batch, [5], ["padrao"], 4, list(range(10)), protocolo="v2")["med_lote_1"]
    assert r["lutas_por_braco"] >= sim.MIN_LUTAS_DELTA
    assert r["delta_pp"] > sim.LIMIAR_DOMINANTE_DELTA_PP
    assert set(r["bandeiras"]) == {"dominante"}


def test_v2_reacao_sem_referencia_usa_remocao(sim, gold):
    r = sim.simulate_batch([gold.synthetic_batch()[1]], [1], ["padrao"], 2, [0, 1], protocolo="v2")[
        "med_lote_2"
    ]
    assert r["delta_base"] == "remocao" and r["referencia"] is None
    assert r["delta_pp"] == r["delta_pp_remocao"]
    assert {"sem_referencia", "uso_nao_medido"} <= set(r["avisos"])


def test_v2_restaura_catalogo_e_deterministico(sim, gold):
    before = set(cards.all_cards())
    batch = gold.synthetic_batch()[:1]
    a = sim.simulate_batch(copy.deepcopy(batch), [1], ["padrao"], 1, [0], protocolo="v2")
    assert set(cards.all_cards()) == before
    assert not [c for c in cards.all_cards() if c.endswith("~ref")]
    assert a == sim.simulate_batch(copy.deepcopy(batch), [1], ["padrao"], 1, [0], protocolo="v2")


def _write_lote(tmp_path, batch):
    p = tmp_path / "lote.json"
    p.write_text(json.dumps({"cards": batch}, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_main_v2_codigo_de_saida(sim, gold, tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(sim.PROTOCOLO_LOTE, "seeds", 10)
    avisos_so = _write_lote(tmp_path, [gold.synthetic_batch()[1]])
    assert sim.main(["--lote", avisos_so, "--protocolo", "lote-v2"]) == 0
    assert "avisos:" in capsys.readouterr().out
    dom = _write_lote(tmp_path, [dict(gold.synthetic_batch()[0], level_req=5)])
    assert sim.main(["--lote", dom, "--protocolo", "lote-v2"]) == 1


def test_promote_aceita_relatorio_v2_com_avisos(mk):
    promote = _load_path("cards_promote_358", os.path.join(ROOT, "scripts", "cards", "promote.py"))
    card = mk(21)
    rep = {card["id"]: {"bandeiras": [], "avisos": ["uso_alto"]}}
    _ok, recusadas = promote.evaluate([card], rep, [])
    assert not any("simulação" in m for m in recusadas.get(card["id"], []))
    rep = {card["id"]: {"bandeiras": ["dominante"], "avisos": []}}
    _ok, recusadas = promote.evaluate([card], rep, [])
    assert any("dominante" in m for m in recusadas[card["id"]])


def test_protocolo_invalido_levanta(sim, gold):
    with pytest.raises(ValueError):
        sim.simulate_batch(gold.synthetic_batch()[:1], [1], ["padrao"], 1, [0], protocolo="v3")
    with pytest.raises(ValueError):
        sim.simulate_protocolo_lote(gold.synthetic_batch()[:1], protocolo="x")


def test_promote_main_escolhe_o_protocolo(gold, tmp_path, monkeypatch):
    """R17: sem `--protocolo` roda o v1; com `--protocolo lote-v2`, o v2."""
    import types

    promote = _load_path("cards_promote_358b", os.path.join(ROOT, "scripts", "cards", "promote.py"))
    chamadas = []

    def fake(batch, **kw):
        chamadas.append(kw.get("protocolo", "v1"))
        return {c["id"]: {"bandeiras": [], "avisos": []} for c in batch}

    monkeypatch.setitem(sys.modules, "sim", types.SimpleNamespace(simulate_protocolo_lote=fake))
    lote = _write_lote(tmp_path, [gold._card(31)])
    promote.main([lote, "--onda", "99", "--dry-run"])
    promote.main([lote, "--onda", "99", "--dry-run", "--protocolo", "lote-v2"])
    assert chamadas == ["v1", "v2"]


def test_referencia_fora_de_posicao_vira_aviso(sim, mk, monkeypatch):
    """R9: um id do baralho entre `cid` e `cid~ref` descarta a referência."""
    card = _ataque(mk, 41)
    entre = dict(mk(42, efeitos=[{"kind": "protecao", "valor": 2}]), id=f"{card['id']}_x")
    orig = sim.build_arms

    def com_intruso(c, level, subclass):
        base, com = orig(c, level, subclass)
        return base + [entre["id"]], com + [entre["id"]]

    monkeypatch.setattr(sim, "build_arms", com_intruso)
    with sim.injected([card, entre]):
        base, com, ref_deck, ref = sim.build_arms_v2(card, 1, "boticario")
        assert ref_deck is None and ref is None
        rep = sim.simulate_batch([card], [1], ["padrao"], 1, [0], protocolo="v2")[card["id"]]
    assert rep["referencia"] is None and rep["delta_base"] == "remocao"
    assert {"sem_referencia", "referencia_fora_de_posicao"} <= set(rep["avisos"])
