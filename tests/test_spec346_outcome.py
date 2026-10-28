"""SPEC-346 R11-R18: o desfecho do combate é narrado (uma chamada), sem números, e o loot não o apaga."""

from __future__ import annotations

import random
import re

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.combat as combat
import agents.loot as loot
from llm_setup import FallbackLLM
from services import conflict_orchestrator as orch
from services import conflict_summary as summ
from services import prose_guard, round_log
from services import turn_outcome as to
from tests.fixtures import spec346_smoke as smoke
from tests.test_encounter_identity_repro import _scan, _start_state
from tests.test_spec346_board_no_llm import _after_open, _attack_decl, _open

FAINT = "Saqueador de Barba de Cobre"


@pytest.fixture(autouse=True)
def _board_on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    random.seed(11)


class _FastLLM:
    """LLM simulada: devolve `text` e conta as chamadas por tier."""

    def __init__(self, calls, tier, text, scan):
        self.calls, self.tier, self.text, self.scan = calls, tier, text, scan
        self.is_fallback = False

    def with_structured_output(self, schema, **_kw):
        owner = self

        class _S:
            def invoke(self, _m):
                owner.calls.append((schema.__name__, owner.tier))
                if schema is combat.EncounterScanner and owner.scan is not None:
                    return owner.scan
                raise RuntimeError("sem structured output")

        return _S()

    def invoke(self, _messages):
        self.calls.append(("invoke", self.tier))
        return AIMessage(content=self.text)


def _install(monkeypatch, text=smoke.GOOD_SUMMARY, scan=None):
    calls: list = []
    scan = scan or _scan(("Goblin", 1))
    monkeypatch.setattr(
        combat, "get_llm", lambda temperature=0.0, tier=None, **k: _FastLLM(calls, tier, text, scan)
    )
    return calls


def _force_victory(monkeypatch, *, nonlethal=True):
    def fake_round(scene, actors_by_id, sides, round_state, *a, **k):
        for eid in sides["enemy"]:
            actor = actors_by_id[eid]
            actor["name"] = FAINT
            if nonlethal:
                actor.update(incapacitated=True, nonlethal_by="player", status="incapacitado")
            else:
                actor.update(dead=True, status="morto")
            actor["vitalidade"] = 0
        atk = {
            "actor_id": "player",
            "target_id": sides["enemy"][0],
            "dice_rolled": [4, 6],
            "dice_kept": [4, 6],
            "virtude": 3,
            "modificador": 0,
            "total": 13,
            "esquiva_alvo": 9,
            "resultado": "acerto",
            "acerto": True,
            "dano_final": 6,
        }
        return {
            "logs": ["Você → Saqueador: acerto (total 13 vs Esquiva 9)."],
            "deaths": [],
            "terminal": [],
            "abyss": [],
            "attacks": [atk],
            "reactions": [],
            "last_stands": [],
            "stabilizations": [],
            "scars_pending": [],
            "resolved_turns": ["player"],
            "cards_used": [],
            "recidiva_event": None,
            "reason": "victory",
            "ended": True,
            "player_dead": False,
        }

    monkeypatch.setattr(orch, "run_round", fake_round)


def _victory_on(monkeypatch, text=smoke.GOOD_SUMMARY):
    state, res = _open(monkeypatch, scan=_scan(("Goblin", 1)))
    calls = _install(monkeypatch, text=text)
    nxt = _after_open(state, res)
    nxt["messages"] = [*nxt["messages"], HumanMessage(content="Jogo a carta")]
    nxt["combat_declaration"] = _attack_decl(nxt)
    _force_victory(monkeypatch)
    return calls, nxt, combat._combat_node(nxt)


def test_outcome_summary_single_call_on(monkeypatch):
    calls, _state, out = _victory_on(monkeypatch)
    fast = [c for c in calls if c[1].value == "fast"]
    assert len(fast) == 1 and len(calls) == 1
    text = out["messages"][0].content
    assert smoke.GOOD_SUMMARY in text
    assert "\n\n" in text  # registro + linha em branco + resumo
    registry = text.split(smoke.GOOD_SUMMARY)[0]
    assert "ataca" in registry and "6 de dano" in registry  # o registro vem ANTES do resumo
    assert out["next"] == "loot" and out["conflict_summary"]
    assert not re.search(r"\d", text.split("\n\n")[-1])


