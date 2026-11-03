"""SPEC-387 R26-R27: `draft.py` — vocabulário no schema/prompt, reparo 1×, contagem e comandos certos."""

from __future__ import annotations

import argparse
import importlib.util
import shlex
import sys
from pathlib import Path

import pytest

from tests.test_card_draft import FakeLLM, _raw, draft  # noqa: F401  (fixture `draft`)


def _lote(draft, alvos):
    cartas = []
    for i, alvo in enumerate(alvos):
        raw = _raw(draft, id=f"med_trama_{i}", name=f"Trama {i}")
        for eff in raw.efeitos:
            eff.alvo = alvo
        cartas.append(raw)
    return draft.LoteRascunho(cartas=cartas)


class _Seq:
    """LLM de mentira: devolve `seq[0]` na 1ª chamada e `seq[1]` nas seguintes."""

    def __init__(self, *seq):
        self.seq, self.calls = list(seq), []

    def with_structured_output(self, _model):
        outer = self

        class S:
            def invoke(_s, messages):
                outer.calls.append(messages)
                return outer.seq[min(len(outer.calls) - 1, len(outer.seq) - 1)]

        return S()


def test_alvo_literal_rejects_aliado(draft):
    schema = draft.EfeitoRascunho.model_json_schema()
    enum = schema["properties"]["alvo"]["enum"]
    assert enum == sorted(draft.fx.ALVOS) and "aliado" not in enum
    out = draft.generate(
        _Seq(_lote(draft, ["aliado", None])), "Médico de Campo", "boticario", 2, lore=[]
    )
    motivos = [m for r in out["rejeitadas"] for m in r["motivos"]]
    assert any("alvo 'aliado' fora do catálogo" in m for m in motivos)


def test_prompt_has_escala_and_budget(draft):
    system, _human = draft.build_prompt(
        "Médico de Campo", "boticario", 4, ("comum", "incomum"), [], []
    )
    assert "GRAMÁTICA DE `escala`" in system and "carga" in system
    assert "comum: " in system and "Fôlego 1: [-2, 9]" in system
    assert "EXEMPLO VÁLIDO" in system and '"raridade": "comum"' in system
    assert "1 efeito e ≤ 1 palavra-chave" in system


def test_repair_called_once_and_counts_reported(draft):
    bad = _lote(draft, ["aliado", "aliado", None, None])
    fixed = _lote(draft, [None, None])
    fixed.cartas[0].id, fixed.cartas[1].id = bad.cartas[0].id, bad.cartas[1].id
    llm = _Seq(bad, fixed)
    out = draft.generate(llm, "Médico de Campo", "boticario", 4, lore=[])
    assert len(llm.calls) == 2  # pedido + 1 reparo
    assert out["pedidas"] == 4 and out["entregues"] == 4 and out["rejeitadas"] == []
    assert out["custo_usd_estimado"] > 0
    assert "REPARO" in llm.calls[1][1].content


def test_no_repair_when_nothing_rejected(draft):
    llm = FakeLLM(_lote(draft, [None, None]))
    out = draft.generate(llm, "Médico de Campo", "boticario", 2, lore=[])
    assert len(llm.calls) == 1 and out["entregues"] == 2 and out["pedidas"] == 2


class _Parsed(Exception):
    pass


@pytest.mark.parametrize("idx", [0, 1, 2])
def test_printed_commands_parse(draft, monkeypatch, idx):
    root = Path(draft.__file__).resolve().parents[2]
    cmd = draft.next_commands(str(root / "data/cards/_rascunhos/onda387_x_y.json"), 387)[idx]
    argv = shlex.split(cmd)
    script = next(a for a in argv if a.endswith(".py") and "scripts/cards" in a)
    args = argv[argv.index(script) + 1 :]
    orig = argparse.ArgumentParser.parse_args

    def spy(self, a=None, ns=None):
        orig(self, a, ns)  # SystemExit(2) se os argumentos estiverem errados
        raise _Parsed

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", spy)
    spec = importlib.util.spec_from_file_location(f"cards_cmd_{idx}", root / script)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    with pytest.raises(_Parsed):
        mod.main(args)
    if idx == 0:
        assert "--lote" not in cmd
    if idx == 2:
        assert "--protocolo lote-v2" in cmd


def test_mock_llm_empty_batch_unchanged(draft):
    class Mock:
        is_mock = True

    out = draft.generate(Mock(), "Médico de Campo", "boticario", 3, lore=[])
    assert out == {"cards": [], "rejeitadas": [], "aviso": "sem chave de provider: lote vazio"}
