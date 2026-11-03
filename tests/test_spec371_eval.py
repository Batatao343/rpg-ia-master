"""SPEC-371 R19: avaliador congelado da arena "a luta ensina" (limiares literais).

Este arquivo e `scripts/fauna/arena_saber.py` ficam congelados no commit da Etapa 1 (D7).
Os testes E1-E4 leem o relatorio publicado pela arena e ficam vermelhos ate o produto existir.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "spec371" / "arena-saber-nova_arcadia.json"


def _load():
    spec = importlib.util.spec_from_file_location(
        "arena_saber_371", ROOT / "scripts" / "fauna" / "arena_saber.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_limiares_literais_da_spec():
    m = _load()
    assert m.E1_MIN_REVELADOS == 0.30
    assert m.E2_MIN_GANHO_PP == 3.0
    assert m.E3_MAX_RAZAO_VIT == 0.92
    assert m.E4_MAX_VITORIA_2 == 0.92
    assert m.E4_MAX_PIOR_PP == 2.0
    assert m.LEVEL == 3


def _p(rev, w1, w2, l1=10, l2=10, bid="x"):
    return {
        "id": bid,
        "classe": "c",
        "seed": 0,
        "win1": w1,
        "win2": w2,
        "lost1": l1,
        "lost2": l2,
        "revelado": rev,
    }


def _base():
    """10 pares: 4 revelados (3 vencem as duas, 1 perde a luta 1 e vence a 2), 6 neutros."""
    pairs = [_p(True, True, True, 10, 9) for _ in range(3)] + [_p(True, False, True)]
    return pairs + [_p(False, True, True) for _ in range(3)] + [_p(False, False, False)] * 3


def test_veredito_passa_com_numeros_no_limiar():
    m = _load()
    agg = m.aggregate(_base())
    assert agg["e1_frac_reveladas"] == 0.4
    assert agg["e2_ganho_pp"] == 25.0
    assert agg["e3_razao_vit"] == 0.9
    assert m.verdict(agg) == {"E1": True, "E2": True, "E3": True, "E4": True}


def test_veredito_falha_cada_metrica():
    m = _load()
    base = _base()
    # E1: so 2 de 10 revelados
    e1 = [dict(p, revelado=i < 2) for i, p in enumerate(base)]
    assert not m.verdict(m.aggregate(e1))["E1"]
    # E2: revelados sem ganho (luta 1 ja vencida)
    e2 = [dict(p, win1=True) if p["revelado"] else p for p in base]
    assert not m.verdict(m.aggregate(e2))["E2"]
    # E3: mesma Vitalidade perdida
    e3 = [dict(p, lost2=10) for p in base]
    assert not m.verdict(m.aggregate(e3))["E3"]
    # E4: luta 2 vence tudo (>92 %)
    e4 = [dict(p, win2=True) for p in base * 3]
    assert not m.verdict(m.aggregate(e4))["E4"]
    # E4: criatura piora mais de 2 pp
    e4b = [dict(p, id="y", win1=True, win2=False) if i == 4 else p for i, p in enumerate(base)]
    assert not m.verdict(m.aggregate(e4b))["E4"]


def test_e5_determinismo_relatorio_byte_identico(monkeypatch):
    m = _load()
    for k, v in m.FLAGS_ON.items():
        monkeypatch.setenv(k, v)
    kw = dict(ids=["mon_arame_vivo"], classes=["Sangromante"])
    a = m.run("nova_arcadia", 2, **kw)
    b = m.run("nova_arcadia", 2, **kw)
    assert m.dumps(a) == m.dumps(b)
    assert m.relatorio(a) == m.relatorio(b)


def _report():
    if not REPORT.exists():
        pytest.fail("relatorio da arena ausente: rode scripts/fauna/arena_saber.py (Etapa 6)")
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "metric",
    [
        "E1",
        "E2",
        "E3",
        pytest.param(
            "E4",
            marks=pytest.mark.xfail(
                strict=True,
                reason="SPEC-371 §9: desvio do E4 aceito pelo dono em 03/11 (−3,0 pp, ruído de 20 seeds)",
            ),
        ),
    ],
)
def test_arena_a_luta_ensina(metric):
    rep = _report()
    m = _load()
    # recalcula o veredito pelo avaliador congelado (nao confia no campo gravado)
    assert m.verdict(rep["agregado"])[metric], rep["agregado"]


# --- Correcao do harness (handoffs/SPEC-371-eval-authoring.md) ---------------------------------
_GATILHO = [{"prenuncio": True, "contra_jogo": "x", "actor_id": "e1"}]


def test_leitor_escolhe_reacao_preparada_quando_a_linha_pede(monkeypatch):
    m = _load()
    for k, v in m.FLAGS_ON.items():
        monkeypatch.setenv(k, v)
    player = m._arena().hero("Sangromante", m.LEVEL)
    assert "san_esquiva" in player["prepared_cards"]
    assert m.reacao_disponivel(player, "san_esquiva")
    decl = m.leitor_decl(player, "e1", _GATILHO)
    assert decl.reaction_card_id == "san_esquiva"
    assert decl.acao.kind != "maneuver"  # a reacao nao gasta a Acao


def test_leitor_cai_para_guardar_sem_reacao_disponivel(monkeypatch):
    m = _load()
    for k, v in m.FLAGS_ON.items():
        monkeypatch.setenv(k, v)
    player = m._arena().hero("Sangromante", m.LEVEL)
    player["entropy"] = 0
    assert not m.reacao_disponivel(player, "san_esquiva")
    decl = m.leitor_decl(player, "e1", _GATILHO)
    assert decl.reaction_card_id is None
    assert decl.acao.kind == "maneuver" and decl.acao.maneuver == "guardar"
    # Carta ativa nunca conta como reacao
    assert not m.reacao_disponivel(player, "san_passo")


def test_reacao_por_turno_volta_na_rodada_seguinte(monkeypatch):
    """`run_round` zera o uso `turno` antes da janela de reacao: usada na rodada anterior, a
    reacao `turno` segue disponivel; uma reacao `cena` ja usada nao."""
    m = _load()
    for k, v in m.FLAGS_ON.items():
        monkeypatch.setenv(k, v)
    from services import cards

    player = m._arena().hero("Sangromante", m.LEVEL)
    assert cards.get_card("san_esquiva")["frequencia"] == "turno"
    player["card_usage"] = {"san_esquiva": {"used_this_turn": 1, "used_this_scene": 1}}
    assert m.reacao_disponivel(player, "san_esquiva")
    assert m.leitor_decl(player, "e1", _GATILHO).reaction_card_id == "san_esquiva"
    devoto = m._arena().hero("Devoto do Abismo", m.LEVEL)
    assert cards.get_card("dev_ombro_porta")["frequencia"] == "cena"
    devoto["card_usage"] = {"dev_ombro_porta": {"used_this_turn": 1, "used_this_scene": 1}}
    assert not m.reacao_disponivel(devoto, "dev_ombro_porta")
