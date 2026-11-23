"""SPEC-428: tamanho-alvo da narracao por tipo de turno (flag RPG_NARRATION_SIZE).

Etapa 1: golden do prompt do narrador no codigo ANTERIOR a spec (`off` = hoje, byte a byte),
uma por classe de turno, nas duas ordens de prompt (RPG_PROMPT_STATIC_FIRST off/on).
`SPEC428_REGEN=1` regrava os arquivos de `tests/fixtures/narration_size_off/` (so vale na Etapa 1).
"""

from __future__ import annotations

import contextlib
import os
import random
from pathlib import Path

import pytest

from tests import spec382_node_cases as cases
from tests.fakes.scripted_llm import ScriptedLLM

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
    return cases.story_state("Viajo para Brekmar.", visited=["nova_arcadia", "brekmar"])


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
        self.update, self.prompts, self.schemas = update, [], []

    def with_structured_output(self, schema=None, *_a, **_k):
        self.schemas.append(schema)
        return self

    def invoke(self, msgs, *_a, **_k):
        self.prompts.append(msgs)
        return self.update if self.update is not None else cases._upd()


def run_node(monkeypatch, case: str, update=None, llm=None):
    """Roda `storyteller_node` no caso e devolve (saida, espiao)."""
    import world_utils
    from agents import storyteller as st

    factory, extra = CASES[case]
    spy = llm or _Spy(update)
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


# ----------------------------------------------------------------- Etapa 2: modulo
from types import SimpleNamespace  # noqa: E402

from services import narration_size as ns  # noqa: E402

# Literal de hoje (copiado de agents/storyteller.py antes da SPEC-428).
TODAYS_OPCOES = (
    "\n    - FECHE com 2 a 3 OPÇÕES concretas de ação, cada uma numa "
    "linha iniciada por '— ', e termine com '— Ou outra ação.' "
    "(dê rumo ao jogador; as opções mecânicas de combate vêm à parte)."
)
SIZE_MARK = "TAMANHO DA RESPOSTA: "


def _turn(**kw):
    base = {
        "world": {"turn_count": 5},
        "dest": None,
        "world_before": {"visited": ["a"]},
        "gancho_novo": "",
        "discovery_events": [],
        "rumor_find": False,
        "world_note": "",
        "scene_state": {},
        "rested_player": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "off"),
        ("off", "off"),
        ("shadow", "shadow"),
        ("on", "on"),
        ("ON", "on"),
        ("true", "off"),
        ("1", "off"),
        ("", "off"),
        ("onn", "off"),
    ],
)
def test_mode_parsing(raw, expected, monkeypatch):
    if raw is None:
        monkeypatch.delenv("RPG_NARRATION_SIZE", raising=False)
    else:
        monkeypatch.setenv("RPG_NARRATION_SIZE", raw)
    assert ns.mode() == expected


_REV = {"gancho_novo": "x <GANCHO_NOVO> y"}
_MED = {"scene_state": {"interlocutor_reason": "meta_to_narrator"}}
_REST = {"rested_player": {"name": "T"}}


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "cena"),
        ({"world": {"turn_count": 1}}, "abertura"),
        ({"world": {"turn_count": 1}, "dest": {"id": "novo"}}, "abertura"),
        ({"dest": {"id": "novo"}}, "local_novo"),
        ({"dest": {"id": "a"}}, "cena"),  # ja visitado
        ({"dest": {"id": "novo"}, **_REV}, "local_novo"),  # empate: 1a visita + gancho
        (_REV, "revelacao"),
        ({"gancho_novo": "<DESFECHO_DE_QUEST>"}, "revelacao"),
        ({"discovery_events": [{"k": 1}]}, "revelacao"),
        ({"rumor_find": True}, "revelacao"),
        ({"world_note": "ENCONTRO NA ESTRADA (rastro): x"}, "revelacao"),
        ({"world_note": "[ECOS DO MUNDO] x", **_REST}, "descanso"),  # pulso nao e revelacao
        ({**_MED, **_REV}, "revelacao"),  # empate: revelacao vence mediacao
        (_MED, "fala_mediada"),
        ({"scene_state": {"interlocutor_reason": "direct_address"}}, "cena"),
        (_REST, "descanso"),
        ({**_MED, **_REST}, "fala_mediada"),  # empate: mediacao vence descanso
        ({"dest": {"id": "a"}, **_REST}, "descanso"),
    ],
)
def test_classify_priority(overrides, expected):
    assert ns.classify(_turn(**overrides)) == expected


