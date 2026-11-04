"""SPEC-387 R21-R25: seeds determinísticas dos "não verificado" — save -> load -> /game/state e uma
rodada do motor (MockLLM) com o resultado prometido em 50/50 sementes de `random`."""

from __future__ import annotations

import pytest

import agents.combat as combat
import persistence
from services import round_log
from tests.fixtures import spec368_seed as sd
from tests.fixtures.spec387_rounds import load, play, step_card

SEEDS = range(50)
G = "bas_san_golpe"

NEW_VARIANTS = [
    (2, "frustrar"),
    (3, "eco"),
    (3, "inelegivel"),
    (3, "rachadura"),
    (5, "chefe_fase"),
    (13, "voto"),
    (13, "reacao"),
    (13, "armadura"),
    (13, "condicao_carta"),
    (14, "entrega"),
    (15, "vg_ouro"),
]


@pytest.fixture(scope="module")
def saves(tmp_path_factory):
    return str(tmp_path_factory.mktemp("spec387_saves"))


@pytest.fixture(scope="module")
def seeded(saves):
    """(item, variante) -> (game_id, estado carregado); cada save é gravado 1× por módulo."""
    cache: dict = {}

    def get(item: int, variant: str = ""):
        if (item, variant) not in cache:
            cache[(item, variant)] = load(item, variant, saves)
        return cache[(item, variant)]

    return get


def _all_seeds(saves, state, steps, check, **kw):
    with sd._legacy(saves):
        for seed in SEEDS:
            out, text, raw = play(state, steps, seed, **kw)
            check(out, text, raw, seed)


def _enemy(state):
    return state["enemies"][0]["id"]


@pytest.mark.parametrize(("item", "variant"), NEW_VARIANTS)
def test_save_load_state_shows_the_scene(saves, seeded, item, variant):
    gid, st = seeded(item, variant)
    if item in (14, 15):
        assert not (st.get("combat") or {}).get("active")
        return
    v = sd.view(gid, saves)
    assert v["combat"]["active"] and v["combat"]["pilhas"]["mao"]
    assert v["combat"]["enemies"]


def test_frustrar_shows_the_frustrated_omen(saves, seeded):
    _, st = seeded(2, "frustrar")
    steps = [step_card("arc1_des_estouro_contido", _enemy(st))]

    def check(out, text, raw, seed):
        frustrated = raw.get("pressagios_frustrados") or []
        assert frustrated and frustrated[0]["actor_id"] == _enemy(st), seed

    _all_seeds(saves, st, steps, check)


def test_eco_hits_and_the_enemy_survives(saves, seeded):
    _, st = seeded(3, "eco")
    steps = [step_card(G, _enemy(st)), step_card("san1_exp_segundo_ato", _enemy(st))]

    def check(out, text, raw, seed):
        line = next(ln for ln in text.splitlines() if "Segundo Ato" in ln)
        assert "Acerta" in line or "Acerto" in line, (seed, line)
        assert not out["enemies"][0].get("dead"), seed

    _all_seeds(saves, st, steps, check)


def test_rachadura_applies_the_condition(saves, seeded):
    _, st = seeded(3, "rachadura")
    steps = [
        step_card("cor1_ino_junta_emperrada", _enemy(st)),
        step_card("bas_cor_golpe", _enemy(st)),
    ]

    def check(out, text, raw, seed):
        assert "Rachadura" in text and "Acerta" in text, seed

    _all_seeds(saves, st, steps, check)


def test_inelegivel_is_refused_without_cost(saves, seeded):
    _, st = seeded(3, "inelegivel")
    steps = [step_card("san1_exp_segundo_ato", _enemy(st))]

    def check(out, text, raw, seed):
        assert "não está no seu baralho." in text, seed
        assert "san1_exp_segundo_ato" in out["combat"]["pilhas"]["mao"], seed  # mão intacta
        assert out["combat"]["pilhas"]["folego"] == st["combat"]["pilhas"]["folego"], seed

    _all_seeds(saves, st, steps, check)


def test_escort_is_an_actor_and_does_not_fail_in_round_one(saves, seeded):
    _, st = seeded(4)
    assert st["party"][0]["id"] == "escoltado"
    assert (st["combat"]["scene"]["objetivo"] or {}) == {"tipo": "proteger", "alvo": "escoltado"}

    def check(out, text, raw, seed):
        assert not raw.get("objetivo"), seed
        assert out["combat"]["active"], seed

    _all_seeds(saves, st, [], check)


