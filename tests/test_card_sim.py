"""SPEC-336 R4/R5/R6: simulação, promoção, métricas e painel da esteira de Cartas."""

import copy
import importlib.util
import json
import os
import sys

import pytest

from services import cards

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    path = os.path.join(ROOT, "scripts", "cards", f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"cards_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sim():
    return _load("sim")


def _card(i, **over):
    c = {
        "id": f"med_lote_{i}",
        "name": f"Fio {i}",
        "tipo": "ativa",
        "origem": "onda-1",
        "classe": "Médico de Campo",
        "subclasse": "boticario",
        "patamar": "inicial",
        "raridade": "comum",
        "custo_entropia": 0,
        "frequencia": "livre",
        "virtude_permitida": ["mente"],
        "efeitos": [{"kind": "cura", "valor": 3}],
        "descricao": "Cinza de fornalha fecha a ferida.",
        "momento": f"Melhor jogada quando o caso {i} pede calma e o inimigo hesita.",
        "tier": 1,
        "level_req": 1,
        "apex": False,
        "onda": 1,
        "versao": 1,
    }
    c.update(over)
    return c


def _synthetic_batch():
    return [
        _card(1, efeitos=[{"kind": "dano", "dano_base": 40, "categoria_arma": "leve"}]),
        _card(2, tipo="reacao", efeitos=[{"kind": "contra_ataque", "dano_base": 4}]),
        _card(3, efeitos=[{"kind": "protecao", "valor": 2}]),
    ]


def test_sim_is_deterministic(sim):
    batch = _synthetic_batch()[:1]
    a = sim.simulate_batch(copy.deepcopy(batch), [1, 3], ["padrao"], 2, [0, 1])
    b = sim.simulate_batch(copy.deepcopy(batch), [1, 3], ["padrao"], 2, [0, 1])
    assert a == b


def test_sim_flags_dominant_card(sim):
    rep = sim.simulate_batch(_synthetic_batch(), [1, 3, 5], ["padrao"], 3, [0, 1, 2, 3])
    r = rep["med_lote_1"]
    assert r["vezes_na_mao"] >= sim.AMOSTRA_MINIMA_MAO
    assert "dominante" in r["bandeiras"]
    assert r["dano_por_folego"] > 10
    assert r["lutas_por_braco"] == 36


def test_sim_flags_blank_card(sim):
    # carta jogável que o bot nunca escolhe: cobra Entropia que o herói não tem
    nunca = _card(
        9, custo_entropia=99, efeitos=[{"kind": "cura", "valor": 1}], frequencia="descanso_longo"
    )
    rep = sim.simulate_batch([nunca], [1, 3], ["padrao"], 3, [0, 1, 2, 3])
    r = rep["med_lote_9"]
    assert r["taxa_uso"] == 0.0
    assert "em_branco" in r["bandeiras"] or "amostra_insuficiente" in r["bandeiras"]


def test_sim_reaction_has_use_not_measured(sim):
    rep = sim.simulate_batch([_synthetic_batch()[1]], [1], ["padrao"], 2, [0, 1])
    assert "uso_nao_medido" in rep["med_lote_2"]["bandeiras"]


def test_sim_restores_catalog(sim):
    before = set(cards.all_cards())
    sim.simulate_batch(_synthetic_batch()[:1], [1], ["padrao"], 1, [0])
    assert set(cards.all_cards()) == before


def test_full_deck_is_legal(sim):
    for cls in ("Devoto do Abismo", "Médico de Campo"):
        deck = sim.full_deck(cls, 5)
        assert cards.DECK_MIN <= len(deck) <= cards.DECK_MAX
        assert any(c for c in deck if not (cards.get_card(c) or {}).get("basica"))


def test_pipeline_end_to_end_ten_cards(sim, tmp_path, monkeypatch):
    """Esteira ponta a ponta num lote de 10: lint -> sim -> promote."""
    lint = _load("lint")
    promote = _load("promote")
    kinds = [
        {"kind": "cura", "valor": 3},
        {"kind": "protecao", "valor": 3},
        {"kind": "torpor", "valor": 2},
        {"kind": "cura", "valor": 2, "alvo": "aliados"},
        {"kind": "protecao", "valor": 2, "alvo": "aliados"},
        {"kind": "torpor", "valor": 1},
        {"kind": "estabilizar"},
        {"kind": "purga_condicao"},
        {"kind": "cura", "valor": 4},
        {"kind": "dano", "dano_base": 3, "categoria_arma": "leve"},
    ]
    batch = []
    for i, eff in enumerate(kinds):
        batch.append(
            _card(
                100 + i,
                name=f"Trama {chr(65 + i)}",
                efeitos=[eff],
                momento=f"Melhor jogada quando a situação {chr(97 + i)}{chr(97 + i)} {chr(110 + i)}{chr(110 + i)} aparece.",
                descricao="Cinza de fornalha fecha a ferida.",
            )
        )
    batch.append(copy.deepcopy(batch[0]) | {"id": "med_lote_dup", "name": "Cópia Fiel"})
    lote = tmp_path / "lote.json"
    lote.write_text(json.dumps({"cards": batch}), encoding="utf-8")

    report = lint.run(str(lote), exigir_momento=True)
    assert report["cartas"] == 11
    assert "med_lote_dup" in report["reprovadas"]

    sim_report = sim.simulate_batch(
        [c for c in batch if c["id"] in report["verdes"]], [1, 3], ["padrao"], 2, [0, 1]
    )
    cdir = tmp_path / "cards"
    cdir.mkdir()
    res = promote.promote(
        str(lote),
        {**sim_report, **{k: {"bandeiras": []} for k in ("med_lote_dup",)}},
        onda=1,
        autor="teste",
        revisor_voz="dono",
        cards_dir=str(cdir),
        data="2026-10-27",
    )
    assert "med_lote_dup" in res["recusadas"]
    assert res["promovidas"], res
    assert len(res["amostra_voz"]) == max(1, round(len(res["promovidas"]) * 0.2))
    onda = promote.load_ondas(str(cdir))
    assert onda[0]["revisor_voz"] == "dono" and onda[0]["onda"] == 1
    written = json.loads(
        (cdir / "posturas" / "medico_de_campo_boticario.json").read_text(encoding="utf-8")
    )
    assert {c["id"] for c in written["cards"]} == set(res["promovidas"])
    left = json.loads(lote.read_text(encoding="utf-8"))
    assert {c["id"] for c in left["cards"]}.isdisjoint(res["promovidas"])


def test_promote_refuses_without_sim_or_voice_review(tmp_path):
    promote = _load("promote")
    lote = tmp_path / "l.json"
    lote.write_text(json.dumps({"cards": [_card(1)]}), encoding="utf-8")
    cdir = tmp_path / "cards"
    cdir.mkdir()
    no_sim = promote.promote(
        str(lote), {}, onda=1, autor="t", revisor_voz="dono", cards_dir=str(cdir)
    )
    assert "med_lote_1" in no_sim["recusadas"] and not no_sim["promovidas"]
    flagged = promote.promote(
        str(lote),
        {"med_lote_1": {"bandeiras": ["dominante"]}},
        onda=1,
        autor="t",
        revisor_voz="dono",
        cards_dir=str(cdir),
    )
    assert "med_lote_1" in flagged["recusadas"]
    no_voice = promote.promote(
        str(lote),
        {"med_lote_1": {"bandeiras": []}},
        onda=1,
        autor="t",
        revisor_voz="",
        cards_dir=str(cdir),
    )
    assert no_voice.get("erro") and not no_voice["promovidas"]
    assert not os.path.exists(promote.ondas_path(str(cdir)))


def test_voice_sample_is_deterministic_and_at_least_one():
    promote = _load("promote")
    ids = [f"c{i}" for i in range(25)]
    assert promote.voice_sample(ids, 1) == promote.voice_sample(ids, 1)
    assert len(promote.voice_sample(ids, 1)) == 5
    assert len(promote.voice_sample(["a"], 1)) == 1
    assert promote.voice_sample([], 1) == []


def test_metrics_table_and_cut_rule():
    metrics = _load("metrics")
    lines = []
    for i in range(200):
        lines.append(
            json.dumps({"event": "cards.card_offered", "card_id": "baixa", "picked": False})
        )
        lines.append(
            json.dumps({"event": "cards.card_offered", "card_id": "alta", "picked": i < 150})
        )
    for g in ("g1", "g2"):
        lines.append(
            "INFO rpg.cards "
            + json.dumps({"event": "cards.card_played", "card_id": "alta", "game_ref": g})
        )
    lines.append(json.dumps({"event": "cards.card_exhausted", "card_id": "alta"}))
    lines.append("lixo sem json")
    table = metrics.aggregate(lines, {"g1": True, "g2": False})
    assert table["baixa"]["acao"] == "reescrever_ou_cortar" and table["baixa"]["pick_rate"] == 0.0
    assert table["alta"]["acao"] == "nerf" and table["alta"]["pick_rate"] == 0.75
    assert table["alta"]["jogos"] == 2 and table["alta"]["vitoria"] == 0.5
    assert table["alta"]["exaustoes"] == 1
    assert "| alta |" in metrics.render(table)


def test_metrics_below_min_offers_has_no_action():
    metrics = _load("metrics")
    lines = [json.dumps({"event": "cards.card_offered", "card_id": "x", "picked": False})] * 10
    assert metrics.aggregate(lines)["x"]["acao"] == ""


def test_card_events_are_emitted(monkeypatch):
    from services import card_telemetry

    seen = []
    monkeypatch.setattr(
        card_telemetry, "log_event", lambda area, ev, **kw: seen.append((area, ev, kw))
    )
    card_telemetry.offered(["a", "b"], picked="b")
    card_telemetry.picked("b")
    card_telemetry.played("a", "exaurida")
    names = [e for _, e, _ in seen]
    assert names == ["card_offered", "card_offered", "card_picked", "card_played", "card_exhausted"]
    assert seen[1][2]["picked"] is True and seen[0][2]["picked"] is False


def test_painel_counts_cards():
    painel = _load("painel")
    text = painel.build()
    assert "Cartas de jogador" in text and "Por Postura" in text and "Por palavra-chave" in text
