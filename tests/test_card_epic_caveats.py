"""SPEC-393: arestas do smoke das ressalvas do épico de Cartas (R1-R6)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import api
import persistence
from services import death_prose_guard, round_log
from services.death_ending import ACCEPT_TEXT
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
    assert saved["messages"][-1].content.endswith(ACCEPT_TEXT)
    assert saved["presentation_history"][-1]["text"].endswith(ACCEPT_TEXT)
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


def test_dot_blows_from_different_authors_share_one_sentence():
    out = {
        "final_blows": [
            _blow("e1", by="x", kind="dano_continuo", condition="sangramento"),
            _blow("e2", by="y", kind="dano_continuo", condition="sangramento"),
        ]
    }
    text = round_log.final_blow_sentence(out, NAMES)
    assert text.count("termina o serviço") == 1 and "Goblin 1 e Goblin 2 tombam" in text


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
    assert death_prose_guard.check("Um ferimento na sua perna direita sangra.", LEVE_PERNA)
    assert death_prose_guard.check("Um ferimento na sua perna sangra.", LEVE_PERNA) is None


def test_guard_own_body_part_subject_and_far_negation_are_checked():
    assert death_prose_guard.check("A perna, ferida de forma grave, cede sob você.", LEVE_PERNA)
    assert death_prose_guard.check("A cabeça, ferida, latejando, cede.", LEVE_PERNA)
    assert death_prose_guard.check("A ferida grave na perna esquerda sangra sem parar.", LEVE_PERNA)
    assert death_prose_guard.check("Sua perna, ferida gravemente, cede.", LEVE_PERNA)
    assert death_prose_guard.check("Sua perna, ferida criticamente, cede.", LEVE_PERNA)
    assert death_prose_guard.check("Sua perna, ferida levemente, cede.", LEVE_PERNA) is None
    assert death_prose_guard.check("A perna ferida gravemente cede.", LEVE_PERNA)
    assert death_prose_guard.check("O goblin ferido na cabeça ri de você.", LEVE_PERNA) is None


@pytest.mark.parametrize(
    "prose",
    [
        "Sem ferimentos graves na perna, você tomba pelo cansaço.",
        "Um leve tremor percorre sua perna.",
        "O lobo, ferido na perna, recua.",
        "O ferimento no braço do Goblin sangra.",
    ],
)
def test_guard_false_positives_pass(prose):
    crit_torso = [{"regiao": "torso", "categoria": "critico"}]
    assert death_prose_guard.check(prose, crit_torso) is None


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
def test_pool_warning_lines(tmp_path):
    from scripts import import_bestiary_art as imp

    (tmp_path / "criaturas").mkdir()
    (tmp_path / "criaturas" / "bst_fantasma.png").write_bytes(b"x")
    assert imp.pool_warnings(tmp_path, {"lobo"}) == [
        "aviso: bst_fantasma: id fora do pool conhecido localmente"
    ]
    assert imp.pool_warnings(tmp_path, {"fantasma"}) == []
    assert "sem fonte local" in imp.pool_warnings(tmp_path, None)[0]


def test_strict_aborts_before_writing_and_plain_run_succeeds(tmp_path, monkeypatch, capsys):
    import functools
    import shutil
    from pathlib import Path

    from scripts import import_bestiary_art as imp
    from tests.test_import_bestiary_art import _png

    root = Path(imp.ROOT)
    catalog = tmp_path / "visual_assets.json"
    shutil.copy(root / "data" / "visual_assets.json", catalog)
    out_dir = tmp_path / "out"
    folder = tmp_path / "in"
    (folder / "criaturas").mkdir(parents=True)
    (folder / "criaturas" / "bst_fantasma-zz.png").write_bytes(_png(3, 800))
    monkeypatch.setattr(imp, "known_pool_ids", lambda: {"lobo"})
    monkeypatch.setattr(
        imp,
        "import_folder",
        functools.partial(imp.import_folder, catalog_path=catalog, out_dir=out_dir),
    )
    before = catalog.read_bytes()

    assert imp.main([str(folder), "--strict"]) == 2
    assert catalog.read_bytes() == before and not out_dir.exists()
    assert "fora do pool" in capsys.readouterr().out

    assert imp.main([str(folder)]) == 0
    assert catalog.read_bytes() != before and out_dir.exists()


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