def test_targets_table():
    assert set(ns.TARGETS) == {
        "abertura",
        "local_novo",
        "revelacao",
        "fala_mediada",
        "descanso",
        "cena",
    }
    short = {c for c, t in ns.TARGETS.items() if t.shortened}
    assert short == {"cena", "fala_mediada", "descanso"}
    for name, t in ns.TARGETS.items():
        assert t.size_class == name
        if t.shortened:
            assert t.chars_min < t.chars_max and 0 < t.words_min < t.words_max
        else:
            assert (t.chars_min, t.chars_max, t.words_min, t.words_max) == (0, 0, 0, 0)
    assert (ns.TARGETS["cena"].chars_min, ns.TARGETS["cena"].chars_max) == (750, 1000)
    assert (ns.TARGETS["cena"].words_min, ns.TARGETS["cena"].words_max) == (90, 140)
    assert (ns.TARGETS["fala_mediada"].chars_min, ns.TARGETS["fala_mediada"].chars_max) == (
        600,
        900,
    )
    assert (ns.TARGETS["descanso"].chars_min, ns.TARGETS["descanso"].chars_max) == (800, 1100)


def test_opcoes_clause_is_todays_literal():
    assert ns.OPCOES_CLAUSE == TODAYS_OPCOES


def _prompt_for(monkeypatch, case, mode, static_first="off"):
    monkeypatch.setenv("RPG_PROMPT_STATIC_FIRST", static_first)
    if mode is None:
        monkeypatch.delenv("RPG_NARRATION_SIZE", raising=False)
    else:
        monkeypatch.setenv("RPG_NARRATION_SIZE", mode)
    _out, spy = run_node(monkeypatch, case)
    return narrator_system(spy)


@pytest.mark.parametrize("static_first", ["off", "on"])
@pytest.mark.parametrize("case", ["cena", "fala_mediada", "descanso"])
def test_on_mode_prompt_has_class_target(case, static_first, monkeypatch):
    target = ns.TARGETS[case]
    prompt = _prompt_for(monkeypatch, case, "on", static_first)
    assert SIZE_MARK + target.paragraphs in prompt
    assert f"entre {target.words_min} e {target.words_max} palavras" in prompt
    assert ns.PARAGRAPH_RULE_ON in prompt and ns.PARAGRAPH_RULE_OFF + "\n" not in prompt
    if static_first == "on":  # "abaixo": a linha de tamanho fica depois do rotulo dinamico
        assert prompt.index("[ESTADO E CONTEXTO DESTE TURNO") < prompt.index(SIZE_MARK)
    else:
        assert prompt.index(ns.PARAGRAPH_RULE_ON) < prompt.index(SIZE_MARK)


@pytest.mark.parametrize("case", ["local_novo", "revelacao", "abertura"])
def test_on_mode_unshortened_classes_have_no_size_line(case, monkeypatch):
    prompt = _prompt_for(monkeypatch, case, "on")
    assert SIZE_MARK not in prompt
    assert ns.PARAGRAPH_RULE_ON in prompt  # a regra estatica e constante por modo