def test_outcome_facts_have_no_digits():
    player = {
        "name": "Ysolde",
        "vitalidade": 3,
        "max_vitalidade": 30,
        "equipment": {"weapon": "Espada Gasta"},
        "ferimentos": {"leve": [{"regiao": "perna_direita"}], "grave": [], "critico": []},
        "post_combat_state": None,
    }
    summary = {"mortos": ["Goblin 2"], "fugitivos": ["Lobo 1"], "rendidos": [], "caidos": []}
    enemies = [{"name": "Orc 3", "status": "ativo", "vitalidade": 5, "max_vitalidade": 20}]
    for outcome in ("victory", "death", "fled", "surrendered_enemy", "expired", "defeat"):
        facts = round_log.outcome_facts(outcome, summary, player, enemies, {})
        text = "\n".join(facts)
        assert not re.search(r"\d", text), (outcome, text)
        assert "Espada Gasta" in text
    glossary = combat._narrate_outcome  # o glossário vive no prompt do resumo
    assert glossary is not None


def test_outcome_prompt_separates_vitalidade_from_folego(monkeypatch):
    captured = {}

    class _Cap(_FastLLM):
        def invoke(self, messages):
            captured["system"] = messages[0].content
            return super().invoke(messages)

    monkeypatch.setattr(
        combat, "get_llm", lambda temperature=0.0, tier=None, **k: _Cap([], tier, "Fim.", None)
    )
    player = {"name": "Ysolde", "equipment": {"weapon": "Espada Gasta"}}
    combat._narrate_outcome(
        "victory", {"mortos": [FAINT]}, player, [], {}, "ataco", "", manifest=None
    )
    system = captured["system"]
    assert "Fôlego" in system and "Vitalidade" in system
    assert "Espada Gasta" in system
    assert "NÃO escreva números" in system


@pytest.mark.parametrize("key", list(smoke.LEAKS))
def test_strip_mechanic_numbers_on_smoke_texts(key):
    text, removed = prose_guard.strip_mechanic_numbers(smoke.LEAKS[key])
    assert removed >= 1
    assert not re.search(r"\d", text) or key == "critico", text
    assert "  " not in text and " ," not in text and " ." not in text, repr(text)
    assert "contra a esquiva" not in text and "→" not in text
    assert "fôlegos" not in text


def test_strip_numbers_critical_sample_is_clean():
    text, _ = prose_guard.strip_mechanic_numbers(smoke.LEAKS["critico"])
    assert "16" not in text and "5 contra 12" not in text and "vitalidade" not in text


def test_strip_numbers_leaves_clean_prose_alone():
    clean = "O goblin cai de joelhos; dois saqueadores recuam."
    assert prose_guard.strip_mechanic_numbers(clean) == (clean, 0)


def test_soft_hyphen_normalized():
    assert (
        prose_guard.strip_mechanic_numbers(smoke.SOFT_HYPHEN)[0]
        == "A lâmina que desferi-o rasga o ar."
    )


def test_numbers_stripped_event_is_emitted(monkeypatch):
    events = []
    monkeypatch.setattr(combat, "_log_event", lambda *a, **k: events.append((a[:2], k)))
    _install(monkeypatch, text=smoke.LEAKS["seta_parenteses"])
    out = combat._narrate_outcome(
        "victory", {"mortos": []}, {"name": "Y"}, [], {}, "ataco", "", manifest=None
    )
    assert "→" not in out
    assert any(e[0] == ("combat", "narration_numbers_stripped") and e[1]["count"] for e in events)