def test_escort_downed_fails_with_the_cause_and_the_hero_standing(saves, seeded, monkeypatch):
    _, st = seeded(4)
    st = {**st, "party": [{**st["party"][0], "dead": True, "status": "morto", "vitalidade": 0}]}
    monkeypatch.setattr(combat, "_fast_text", lambda *a, **k: "")  # cai no texto determinístico
    with sd._legacy(saves):
        out, text, raw = play(st, [], 3)
    assert raw["objetivo"]["resultado"] == "falhou"
    assert "O objetivo se perdeu: Escoltado não resistiu." in text
    assert "perde os sentidos" not in text and "Você tomba" not in text and "apaga" not in text


def test_boss_phase_line_shows_up(saves, seeded):
    _, st = seeded(5, "chefe_fase")
    steps = [step_card("bas_dev_golpe", _enemy(st))]

    def check(out, text, raw, seed):
        assert raw.get("fases"), seed

    _all_seeds(saves, st, steps, check)


def test_voto_redirects_or_resists(saves, seeded):
    _, st = seeded(13, "voto")
    assert st["combat"]["pressagios_publicos"][0]["alvo_id"] == "ketil"
    steps = [step_card("bas_dev_voto", _enemy(st))]

    def check(out, text, raw, seed):
        logs = " ".join(raw["logs"])
        assert "muda de alvo" in logs or "resiste" in logs, (seed, logs)

    _all_seeds(saves, st, steps, check)


def test_reacao_kills_and_the_summary_cites_the_author(saves, seeded):
    _, st = seeded(13, "reacao")
    guard = {"kind": "maneuver", "maneuver": "guardar", "target_id": None}

    def check(out, text, raw, seed):
        blows = [b for b in raw.get("final_blows") or [] if b.get("kind") == "reacao"]
        assert blows and blows[0]["by_actor_id"] == "player", seed
        sentence = round_log.final_blow_sentence(raw, {"player": "Você", _enemy(st): "Goblin"})
        assert "reação" in sentence and "Goblin" in sentence, (seed, sentence)
        # SPEC-387: derrubado pela Reação, o atacante não resolve o próprio ataque na rodada
        assert not any(x.get("actor_id") == _enemy(st) for x in raw.get("attacks") or []), seed
        assert not any("Usa Investida Cega" in ln for ln in raw["logs"]), seed
        # Sol P1-2: presságio FRUSTRADO (não cumprido), sem revelar a Carta que não foi jogada
        assert not any(
            p["actor_id"] == _enemy(st) for p in raw.get("pressagios_cumpridos") or []
        ), seed
        assert any(p["actor_id"] == _enemy(st) for p in raw.get("pressagios_frustrados") or []), (
            seed
        )
        assert not any("cumpre o que o presságio" in ln for ln in raw["logs"]), seed
        board = out["combat"]["last_round_board"]
        assert not [e for e in board if e.get("tipo") == "pressagio"], seed
        assert "Presságio frustrado: Goblin" in text and "Investida" not in text, (seed, text)

    _all_seeds(saves, st, [guard], check, reaction="dev_encaixe")


def test_armadura_comprometida_has_a_readable_name(saves, seeded):
    _, st = seeded(13, "armadura")
    assert st["enemies"][0]["id"].startswith("enemy_soldado_legiao_ferro")
    step = step_card("cor_ino_fadiga", _enemy(st))
    step["params"]["ruptura"] = True

    def check(out, text, raw, seed):
        assert "ganha a condição Armadura Comprometida." in text, (seed, text)
        assert "armadura_comprometida" not in text.lower(), seed

    _all_seeds(saves, st, [step], check)


def test_condicao_carta_is_applied_to_the_enemy(saves, seeded):
    _, st = seeded(13, "condicao_carta")
    steps = [step_card("neu1_er_lanca_de_gancho", _enemy(st))]

    def check(out, text, raw, seed):
        assert "ganha a condição Enredado." in text, seed

    _all_seeds(saves, st, steps, check)


def test_entrega_completes_the_quest_and_grants_the_card(seeded, monkeypatch):
    from services.event_processor import process_pending_events

    monkeypatch.setenv("RPG_CARD_REWARDS", "on")
    _, st = seeded(14, "entrega")
    assert st["world"]["current_location_id"] == "brekmar" and "Contratante" in st["npcs"]
    quest = next(q for q in st["quests"] if q["id"] == "q368")
    ev = {
        "type": "quest_completed",
        "actor_id": "player",
        "target_id": quest["id"],
        "payload": {"quest_id": quest["id"]},
        "source": "storyteller",
    }
    state = {**st, "pending_world_events": [ev]}
    state["player"] = {**st["player"], "level": 6}
    state["world"] = {**st["world"], "turn_count": 5}  # a quest do save nasce no turno 1
    out = process_pending_events(state)
    assert [c for c in out["player"]["known_cards"] if c.startswith("neu1_")]
    assert next(q for q in out["quests"] if q["id"] == "q368")["reward_card"]