def test_golden_cases_hit_their_class(monkeypatch):
    """Guarda do proprio golden: cada caso cai na classe que o nome diz."""
    seen = {}
    real = ns.classify

    def spy(t):
        seen["c"] = real(t)
        return seen["c"]

    monkeypatch.setattr(ns, "classify", spy)
    monkeypatch.setenv("RPG_NARRATION_SIZE", "shadow")
    for case in CASES:
        run_node(monkeypatch, case)
        assert seen["c"] == case, case


# ----------------------------------------------------------------- Etapa 3: costura e log
def _size_events(caplog):
    import json

    out = []
    for rec in caplog.records:
        if rec.name != "rpg.narration":
            continue
        out.append(json.loads(rec.getMessage()))
    return out


@pytest.mark.parametrize("static_first", ["off", "on"])
@pytest.mark.parametrize("case", sorted(CASES))
def test_shadow_prompt_equals_off(case, static_first, monkeypatch):
    off = _prompt_for(monkeypatch, case, None, static_first)
    shadow = _prompt_for(monkeypatch, case, "shadow", static_first)
    assert shadow == off


@pytest.mark.parametrize("raw", ["true", "1", "onn", "yes", ""])
def test_near_valid_values_keep_todays_prompt(raw, monkeypatch):
    base = _prompt_for(monkeypatch, "cena", None)
    assert _prompt_for(monkeypatch, "cena", raw) == base
    assert SIZE_MARK not in base


@pytest.mark.parametrize("mode_name", ["shadow", "on"])
def test_shadow_and_on_log_size_class(mode_name, monkeypatch, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="rpg.narration")
    _prompt_for(monkeypatch, "descanso", mode_name)
    events = _size_events(caplog)
    assert len(events) == 1
    ev = events[0]
    assert ev["event"] == "narration.size_class"
    assert (ev["mode"], ev["size_class"], ev["shortened"], ev["chars_max"]) == (
        mode_name,
        "descanso",
        True,
        1100,
    )


def test_log_for_unshortened_class_has_zero_chars_max(monkeypatch, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="rpg.narration")
    _prompt_for(monkeypatch, "local_novo", "on")
    ev = _size_events(caplog)[0]
    assert (ev["size_class"], ev["shortened"], ev["chars_max"]) == ("local_novo", False, 0)


