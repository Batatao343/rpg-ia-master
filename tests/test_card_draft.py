"""SPEC-336 R2: rascunho por LLM — guard de FallbackLLM e só vocabulário fechado."""

import importlib.util
import json
import os
import sys

import pytest
from langchain_core.messages import AIMessage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def draft():
    path = os.path.join(ROOT, "scripts", "cards", "draft.py")
    spec = importlib.util.spec_from_file_location("cards_draft", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Structured:
    def __init__(self, result, sink):
        self.result, self.sink = result, sink

    def invoke(self, messages):
        self.sink.append(messages)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeLLM:
    def __init__(self, result):
        self.result, self.calls = result, []

    def with_structured_output(self, model):
        self.model = model
        return _Structured(self.result, self.calls)


def _raw(draft, **over):
    base = {
        "id": "Med Trama",
        "name": "Trama de Cinza",
        "tipo": "ativa",
        "raridade": "comum",
        "custo_entropia": 1,
        "efeitos": [{"kind": "cura", "valor": 3}],
        "descricao": "Cinza de fornalha fecha a ferida.",
        "momento": "Melhor jogada quando um aliado sangra.",
    }
    base.update(over)
    return draft.CartaRascunho(**base)


def test_fallback_message_gives_empty_batch(draft):
    llm = FakeLLM(AIMessage(content="erro do provider"))
    out = draft.generate(llm, "Médico de Campo", "boticario", 6, lore=[])
    assert out["cards"] == [] and "vazio" in out["aviso"]


def test_provider_exception_gives_empty_batch(draft):
    out = draft.generate(FakeLLM(RuntimeError("429")), "Médico de Campo", "boticario", 6, lore=[])
    assert out["cards"] == [] and "RuntimeError" in out["aviso"]


def test_mock_llm_never_invents_cards(draft):
    from mock_llm import MockLLM

    out = draft.generate(MockLLM(), "Médico de Campo", "boticario", 6, lore=[])
    assert out["cards"] == [] and "sem chave" in out["aviso"]


def test_output_only_in_closed_vocabulary(draft):
    lote = draft.LoteRascunho(
        cartas=[
            _raw(draft),
            _raw(draft, id="med_ruim", efeitos=[{"kind": "cura_milagrosa", "valor": 3}]),
            _raw(draft, id="med_kw", palavras_chave={"furia": True}),
            _raw(draft, id="Med Trama"),  # id repetido no lote
        ]
    )
    out = draft.generate(FakeLLM(lote), "Médico de Campo", "boticario", 4, onda=3, lore=[])
    assert [c["id"] for c in out["cards"]] == ["med_trama"]
    assert {r["id"] for r in out["rejeitadas"]} == {"med_ruim", "med_kw", "med_trama"}
    card = out["cards"][0]
    assert card["classe"] == "Médico de Campo" and card["onda"] == 3 and card["versao"] == 1
    assert card["patamar"] == "inicial" and card["origem"] == "onda-3"


def test_prompt_carries_vocabulary_wheel_and_existing(draft):
    llm = FakeLLM(draft.LoteRascunho(cartas=[]))
    draft.generate(llm, "Médico de Campo", "boticario", 4, lore=["Trecho de lore de Valoria."])
    system, human = (m.content for m in llm.calls[0])
    assert "VOCABULÁRIO FECHADO" in system and "Rachadura" in system
    assert "NUNCA" in system and "dano alto" in system
    assert "Trecho de lore de Valoria." in human and "Médico de Campo" in human


def test_write_batch_goes_to_drafts_dir_outside_pool(draft, tmp_path):
    out = {"cards": [{"id": "med_a"}], "rejeitadas": [], "aviso": ""}
    path = draft.write_batch(out, "Médico de Campo", "boticario", 2, str(tmp_path / "_rascunhos"))
    assert os.path.basename(os.path.dirname(path)).startswith("_")
    assert json.load(open(path, encoding="utf-8"))["cards"][0]["id"] == "med_a"


def test_cli_without_key_writes_empty_batch_with_warning(draft, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(draft, "DRAFT_DIR", str(tmp_path / "_rascunhos"))
    monkeypatch.setattr(draft, "write_batch", lambda *a, **k: str(tmp_path / "x.json"))
    rc = draft.main(["--postura", "Médico de Campo", "--subclasse", "boticario", "--n", "3"])
    assert rc == 0
    assert "AVISO" in capsys.readouterr().out  # RPG_FORCE_MOCK=1 na suíte = sem chave


def test_unknown_postura_is_rejected(draft):
    assert draft.main(["--postura", "Bardo", "--subclasse", "x"]) == 2