def test_contradiction_falls_back(monkeypatch):
    _install(monkeypatch, text=smoke.CONTRADICTION)
    summary = {"mortos": [FAINT], "caidos": [], "inconscientes": []}
    out = combat._narrate_outcome(
        "victory", summary, {"name": "Y", "equipment": {}}, [], {}, "ataco", "", manifest=None
    )
    assert "sobrevive" not in out and "foge" not in out
    assert FAINT in out  # o fallback diz o que o motor diz


@pytest.mark.parametrize(
    "outcome", ["victory", "fled", "death", "defeat", "surrendered_enemy", "expired"]
)
def test_fallback_is_readable(monkeypatch, outcome):
    monkeypatch.setattr(combat, "get_llm", lambda **k: FallbackLLM("sem chave"))
    summary = {"mortos": [FAINT + " 2"], "inconscientes": ["Orc 1"], "caidos": [], "fugitivos": []}
    player = {"name": "Ysolde", "ferimentos": {"leve": [{"regiao": "perna"}]}}
    out = combat._narrate_outcome(outcome, summary, player, [], {}, "ataco", "", manifest=None)
    assert out.strip()
    assert "•" not in out and "⚔️" not in out and "☠️" not in out
    assert not re.search(r"\d", out), out
    assert not re.search(r"\b[a-z]+_[a-z0-9_]+\b", out)  # ids


def test_death_on_appends_wheel_text(monkeypatch):
    _install(monkeypatch, text=smoke.GOOD_SUMMARY)
    state, res = _open(monkeypatch)
    calls = []
    nxt = _after_open(state, res)
    nxt["messages"] = [*nxt["messages"], HumanMessage(content="Jogo a carta")]
    nxt["combat_declaration"] = _attack_decl(nxt)
    real = orch.run_round

    def killer(*a, **k):
        out = real(*a, **k)
        out.update(player_dead=True, ended=True, reason="derrota")
        a[1]["player"]["dead"] = True
        return out

    monkeypatch.setattr(orch, "run_round", killer)
    out = combat._combat_node(nxt)
    text = out["messages"][0].content
    assert text.rstrip().endswith(round_log.WHEEL_TEXT)
    assert "• " not in text and "☠️" not in text
    assert out["death_pending"] is True
    assert calls == []


