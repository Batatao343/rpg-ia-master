"""Casos do golden de nos da SPEC-382 (storyteller, combate, stream, campanha)."""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import HumanMessage, SystemMessage

from tests.spec382_node_golden import Recorder


# --------------------------------------------------------------------------- storyteller
def story_state(text: str = "Observo a rua.", **world) -> dict:
    st = {
        "game_id": "g382",
        "messages": [HumanMessage(content=text)],
        "player": {
            "name": "Ari",
            "class_name": "Devoto do Abismo",
            "level": 1,
            "xp": 0,
            "gold": 10,
            "inventory": [],
            "vitalidade": 5,
            "max_vitalidade": 8,
        },
        "world": {
            "current_location_id": "nova_arcadia",
            "current_location": "Nova Arcádia",
            "turn_count": 4,
            "danger_level": 1,
            "world_clock": {"day": 1, "period": "Manhã"},
            "visited": ["nova_arcadia"],
        },
        "npcs": {},
        "factions": [],
        "faction_intel": {},
        "quests": [],
        "campaign_plan": {},
        "event_log": [],
        "world_projection": {},
        "narrative_summary": "",
        "archivist_last_run": 0,
    }
    st["world"].update(world)
    return st


class _Fake:
    """LLM falso: `with_structured_output(...).invoke` devolve `update`; grava o prompt."""

    def __init__(self, update, prompts: list) -> None:
        self.update, self.prompts = update, prompts

    def with_structured_output(self, _schema):
        return self

    def invoke(self, messages):
        self.prompts.append([[type(m).__name__, str(m.content)] for m in messages])
        if isinstance(self.update, Exception):
            raise self.update
        return self.update


def _story_run(rec: Recorder, state: dict, update, *, patches=(), seed: int = 1):
    from agents import storyteller as st

    prompts: list = []
    fake = _Fake(update, prompts)
    rec.mp.setattr(st, "get_llm", lambda *a, **k: fake)
    for target, name, value in patches:
        rec.mp.setattr(target, name, value)
    out = rec.call(st.storyteller_node, state, seed=seed)
    rec.trace.append(["prompts", prompts])
    return out


def _upd(**kw):
    from agents.storyteller import StoryUpdate

    return StoryUpdate(narrative=kw.pop("narrative", "A cena segue calma e tensa."), **kw)


def _enc(**kw):
    base = {"reason": "controlled", "flavor": "Bandidos bloqueiam a estrada.", "hint": "Bandido"}
    base.update(kw)
    return lambda *a, **k: dict(base)


def _roll(kind: str):
    import world_utils

    return (world_utils, "roll_encounter_type", lambda danger: kind)


def _patch_enc(enc):
    from agents import storyteller as st

    return (st, "check_encounter", enc)


def s_free(rec):
    _story_run(rec, story_state(), _upd(), patches=[_patch_enc(lambda *a, **k: None)])


def s_free_items(rec):
    st = story_state("Pego a corda do baú.")
    _story_run(
        rec,
        st,
        _upd(items_gained=["Corda"], introduced_npcs=["Mira"], beat_completed=True),
        patches=[_patch_enc(lambda *a, **k: None)],
    )


def s_travel(rec):
    st = story_state("Viajo para Brekmar.")
    _story_run(rec, st, _upd(), patches=[_patch_enc(lambda *a, **k: None)])


def s_travel_refused(rec):
    _story_run(rec, story_state("Viajo para Zhur Inexistente."), _upd())


def s_travel_combat(rec):
    st = story_state("Viajo para Brekmar.")
    _story_run(rec, st, _upd(), patches=[_patch_enc(_enc())])


def s_travel_trap(rec):
    st = story_state("Viajo para Brekmar.")
    _story_run(rec, st, _upd(), patches=[_patch_enc(_enc(reason="x")), _roll("trap")])


def s_travel_track(rec):
    st = story_state("Viajo para Brekmar.")
    _story_run(rec, st, _upd(), patches=[_patch_enc(_enc(reason="x")), _roll("track")])


def s_travel_social(rec):
    st = story_state("Viajo para Brekmar.")
    _story_run(
        rec,
        st,
        _upd(introduced_npcs=["Porta-voz"]),
        patches=[_patch_enc(_enc(reason="x")), _roll("social")],
    )