def test_vg_ouro_leaves_a_final_balance_of_30(seeded):
    from services import card_shop

    _, st = seeded(15, "vg_ouro")
    mid, ids = card_shop.shelf(st)
    price = min(card_shop.card_price(st, c, card_shop.economy.MERCHANTS[mid]) for c in ids)
    assert st["player"]["gold"] - price == 30


def test_espolio_has_forja_and_esquecer_visible(saves):
    gid = sd.seed_save(6, variant="espolio", saves_dir=saves)
    with sd._legacy(saves):
        st = persistence.load_game_state(persistence.save_path(gid))
    assert st["player"]["forja_esquecer"] == 1 and st["player"].get("deck")


def test_reaction_kill_fires_ao_pressagio_frustrado_once(saves, seeded):
    """Sol R2-P2-1: matar o atacante com a Reação dispara o gatilho como `_frustrate` ("Ferro Antes do Ferro")."""
    _, st = seeded(13, "reacao")
    st = {**st, "player": {**st["player"], "vitalidade": 5}}
    st["combat"] = {**st["combat"], "scene": dict(st["combat"]["scene"])}
    st["combat"]["scene"]["gatilhos_armados"] = [
        {
            "owner_id": "player",
            "card_id": "dev1_zel_ferro_antes_do_ferro",
            "efeito": {
                "kind": "cura",
                "valor": 3,
                "alvo": "eu",
                "quando": "ao_pressagio_frustrado",
            },
        }
    ]
    guard = {"kind": "maneuver", "maneuver": "guardar", "target_id": None}
    with sd._legacy(saves):
        for seed in range(10):
            out, _text, raw = play(st, [guard], seed, reaction="dev_encaixe")
            fired = [
                g for g in raw.get("gatilhos") or [] if g["gatilho"] == "ao_pressagio_frustrado"
            ]
            assert len(fired) == 1, (seed, raw.get("gatilhos"))
            assert out["player"]["vitalidade"] == 8, seed


def test_escort_fail_50_seeds(saves, seeded, monkeypatch):
    """SPEC-389 R16: `4 falha` — o inimigo mira o escoltado (Vit 1) e o objetivo FALHA em toda semente."""
    monkeypatch.setattr(combat, "_fast_text", lambda *a, **k: "")  # texto determinístico
    _, st = seeded(4, "falha")
    assert st["party"][0]["id"] == "escoltado"

    def check(out, text, raw, seed):
        assert (raw.get("objetivo") or {}).get("resultado") == "falhou", (seed, raw.get("objetivo"))
        assert "O objetivo se perdeu: Escoltado não resistiu." in text, (seed, text)
        for bad in ("perde os sentidos", "apaga", "Você tomba"):
            assert bad not in text, (seed, text)
        assert out["player"]["vitalidade"] > 0, seed

    _all_seeds(saves, st, [], check)


def test_hostile_fallback_seed(seeded, monkeypatch):
    """SPEC-389 R17: com CLASSIFY esgotado, "Ataco o goblin" abre COMBAT por `hostility_fallback`
    sem depender do narrador ao vivo (a regra da SPEC-355 R5 não muda)."""
    from langchain_core.messages import HumanMessage

    import agents.router as router
    from llm_setup import FallbackLLM

    monkeypatch.setattr(router, "get_llm", lambda **k: FallbackLLM("esgotado"))
    _, st = seeded(12, "hostil")
    assert not (st.get("combat") or {}).get("active")
    state = {**st, "messages": [*st["messages"], HumanMessage(content="Ataco o goblin")]}
    payload = router.dm_router_node(state)
    assert payload["next"] == "combat_agent"
    assert router.last_decision()["route_source"] == "hostility_fallback"


@pytest.mark.parametrize(("item", "variant"), sorted(sd._BODIES))
def test_smoke_bodies_parse_and_play(saves, item, variant):
    """SPEC-389 R18: cada corpo do roteiro passa pelo `ActionRequest` e o `TestClient` (MockLLM) joga."""
    from fastapi.testclient import TestClient

    import api

    gid = sd.seed_save(item, variant=variant, saves_dir=saves)
    with sd._legacy(saves):
        body = sd.smoke_body(item, variant, gid)
        api.ActionRequest(**body)
        if (item, variant) == (14, "entrega"):  # roteamento real é do CLASSIFY: roda o nó direto
            _assert_entrega_closes(gid, body["input_text"])
        else:
            r = TestClient(api.app).post("/game/action", json=body)
            assert r.status_code == 200, (item, variant, r.text[:300])
            state = TestClient(api.app).get("/game/state", params={"game_id": gid}).json()
            _assert_variant_result(item, variant, r.text, state, gid)