@pytest.mark.parametrize("raw", [None, "off", "true", "1"])
def test_off_logs_nothing(raw, monkeypatch, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    _prompt_for(monkeypatch, "cena", raw)
    assert _size_events(caplog) == []


def test_log_never_carries_narration_text(monkeypatch, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="rpg.narration")
    _prompt_for(monkeypatch, "cena", "on")
    raw = " ".join(r.getMessage() for r in caplog.records if r.name == "rpg.narration")
    assert "Skallgard" not in raw and "Observo" not in raw and "TAMANHO" not in raw


# ----------------------------------------------------------------- Etapa 4: invariantes
def _rich_update():
    from agents.storyteller import FactionImpact, StoryUpdate
    from services.structured_outputs import ProposedQuest, ProposedWorldEvent

    return StoryUpdate(
        narrative="A cena segue calma e tensa.",
        items_gained=["Corda"],
        introduced_npcs=["Mira"],
        faction_impacts=[FactionImpact(faction_id="x", direction="ajudou")],
        proposed_events=[
            ProposedWorldEvent(type="reputation_changed", target_id="nova_arcadia", detail="d")
        ],
        proposed_quests=[ProposedQuest(title="Achar a corda", description="d")],
        beat_completed=True,
    )


def _stable(out) -> str:
    """Dict devolvido pelo no, com mensagens em texto, para comparar entre modos."""
    return repr({k: (repr(v) if k == "messages" else v) for k, v in sorted(out.items())})


@pytest.mark.parametrize("case", ["cena", "descanso", "fala_mediada"])
def test_size_mode_does_not_change_engine_output(case, monkeypatch):
    results = {}
    for mode_name in ("off", "shadow", "on"):
        monkeypatch.setenv("RPG_NARRATION_SIZE", mode_name)
        out, _spy = run_node(monkeypatch, case, update=_rich_update())
        results[mode_name] = _stable(out)
    assert results["off"] == results["shadow"] == results["on"]
    assert "AIMessage" in results["off"]


def test_size_mode_keeps_story_schema(monkeypatch):
    from agents.storyteller import StoryUpdate, StoryUpdateWithRumors

    base = (StoryUpdate.model_json_schema(), StoryUpdateWithRumors.model_json_schema())
    seen = {}
    for mode_name in ("off", "on"):
        monkeypatch.setenv("RPG_NARRATION_SIZE", mode_name)
        _out, spy = run_node(monkeypatch, "cena")
        seen[mode_name] = spy.schemas[0]
        assert (StoryUpdate.model_json_schema(), StoryUpdateWithRumors.model_json_schema()) == base
    assert seen["off"] is seen["on"]


def test_size_on_fallback_llm_aimessage_guard(monkeypatch, caplog):
    import logging

    caplog.set_level(logging.INFO)
    monkeypatch.setenv("RPG_NARRATION_SIZE", "on")
    out, _spy = run_node(monkeypatch, "cena", llm=ScriptedLLM.failing("falha do provedor"))
    assert out["messages"]
    assert any("structured_invalid" in r.getMessage() for r in caplog.records)


def test_options_clause_unchanged_every_class(monkeypatch):
    for case in CASES:
        for mode_name in (None, "shadow", "on"):
            prompt = _prompt_for(monkeypatch, case, mode_name)
            assert TODAYS_OPCOES in prompt, (case, mode_name)


def _npc_prompt(monkeypatch) -> str:
    from langchain_core.messages import HumanMessage

    import agents.npc as npc
    from tests.test_ambient_consumers import _story_state

    seen = {}

    class _LLM:
        def with_structured_output(self, *a, **k):
            return self

        def invoke(self, msgs, *a, **k):
            seen["p"] = str(msgs[0].content)
            raise RuntimeError("so o prompt interessa")

    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: _LLM())
    st = _story_state()
    guard = {
        "name": "Guarda",
        "role": "guarda",
        "persona": "rude",
        "location": "skallgard",
        "memory": [],
        "relationship": 5,
    }
    st.update(
        active_npc_name="Guarda",
        npcs={"Guarda": guard},
        messages=[HumanMessage(content="quem manda aqui?")],
    )
    with contextlib.suppress(RuntimeError):
        npc.npc_actor_node(st)
    return seen["p"]


def _combat_prompt(monkeypatch) -> str:
    from langchain_core.messages import HumanMessage

    import agents.combat as combat
    from tests.test_ambient_consumers import _Spy as _CSpy
    from tests.test_combat_lifecycle import _enemy, _player

    spy = _CSpy()
    monkeypatch.setattr(combat, "get_llm", lambda *a, **k: spy)
    random.seed(1)
    world = {
        "current_location": "Skallgard",
        "current_location_id": "skallgard",
        "turn_count": 3,
        "danger_level": 2,
        "world_clock": {"day": 1, "period": "Manhã"},
    }
    combat.combat_node(
        {
            "game_id": "p428-combat",
            "messages": [HumanMessage(content="ataco o goblin")],
            "player": _player(),
            "enemies": [_enemy(hp=200)],
            "combat": {"active": True},
            "world": world,
            "party": [],
        }
    )
    return "\n".join(spy.prompts)


def test_size_on_does_not_touch_npc_or_combat_prompt(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    prompts = {}
    for mode_name in ("off", "on"):
        monkeypatch.setenv("RPG_NARRATION_SIZE", mode_name)
        prompts[mode_name] = (_npc_prompt(monkeypatch), _combat_prompt(monkeypatch))
    assert prompts["off"] == prompts["on"]
    assert prompts["on"][0] and prompts["on"][1]
    assert all(SIZE_MARK not in p for p in prompts["on"])