def s_rest(rec):
    _story_run(
        rec,
        story_state("Descanso até o amanhecer."),
        _upd(),
        patches=[_patch_enc(lambda *a, **k: None)],
    )


def s_rest_ambush(rec):
    st = story_state("Descanso até o amanhecer.", danger_level=4)
    st["world"]["current_location_id"] = "pantano_melancolia"
    st["world"]["current_location"] = "Pântano da Melancolia"
    _story_run(rec, st, _upd(), patches=[_patch_enc(_enc())])


def s_rest_blocked(rec):
    st = story_state("Descanso até o amanhecer.", weather_state="miasma")
    st["world"]["current_location_id"] = "pantano_melancolia"
    st["world"]["current_location"] = "Pântano da Melancolia"
    _story_run(rec, st, _upd(), patches=[_patch_enc(lambda *a, **k: None)])


def s_fallback_llm(rec):
    from llm_setup import FallbackLLM

    class _FB(FallbackLLM):
        def __init__(self) -> None:
            super().__init__("falha")

    from agents import storyteller as st

    rec.mp.setattr(st, "get_llm", lambda *a, **k: _FB())
    rec.mp.setattr(st, "check_encounter", lambda *a, **k: None)
    rec.call(st.storyteller_node, story_state("Viajo para Brekmar."))


def s_exception(rec):
    _story_run(
        rec,
        story_state("Viajo para Brekmar."),
        RuntimeError("falha no narrador"),
        patches=[_patch_enc(lambda *a, **k: None)],
    )


def s_quarantine(rec):
    from agents.storyteller import ProposedWorldEvent

    ev = ProposedWorldEvent(
        type="quest_completed", target_id="inexistente", payload={"quest_id": "inexistente"}
    )
    _story_run(
        rec, story_state(), _upd(proposed_events=[ev]), patches=[_patch_enc(lambda *a, **k: None)]
    )


def s_empty_narrative(rec):
    _story_run(
        rec,
        story_state("Viajo para Brekmar."),
        _upd(narrative="  "),
        patches=[_patch_enc(lambda *a, **k: None)],
    )


def s_membership(rec):
    import gamedata

    st = story_state("Viajo para Brekmar.")
    st["factions"] = gamedata.seed_factions()
    st["faction_membership"] = {"faction_id": gamedata.seed_factions()[0]["id"], "rank": 1}
    _story_run(rec, st, _upd(), patches=[_patch_enc(lambda *a, **k: None)])


def s_recovery(rec):
    st = story_state("Ataco!")
    st["player"].update(vitalidade=0, conscious=False)
    _story_run(rec, st, _upd(), patches=[_patch_enc(lambda *a, **k: None)])


STORY_CASES: dict[str, Callable] = {
    "story_free": s_free,
    "story_free_items": s_free_items,
    "story_travel": s_travel,
    "story_travel_refused": s_travel_refused,
    "story_travel_combat": s_travel_combat,
    "story_travel_trap": s_travel_trap,
    "story_travel_track": s_travel_track,
    "story_travel_social": s_travel_social,
    "story_rest": s_rest,
    "story_rest_ambush": s_rest_ambush,
    "story_rest_blocked": s_rest_blocked,
    "story_fallback_llm": s_fallback_llm,
    "story_exception": s_exception,
    "story_quarantine": s_quarantine,
    "story_empty_narrative": s_empty_narrative,
    "story_membership": s_membership,
    "story_recovery": s_recovery,
}


# --------------------------------------------------------------------------- combate
def _combat_mod():
    from agents import combat as cbt

    return cbt


def _seq(
    rec: Recorder, state: dict, steps: list, *, narrate="fake", deck: str = "off", seed0: int = 10
) -> list:
    """Roda `combat_node` real em sequencia, mesclando cada resultado no estado seguinte."""
    cbt = _combat_mod()
    rec.mp.setenv("RPG_CARD_DECK", deck)
    if narrate == "fake":
        rec.mp.setattr(cbt, "_narrate", lambda *a, **k: "Fim da rodada.")
    outs = []
    for i, (intent, decl) in enumerate(steps):
        if intent is not None:
            state["messages"] = (
                [SystemMessage(content=intent)]
                if intent.startswith("COMBAT START")
                else [HumanMessage(content=intent)]
            )
        state["combat_declaration"] = decl
        out = rec.call(cbt.combat_node, state, seed=seed0 + i)
        outs.append(out)
        merged = {k: v for k, v in (out or {}).items() if k != "next"}
        state.update(merged)
    return outs


