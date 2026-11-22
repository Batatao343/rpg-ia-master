"""SPEC-428: tamanho-alvo da narracao por tipo de turno (flag RPG_NARRATION_SIZE).

Etapa 1: golden do prompt do narrador no codigo ANTERIOR a spec (`off` = hoje, byte a byte),
uma por classe de turno, nas duas ordens de prompt (RPG_PROMPT_STATIC_FIRST off/on).
`SPEC428_REGEN=1` regrava os arquivos de `tests/fixtures/narration_size_off/` (so vale na Etapa 1).
"""

from __future__ import annotations

import os
import random
from pathlib import Path

import pytest

from tests import spec382_node_cases as cases

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "narration_size_off"
_NO_ENC = lambda *a, **k: None  # noqa: E731 - patch de check_encounter


def _state_cena():
    return cases.story_state()


def _state_abertura():
    return cases.story_state("Começo a aventura.", turn_count=1)


def _state_local_novo():
    return cases.story_state("Viajo para Brekmar.")


def _state_revelacao():
    # Brekmar ja visitado (nao e local novo) + armadilha na estrada: nota "ENCONTRO NA ESTRADA".
    st = cases.story_state("Viajo para Brekmar.", visited=["nova_arcadia", "brekmar"])
    return st


def _state_fala_mediada():
    st = cases.story_state("Narrador, o que Mira sabe sobre isso?")
    st["interlocutor_reason"] = "meta_to_narrator"
    return st


def _state_descanso():
    return cases.story_state("Descanso até o amanhecer.")


# classe -> (fabrica do estado, patches extras do turno)
CASES = {
    "cena": (_state_cena, []),
    "abertura": (_state_abertura, []),
    "local_novo": (_state_local_novo, []),
    "revelacao": (_state_revelacao, ["trap"]),
    "fala_mediada": (_state_fala_mediada, []),
    "descanso": (_state_descanso, []),
}


class _Spy:
    """LLM roteirizado: grava o prompt e devolve a mesma StoryUpdate."""

    def __init__(self, update=None):
        self.update, self.prompts = update, []

    def with_structured_output(self, *_a, **_k):
        return self

    def invoke(self, msgs, *_a, **_k):
        self.prompts.append(msgs)
        return self.update if self.update is not None else cases._upd()


def run_node(monkeypatch, case: str, update=None):
    """Roda `storyteller_node` no caso e devolve (saida, espiao)."""
    import world_utils
    from agents import storyteller as st

    factory, extra = CASES[case]
    spy = _Spy(update)
    monkeypatch.setattr(st, "get_llm", lambda *a, **k: spy)
    monkeypatch.setattr(st, "check_encounter", cases._enc(reason="x") if extra else _NO_ENC)
    if "trap" in extra:
        monkeypatch.setattr(world_utils, "roll_encounter_type", lambda danger: "trap")
    random.seed(1)
    return st.storyteller_node(factory()), spy


def narrator_system(spy) -> str:
    return str(spy.prompts[0][0].content)


@pytest.mark.parametrize("static_first", ["off", "on"])
@pytest.mark.parametrize("case", sorted(CASES))
def test_narrator_prompt_off_matches_golden(case, static_first, monkeypatch):
    monkeypatch.setenv("RPG_PROMPT_STATIC_FIRST", static_first)
    monkeypatch.delenv("RPG_NARRATION_SIZE", raising=False)
    _out, spy = run_node(monkeypatch, case)
    got = narrator_system(spy)
    path = GOLDEN_DIR / f"{case}-{static_first}.txt"
    if os.getenv("SPEC428_REGEN") == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(got, encoding="utf-8", newline="\n")
        pytest.skip("golden regravado")
    assert got == path.read_text(encoding="utf-8")