def _assert_variant_result(item: int, variant: str, text: str, state: dict, gid: str) -> None:
    """SPEC-389 R18 (Sol P2-5): o corpo produz o resultado prometido da variante."""
    key = (item, variant)
    combat = state.get("combat") or {}
    if key == (2, "frustrar"):
        assert any(e.get("tipo") == "pressagio_frustrado" for e in combat["registro_rodada"])
    elif key == (3, "eco"):
        assert "Segundo Ato" in text
    elif key == (4, "falha"):
        assert (
            not combat.get("active") and "perde os sentidos" not in text
        )  # objetivo falho encerra
    elif key == (12, "hostil"):
        assert combat.get("active")
    elif key == (13, "voto"):
        assert ("muda de alvo" in text or "resiste" in text) and "próxima intenção" not in text
    elif key == (13, "condicao_carta"):
        assert "ganha a condição Enredado" in text
    elif key == (13, "armadura"):
        conds = [c for e in combat["enemies"] for c in e["conditions"]]
        assert any(c["name"] == c["label"] == "Armadura Comprometida" for c in conds), conds
    elif key == (13, "reacao"):
        assert "reage com Encaixe do Golpe" in text


def _assert_entrega_closes(gid: str, text: str) -> None:
    """O MockLLM roteia "Entrego…" para STORY (sem palavra de conversa); o caminho real é o roteador
    (CLASSIFY) → `npc_actor`. Aqui o nó roda direto com a frase do corpo: fecha a quest e paga."""
    from langchain_core.messages import HumanMessage

    from agents.npc import npc_actor_node
    from services.event_processor import process_pending_events

    st = sd._load(gid)
    st["messages"] = [*st.get("messages", []), HumanMessage(content=text)]
    st["active_npc_name"] = "Contratante"
    out = npc_actor_node(st)
    done = process_pending_events({**st, **out})
    quest = next(q for q in done["quests"] if q["id"] == "q368")
    assert quest["status"] == "completed", quest
    from services.quest_log import QUEST_REWARD_GOLD

    assert done["player"]["gold"] == st["player"]["gold"] + QUEST_REWARD_GOLD


def test_printed_promote_passes_reviewer_check(monkeypatch):
    """SPEC-389 R19: a linha impressa do `promote` não é recusada por falta de revisor (D-389-6)."""
    import argparse
    import importlib.util
    import shlex
    import sys
    from pathlib import Path

    from scripts.cards import draft

    root = Path(draft.__file__).resolve().parents[2]
    cmd = draft.next_commands(str(root / "data/cards/_rascunhos/onda389_x_y.json"), 389)[2]
    argv = shlex.split(cmd)
    script = next(a for a in argv if a.endswith("promote.py"))
    seen: dict = {}
    orig = argparse.ArgumentParser.parse_args

    class _Stop(Exception):
        pass

    def spy(self, a=None, ns=None):
        seen["ns"] = orig(self, a, ns)
        raise _Stop

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", spy)
    spec = importlib.util.spec_from_file_location("cards_promote_389", root / script)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    with pytest.raises(_Stop):
        mod.main(argv[argv.index(script) + 1 :])
    ns = seen["ns"]
    assert (
        ns.voz_pendente and not ns.revisor_voz
    )  # mesma regra de `promote()`: pendente XOR revisor
    assert ns.voz_pendente or mod.revisor_valido(ns.revisor_voz)


def test_entrega_body_through_the_graph_keeps_the_arc(saves):
    """SPEC-389 R8 (Sol R2): o POST da `14 entrega` pelo grafo (MockLLM) não replaneja por região.

    Achado: o MockLLM roteia "Entrego…" para STORY (sem palavra de conversa), então a quest só fecha
    quando o storyteller do mock propõe (aleatório, ~metade das execuções). O fechamento
    determinístico pela rota NPC é provado por `_assert_entrega_closes` (nó direto); o roteamento real
    é do CLASSIFY (smoke §6). Aqui só se prova o que o grafo garante: 200, jogo em Brekmar e o arco
    preservado (`campaign_plan.location` e `current_step`)."""
    from fastapi.testclient import TestClient

    import api

    gid = sd.seed_save(14, variant="entrega", saves_dir=saves)  # seed nova: o POST muda o save
    with sd._legacy(saves):
        before = sd._load(gid)["campaign_plan"]
        r = TestClient(api.app).post("/game/action", json=sd.smoke_body(14, "entrega", gid))
        assert r.status_code == 200, r.text[:300]
        after = sd._load(gid)
    assert after["campaign_plan"]["location"] == "Brekmar"
    assert int(after["campaign_plan"].get("current_step", 0)) >= int(before.get("current_step", 0))
    quest = next(q for q in after["quests"] if q["id"] == "q368")
    assert quest["status"] in {"active", "completed"}