def _decl(kind: str, **params):
    d = {"actor_id": "player", "acao": {"kind": kind}}
    d["acao"].update(params)
    return d


def _cstate(enemies=None, intent="ataco o inimigo", **kw):
    from tests.spec325_helpers import lacaio, make_state

    return make_state(enemies or [lacaio()], intent, **kw)


def c_basic(deck):
    def run(rec):
        from tests.spec325_helpers import lacaio

        foes = [lacaio("e1", "Goblin", hp=3, max_hp=3, vitalidade=3, max_vitalidade=3)]
        st = _cstate(foes)
        steps = [("ataco o inimigo", None), ("ataco o inimigo", None), ("ataco com tudo", None)]
        if deck == "on":
            steps = [("COMBAT START. Goblins!", None)] + steps
            st["combat"] = {}
            st["combat_declaration"] = None
        _seq(rec, st, steps, deck=deck)

    return run


def c_unconscious(deck):
    def run(rec):
        st = _cstate()
        st["player"]["conscious"] = False
        st["combat"] = {"active": False}
        _seq(rec, st, [("ataco", None)], deck=deck)

    return run


def c_freetext(deck):
    def run(rec):
        st = _cstate()
        st["combat"] = {}
        _seq(rec, st, [("COMBAT START. Lacaios.", None), ("ataco o inimigo", None)], deck="on")

    return run


def c_start_spawn(deck):
    def run(rec):
        st = _cstate()
        st["enemies"] = []
        st["combat"] = {}
        st["combat_target"] = "Goblin"
        _seq(rec, st, [("COMBAT START. Goblins na estrada.", None), ("ataco", None)], deck=deck)

    return run


def c_no_active(deck):
    def run(rec):
        from tests.spec325_helpers import lacaio

        st = _cstate([lacaio("e1", "Goblin", status="morto", dead=True)])
        _seq(rec, st, [("olho em volta", None)], deck=deck)

    return run


def c_flee(deck):
    def run(rec):
        from tests.spec325_chase_helpers import first_state

        st = first_state()
        if deck == "on":
            st["combat"] = {}
        _seq(
            rec, st, [("fujo", None), ("fujo", None), ("fujo para longe", _decl("flee"))], deck=deck
        )

    return run


def c_flee_dest(deck):
    def run(rec):
        from tests.spec325_chase_helpers import first_state

        st = first_state()
        st["world"] = {
            "turn_count": 3,
            "current_location_id": "nova_arcadia",
            "current_location": "Nova Arcádia",
            "world_clock": {"day": 1, "period": "Manhã"},
        }
        st["combat_flee_attempt"] = True
        st["combat_flee_destination"] = "brekmar"
        _seq(rec, st, [("fujo", None), ("fujo", None)], deck=deck)

    return run


def c_flee_rooted(deck):
    def run(rec):
        from tests.spec325_chase_helpers import first_state

        st = first_state()
        st["player"]["active_conditions"] = [{"name": "Raízes", "control": "root", "duration": 3}]
        _seq(rec, st, [("fujo", None), ("fujo", None)], deck=deck)

    return run


def c_death(deck):
    def run(rec):
        from tests.spec325_helpers import lacaio

        brute = lacaio(
            "e1",
            "Ogro",
            hp=60,
            max_hp=60,
            vitalidade=60,
            max_vitalidade=60,
            attacks=[{"name": "Clava", "bonus": 30, "damage": "6d6"}],
            attack_mod=30,
            virtudes={"forca": 9, "agilidade": 9, "corpo": 9, "mente": 0, "carisma": 0},
        )
        st = _cstate([brute], player_over={"vitalidade": 0})
        _seq(rec, st, [("ataco", None)] * 4, deck=deck, seed0=0)

    return run


def c_victory_quest(deck):
    def run(rec):
        from tests.spec325_helpers import lacaio

        foes = [lacaio("e1", "Goblin", bestiary_id="goblin", hp=1, max_hp=1)]
        st = _cstate(foes)
        st["quests"] = [
            {
                "id": "q_cacar",
                "title": "Caçar goblin",
                "status": "active",
                "world_kind": "cacar_criatura",
                "lore_anchor": {"type": "enemy", "id": "goblin"},
            }
        ]
        st["world"].update(current_location_id="nova_arcadia", current_location="Nova Arcádia")
        _seq(rec, st, [("ataco", None), ("ataco", None)], deck=deck)

    return run


