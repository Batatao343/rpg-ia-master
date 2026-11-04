"""SPEC-369 R12 (B1): `draft.py` com orçamento e raridade na triagem, reparo com score/faixa e
ajuste determinístico (D-369-5); `services/card_budget_fit` equivale ao `_fit_orcamento` antigo."""

from __future__ import annotations

import copy
import glob
import json
import os

from langchain_core.messages import AIMessage

from services import card_effects as fx
from services import card_lint
from services.card_budget_fit import fit_orcamento
from tests.test_card_draft import ROOT, FakeLLM, _raw, draft  # noqa: F401  (fixture `draft`)


class Seq:
    def __init__(self, *seq):
        self.seq, self.calls = list(seq), []

    def with_structured_output(self, _model):
        outer = self

        class S:
            def invoke(_s, messages):
                outer.calls.append(messages)
                return outer.seq[min(len(outer.calls) - 1, len(outer.seq) - 1)]

        return S()


def _dano(draft, i, dano):
    return _raw(
        draft,
        id=f"med_golpe_{i}",
        name=f"Golpe {i}",
        efeitos=[{"kind": "dano", "alvo": "inimigos", "dano_base": dano}],
        descricao="Cinza de fornalha corta o ar.",
    )


def _lote(draft, danos):
    return draft.LoteRascunho(cartas=[_dano(draft, i, d) for i, d in enumerate(danos)])


def _gen(draft, llm):
    return draft.generate(llm, "Médico de Campo", "boticario", 4, lore=[])


def test_triagem_reprova_fora_do_orcamento(draft):
    out = _gen(draft, Seq(_lote(draft, [3, 40]), AIMessage(content="erro")))
    assert [c["id"] for c in out["cards"]] == ["med_golpe_0"]
    assert any("fora do orçamento" in m for r in out["rejeitadas"] for m in r["motivos"])


def test_triagem_reprova_raridade(draft):
    raw = _raw(
        draft,
        efeitos=[
            {"kind": "cura", "valor": 2},
            {"kind": "dano", "alvo": "inimigos", "dano_base": 1},
        ],
    )
    out = _gen(draft, Seq(draft.LoteRascunho(cartas=[raw]), AIMessage(content="x")))
    assert out["cards"] == []
    assert any("comum com 2 efeitos" in m for r in out["rejeitadas"] for m in r["motivos"])


def test_reparo_recebe_power_score_e_faixa(draft):
    llm = Seq(_lote(draft, [3, 40]), AIMessage(content="erro"))
    _gen(draft, llm)
    assert len(llm.calls) == 2
    pedido = llm.calls[1][1].content
    assert "power_score" in pedido and "faixa" in pedido
    assert "reduza poder em" in pedido and "79.5" in pedido and "[4.0, 13.0]" in pedido


def test_reparo_aumenta_quando_abaixo(draft):
    raw = _raw(draft, efeitos=[{"kind": "cura", "valor": 1}], custo_entropia=3)
    llm = Seq(draft.LoteRascunho(cartas=[raw]), AIMessage(content="erro"))
    _gen(draft, llm)
    assert len(llm.calls) == 2
    assert "aumente poder em" in llm.calls[1][1].content


def test_ajuste_deterministico_poe_na_faixa(draft):
    # reparo devolve a mesma Carta fora da faixa: o ajuste (dano 10 -> 7) resolve
    ruim = _lote(draft, [10])
    out = _gen(draft, Seq(ruim, ruim))
    assert out["rejeitadas"] == [] and len(out["cards"]) == 1
    carta = out["cards"][0]
    assert carta["ajuste_orcamento"] and len(carta["ajuste_orcamento"]) <= 6
    assert card_lint.check_budget(carta) == []


def test_ajuste_desiste_e_rejeita(draft):
    ruim = _lote(draft, [40])
    out = _gen(draft, Seq(ruim, ruim))
    assert out["cards"] == []
    motivos = [m for r in out["rejeitadas"] for m in r["motivos"]]
    assert any("ajuste de orçamento" in m for m in motivos)


def test_ajuste_sem_passo_possivel_tem_motivo_proprio(draft):
    raw = _raw(draft, efeitos=[{"kind": "cura", "valor": 1}], custo_entropia=3)
    ruim = draft.LoteRascunho(cartas=[raw])
    out = _gen(draft, Seq(ruim, ruim))
    assert out["cards"] == []
    motivos = [m for r in out["rejeitadas"] for m in r["motivos"]]
    assert any("sem passo possível" in m for m in motivos)
    assert not any("não coube" in m for m in motivos)


def test_lote_final_so_tem_cartas_no_orcamento(draft):
    bom, ruim = _lote(draft, [3, 4, 40, 10]), _lote(draft, [40, 10])
    ruim.cartas[0].id, ruim.cartas[1].id = "med_golpe_2", "med_golpe_3"
    out = _gen(draft, Seq(bom, ruim))
    assert out["cards"] and all(card_lint.check_budget(c) == [] for c in out["cards"])


def test_reparo_fallback_llm(draft):
    out = _gen(draft, Seq(_lote(draft, [3, 40]), AIMessage(content="erro do provider")))
    assert [c["id"] for c in out["cards"]] == ["med_golpe_0"]


# --- D-369-5: equivalência do módulo extraído com o `_fit_orcamento` antigo ---
def _fit_orcamento_antigo(card: dict) -> dict:
    """Cópia congelada de `scripts/bestiario/gerar_mecanica._fit_orcamento` (pré-SPEC-369)."""
    for _ in range(40):
        if not fx.budget_error(card):
            break
        band = fx.budget_band(card)
        if band is None:
            break
        fol = fx.custo_folego(card)
        if fx.power_score(card) > band[1]:
            if fol < 3:
                card["custo_folego"] = fol + 1
                continue
            alvo = max(
                (
                    e
                    for e in (card.get("efeitos") or [card["efeito"]])
                    if e.get("kind") == "dano" and e.get("dano_base", 0) > 1
                ),
                key=lambda e: int(e["dano_base"]),
                default=None,
            )
            if alvo is None:
                break
            alvo["dano_base"] = int(alvo["dano_base"]) - 1
        elif fol > 0:
            card["custo_folego"] = fol - 1
        else:
            break
    card["efeito"] = fx.primary_effect(card) or card["efeito"]
    return card


def _cartas_inimigas() -> list[dict]:
    cartas: list[dict] = []
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "cards", "inimigos", "*.json"))):
        if os.path.basename(path).startswith("_"):
            continue
        with open(path, encoding="utf-8") as fh:
            cartas += json.load(fh).get("cards", [])
    return cartas


def test_fit_equivale_ao_antigo_na_saida_do_bestiario():
    cartas = _cartas_inimigas()
    assert len(cartas) > 50
    n = 0
    for base in cartas:
        for adj in (0, 2, 5, -2):
            c = copy.deepcopy(base)
            for e in c.get("efeitos") or [c["efeito"]]:
                if e.get("kind") == "dano":
                    e["dano_base"] = max(1, int(e["dano_base"]) + adj)
            c["efeito"] = fx.primary_effect(c) or c["efeito"]
            novo = fit_orcamento(copy.deepcopy(c))
            assert novo == _fit_orcamento_antigo(copy.deepcopy(c)), (base["id"], adj)
            n += 1
    assert n > 200