def test_death_off_no_bullets(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    monkeypatch.setattr(combat, "get_llm", lambda **k: FallbackLLM("sem chave"))
    state = _start_state(hint="Goblin")
    state["enemies"] = [
        orch.ensure_combat_sheet({"id": "g_1", "name": "Goblin", "status": "ativo"})
    ]
    state["combat"] = {"active": True}
    state["messages"] = [HumanMessage(content="ataco")]
    state["combat_declaration"] = {"actor_id": "player", "acao": {"kind": "pass"}}

    def killer(scene, actors, sides, rs, *a, **k):
        actors["player"]["dead"] = True
        return {
            "logs": ["Goblin → Ysolde: acerto (total 13 vs Esquiva 9)."],
            "deaths": ["player"],
            "terminal": [],
            "abyss": [],
            "attacks": [],
            "reactions": [],
            "last_stands": [],
            "stabilizations": [],
            "scars_pending": [],
            "resolved_turns": ["player"],
            "cards_used": [],
            "recidiva_event": None,
            "reason": "derrota",
            "ended": True,
            "player_dead": True,
        }

    monkeypatch.setattr(orch, "run_round", killer)
    out = combat._combat_node(state)
    text = out["messages"][0].content
    assert "• " not in text and "⚔️" not in text
    assert text.rstrip().endswith(round_log.WHEEL_TEXT)


def test_off_victory_keeps_round_narration_and_loot_line(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    calls = _install(monkeypatch, text="A lâmina encontra o saqueador e o campo silencia.")
    state = _start_state(hint="Goblin")
    state["enemies"] = [
        orch.ensure_combat_sheet(
            {"id": "g_1", "name": FAINT, "status": "ativo", "categoria": "padrao"}
        )
    ]
    state["combat"] = {"active": True}
    state["messages"] = [HumanMessage(content="ataco")]
    state["combat_declaration"] = {"actor_id": "player", "acao": {"kind": "pass"}}
    _force_victory(monkeypatch)
    out = combat._combat_node(state)
    narration = out["messages"][0].content
    assert "campo silencia" in narration  # a narração da rodada final É o desfecho
    assert any(c[1].value == "fast" for c in calls)
    # junta com o loot pós-vitória (sem LLM): o texto do turno tem as duas partes
    merged = {**state, **{k: v for k, v in out.items() if k != "messages"}}
    merged["messages"] = [*state["messages"], *out["messages"]]
    random.seed(3)
    loot_out = loot.loot_node({**merged, "loot_source": "TREASURE", "next": "loot"})
    merged["messages"] = [*merged["messages"], *loot_out["messages"]]
    text = to._turn_ai_text(merged)
    assert text.startswith(narration.strip())
    assert "[SISTEMA]" not in text
    assert "ouro" in text.lower()
    assert text != "Saqueador de Barba de Cobre perde os sentidos."


def test_loot_post_victory_no_llm_and_message_kind(monkeypatch):
    _install(monkeypatch)
    _calls, state, out = _victory_on(monkeypatch)
    merged = {**state, **{k: v for k, v in out.items() if k != "messages"}}
    merged["messages"] = [*state["messages"], *out["messages"]]

    def boom(*a, **k):
        raise AssertionError("o loot pós-vitória não chama LLM")

    monkeypatch.setattr(loot, "get_llm", boom)
    random.seed(5)
    loot_out = loot.loot_node({**merged, "loot_source": "TREASURE", "next": "loot"})
    text = loot_out["messages"][0].content
    assert text.startswith("[SISTEMA]")
    assert FAINT not in text  # sem repetir o resumo canônico
    result = loot_out["combat"]["result"]
    assert result["loot_claimed"] is True and "loot_turn" in result and "location_id" in result
    merged = {**merged, **{k: v for k, v in loot_out.items() if k != "messages"}}
    merged["messages"] = [*merged["messages"], *loot_out["messages"]]
    merged["next"] = "loot"
    from services.presentation_history import message_kind

    assert message_kind(merged) == "COMBAT"
    full = to._turn_ai_text(merged)
    assert smoke.GOOD_SUMMARY in full and "ouro" in full.lower()


def test_single_ai_message_turn_unchanged():
    msgs = [HumanMessage(content="olho"), AIMessage(content="Uma estrada.\n[RESULTADO] +1 ouro")]
    assert to._turn_ai_text({"messages": msgs}) == "Uma estrada.\n[RESULTADO] +1 ouro"
    assert to._turn_ai_text({"messages": [HumanMessage(content="x")]}) == ""
    assert to._turn_ai_text({"messages": []}) == ""


def test_multi_ai_messages_join_in_order_dedup_and_strip():
    msgs = [
        AIMessage(content="turno anterior"),
        HumanMessage(content="ataco"),
        AIMessage(content="O saqueador tomba."),
        AIMessage(content="[SISTEMA] Maça de Ferro (incomum) e +12 de ouro"),
        AIMessage(content="O saqueador tomba."),
    ]
    text = to._turn_ai_text({"messages": msgs})
    assert text == "O saqueador tomba.\n\nMaça de Ferro (incomum) e +12 de ouro"


def test_stream_final_extends_shown():
    """R17 x SPEC-316: o texto da 1ª mensagem (o que foi ao vivo) é prefixo do texto final."""
    first = "A lâmina encontra o saqueador."
    msgs = [HumanMessage(content="a"), AIMessage(content=first), AIMessage(content="[SISTEMA] x")]
    assert to._turn_ai_text({"messages": msgs}).startswith(first)


def test_summary_text_helper_still_ok():
    assert "tomba" in summ.player_summary_text({"mortos": ["Goblin"]})


def test_no_digits_leaves_clean_punctuation():
    assert round_log._no_digits("Alvo 3 , ok.") == "Alvo, ok."
    assert round_log._no_digits("Goblin 2 e Goblin 3 caem.") == "Goblin e Goblin caem."