def c_simulation(deck):
    def run(rec):
        st = _cstate()
        st["combat_simulation"] = {"enabled": True}
        _seq(rec, st, [("ataco", None), ("ataco", None)], deck=deck)

    return run


def c_party(deck):
    def run(rec):
        from tests.spec325_chase_helpers import first_state

        st = first_state(party=True)
        st["combat_declaration"] = None
        _seq(rec, st, [("ataco o inimigo", None), ("ataco o inimigo", None)], deck=deck)

    return run


def c_real_narrate(deck):
    def run(rec):
        from tests.spec325_helpers import lacaio

        st = _cstate([lacaio("e1", "Goblin", hp=2, max_hp=2)])
        _seq(
            rec,
            st,
            [("ataco o inimigo", None), ("ataco o inimigo", None)],
            narrate="real",
            deck=deck,
        )

    return run


_COMBAT_BASE = {
    "basic": c_basic,
    "unconscious": c_unconscious,
    "start_spawn": c_start_spawn,
    "no_active": c_no_active,
    "flee": c_flee,
    "flee_dest": c_flee_dest,
    "flee_rooted": c_flee_rooted,
    "death": c_death,
    "victory_quest": c_victory_quest,
    "simulation": c_simulation,
    "party": c_party,
    "real_narrate": c_real_narrate,
}
COMBAT_CASES: dict[str, Callable] = {
    f"combat_{name}_{deck}": maker(deck)
    for name, maker in _COMBAT_BASE.items()
    for deck in ("off", "on")
}
COMBAT_CASES["combat_freetext_on"] = c_freetext("on")


# --------------------------------------------------------------------------- stream
def _with_sink(rec: Recorder, fn):
    from services import narrative_sink as ns

    chunks: list = []
    token = ns.bind(lambda kind, text: chunks.append([kind, text]))
    try:
        fn()
    finally:
        ns.unbind(token)
    rec.trace.append(["stream", chunks])


def stream_story(rec):
    from agents import storyteller as st

    rec.mp.setattr(st, "check_encounter", lambda *a, **k: None)
    state = story_state("Viajo para Brekmar.")
    _with_sink(rec, lambda: rec.call(st.storyteller_node, state, seed=3))


def stream_story_rumor_guard(rec):
    from agents import storyteller as st

    rec.mp.setattr(st, "check_encounter", lambda *a, **k: None)
    state = story_state("Observo a rua.")
    _with_sink(rec, lambda: rec.call(st.storyteller_node, state, seed=4))


def stream_combat(rec):
    from tests.spec325_helpers import lacaio

    st = _cstate([lacaio("e1", "Goblin", hp=2, max_hp=2)])
    _with_sink(
        rec, lambda: _seq(rec, st, [("ataco o inimigo", None), ("ataco", None)], narrate="real")
    )


STREAM_CASES: dict[str, Callable] = {
    "stream_story": stream_story,
    "stream_story_plain": stream_story_rumor_guard,
    "stream_combat": stream_combat,
}


# --------------------------------------------------------------------------- campanha
def _fingerprint(result) -> dict:
    turns = [
        [
            r.action,
            r.route,
            r.location_id,
            int(r.player_vitality),
            int(r.gold),
            int(r.player_level),
            bool(r.combat_started),
            bool(r.combat_ended),
            len(r.llm_events),
        ]
        for r in result.history
    ]
    st = result.final_state or {}
    return {
        "turns": turns,
        "final_state": st,
        "last_mech_log": (st.get("combat") or {}).get("last_mech_log"),
        "errors": len(result.errors),
    }


def _campaign(profile: str, deck: str):
    def run(rec):
        from playtest.runner import run_campaign

        rec.mp.setenv("RPG_CARD_DECK", deck)
        result = run_campaign(profile, turns=30, seed=0, invariants=False)
        rec.results.append(_fingerprint(result))

    return run


CAMPAIGN_CASES: dict[str, Callable] = {
    f"campaign_{profile}_{deck}": _campaign(profile, deck)
    for profile in ("explorador", "combate", "diplomatico", "secret_rusher")
    for deck in ("off", "on")
}
