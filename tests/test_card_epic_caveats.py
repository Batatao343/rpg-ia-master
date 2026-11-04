"""SPEC-393: arestas do smoke das ressalvas do épico de Cartas (R1-R6)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import api
import persistence
from services import death_prose_guard, round_log
from tests.test_death_flow import _state

NAMES = {"player": "Você", "e1": "Goblin 1", "e2": "Goblin 2"}


# --- R1 ----------------------------------------------------------------------------------
def test_accept_replaces_wheel_question_in_message_and_history(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    api._rate_hits.clear()
    client = TestClient(api.app)
    gid = str(uuid.uuid4())
    st = _state(gid, hp=0, gold=0, death_pending=True)
    st["messages"] = [AIMessage(content=f"Você tomba. {round_log.WHEEL_TEXT}")]
    st["presentation_history"] = [
        {
            "id": "a",
            "turn": 8,
            "epoch": 0,
            "role": "narrator",
            "text": f"Você tomba. {round_log.WHEEL_TEXT}",
        }
    ]
    persistence.save_game_state(st)
    r = client.post("/game/death", json={"game_id": gid, "choice": "accept"})
    assert r.status_code == 200
    assert "aceitar o fim aqui?" not in r.text and "aceita o fim" in r.text
    saved = persistence.load_game_state(persistence.save_path(gid))
    assert all("aceitar o fim aqui?" not in str(m.content) for m in saved["messages"])
    assert all("aceitar o fim aqui?" not in row["text"] for row in saved["presentation_history"])


# --- R2 ----------------------------------------------------------------------------------
def _blow(target, by="player", kind="golpe", condition=None):
    return {"target_id": target, "by_actor_id": by, "kind": kind, "condition": condition}


def test_final_blow_names_two_targets_same_author():
    out = {"final_blows": [_blow("e1"), _blow("e2")]}
    assert (
        round_log.final_blow_sentence(out, NAMES)
        == "Seu golpe termina o serviço: Goblin 1 e Goblin 2 tombam."
    )


def test_final_blow_groups_by_author_and_kind_in_order():
    out = {
        "final_blows": [
            _blow("e1"),
            _blow("e2", by="", kind="dano_continuo", condition="sangramento"),
        ]
    }
    text = round_log.final_blow_sentence(out, NAMES)
    assert text.startswith("Seu golpe termina o serviço: Goblin 1 tomba. ")
    assert text.endswith("termina o serviço: Goblin 2 tomba.")


def test_final_blow_single_target_unchanged():
    out = {"final_blows": [_blow("e1")]}
    assert (
        round_log.final_blow_sentence(out, NAMES) == "Seu golpe termina o serviço: Goblin 1 tomba."
    )


# --- R3 ----------------------------------------------------------------------------------
LEVE_PERNA = [{"regiao": "perna_esquerda", "categoria": "leve"}]


def test_guard_accepts_faithful_prose():
    assert death_prose_guard.check("Um ferimento leve na perna esquerda arde.", LEVE_PERNA) is None
    assert death_prose_guard.check("Você tomba sob o último golpe.", []) is None


def test_guard_rejects_wrong_gravity_and_unrecorded_part():
    assert death_prose_guard.check("Sua perna, ferida de forma grave, cede.", LEVE_PERNA)
    assert death_prose_guard.check("Um ferimento no torso rasga você.", LEVE_PERNA)
    assert death_prose_guard.check("Um ferimento na perna direita sangra.", LEVE_PERNA)
    assert death_prose_guard.check("Um ferimento na perna sangra.", LEVE_PERNA) is None


def _death_outcome(monkeypatch, text, player):
    import agents.combat as combat
    from tests.test_spec346_outcome import _install

    _install(monkeypatch, text=text)
    events: list = []
    monkeypatch.setattr(combat, "_log_event", lambda *a, **k: events.append(a[1]))
    sink: dict = {}
    out = combat._narrate_outcome(
        "death", {"mortos": []}, player, [], {}, "ataco", "", manifest=None, source_sink=sink
    )
    return out, sink, events


def test_contradicting_death_prose_falls_back_with_event(monkeypatch):
    player = {"name": "Kael", "ferimentos": {"leve": [{"regiao": "perna_esquerda"}]}}
    out, sink, events = _death_outcome(
        monkeypatch, "Você cai de joelhos, a perna com ferimento grave.", player
    )
    assert sink["last_outcome_source"] == "fallback_attribution"
    assert "outcome_attribution_rejected" in events and "ferimento grave" not in out


def test_faithful_death_prose_passes(monkeypatch):
    player = {"name": "Kael", "ferimentos": {"leve": [{"regiao": "perna_esquerda"}]}}
    text = "Você cai de joelhos, a perna com o ferimento leve cedendo sob o peso. O mundo escurece."
    _, sink, _ = _death_outcome(monkeypatch, text, player)
    assert sink["last_outcome_source"] == "llm"


# --- R4 ----------------------------------------------------------------------------------
def _buy(text, gold=500):
    from agents import loot
    from tests.test_card_shop_loot_text import _offer
    from tests.test_card_shop_loot_text import _state as shop_state

    st = shop_state("", gold=gold)
    _cid, name = _offer(st)
    return loot.loot_node(shop_state(text.format(name=name), gold=gold)), name


@pytest.mark.parametrize(
    "phrase",
    [
        "Compro a {name} com minhas últimas moedas",
        "Compro a {name} com as moedas",
        "Compro o {name} com ouro, por favor",
    ],
)
def test_buy_with_payment_tail(monkeypatch, phrase):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")
    out, name = _buy(phrase)
    assert out["player"]["gold"] < 500 and name in out["messages"][0].content


def test_buy_payment_tail_does_not_open_prose_hole(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")
    out, _ = _buy("Compro a {name} com minhas moedas se for barato")
    assert "nada foi cobrado" in out["messages"][0].content


# --- R5 ----------------------------------------------------------------------------------
def test_pool_warning_and_strict(tmp_path, capsys):
    from scripts import import_bestiary_art as imp

    (tmp_path / "criaturas").mkdir()
    (tmp_path / "criaturas" / "bst_fantasma.png").write_bytes(b"x")
    assert imp.pool_warnings(tmp_path, {"lobo"}) == [
        "aviso: bst_fantasma: id fora do pool conhecido localmente"
    ]
    assert imp.pool_warnings(tmp_path, {"fantasma"}) == []
    assert "sem fonte local" in imp.pool_warnings(tmp_path, None)[0]
    assert imp.main([str(tmp_path), "--strict"]) == 2


# --- R6 (investigação do Achado 2) -------------------------------------------------------
def test_continue_restores_checkpoint_narration_not_player_text(tmp_path):
    """/game/new (MockLLM) + 2 turnos + morte + continue: a prosa restaurada é a narração do
    início da sessão, nunca o texto da ação do jogador."""
    from fastapi.testclient import TestClient

    from tests.fixtures import spec368_seed as seed

    with seed._legacy(str(tmp_path)):
        client = TestClient(api.app)
        gid = seed._new_game(client, "Sangromante", "Iria")
        opening = [m for m in seed._load(gid)["messages"] if m.type == "ai"][-1].content
        for text in ("Observo o lugar", "Sigo em frente"):
            assert (
                client.post("/game/action", json={"game_id": gid, "input_text": text}).status_code
                == 200
            )
        state = seed._load(gid)
        state["player"]["hp"] = 0
        state["death_pending"] = True
        persistence.save_game_state(state)
        r = client.post("/game/death", json={"game_id": gid, "choice": "continue"})
        assert r.status_code == 200, r.text
        restored = r.json()
        shown = restored.get("message") or restored.get("narrative") or r.text
        assert "Sigo em frente" not in shown and "Observo o lugar" not in shown
        assert opening[:40] in shown or opening in r.text
