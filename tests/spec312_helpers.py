"""Helpers dos testes da SPEC-312 (rumores com semente)."""

from __future__ import annotations

from services import rumors
from services import world_engine as we


def world_at(day: int, loc: str = "nova_arcadia", turn: int | None = None) -> dict:
    return {
        "current_location_id": loc,
        "current_location": loc,
        "world_clock": {"day": day, "period": "Manhã"},
        "turn_count": day if turn is None else turn,
    }


def base_state(day: int = 5, loc: str = "nova_arcadia", **extra) -> dict:
    return {
        "game_id": "g312",
        "world": world_at(day, loc),
        "event_log": [],
        "world_projection": {},
        "npcs": {},
        "factions": [],
        "faction_intel": {},
        **extra,
    }


def run_hook(sim: dict, day: int, *, loc: str = "nova_arcadia", state: dict | None = None):
    st = state or base_state(day, loc)
    ctx = we.DayContext(
        st["game_id"],
        day,
        sim,
        st.get("world_projection") or {},
        world_at(day, loc),
        [],
        we.day_rng(st["game_id"], day, "hooks_post"),
        state=st,
    )
    return rumors.day_hook(ctx)


def walk(days: int, *, game_id: str = "g312", route=None, start: int = 1):
    """Anda `days` dias chamando so o hook; `route(day) -> local`. Devolve (sim, itens)."""
    sim: dict = {}
    items: list[dict] = []
    for d in range(start, start + days):
        loc = route(d) if route else "nova_arcadia"
        st = base_state(d, loc, game_id=game_id)
        st["world_sim"] = sim
        res = run_hook(sim, d, loc=loc, state=st)
        items += res.digest
    return sim, items


def make_rumor(
    sim: dict,
    seed_id: str = "rumor_valerius_nao_come_nem_dorme",
    *,
    region: str = "nova_arcadia",
    loc: str = "na_anel_dourado",
    day: int = 5,
    turn: int | None = None,
    truth: bool = True,
    family: str | None = None,
    perceived: int = 0,
    quest_eligible: bool = True,
) -> dict:
    """Injeta uma instancia em `sim` e devolve o item de digest correspondente."""
    from services.world_director import digest_item

    fam = family or ("avistamento" if seed_id.startswith("rumor_avist_") else "lore")
    rid = rumors._sha("g312", seed_id, day)[:16]
    inst = {
        "rumor_id": rid,
        "seed_id": seed_id,
        "family": fam,
        "region_id": region,
        "location_id": loc,
        "entities": [],
        "subject": "pessoa",
        "truth": truth,
        "quest_eligible": quest_eligible,
        "born_day": day,
        "born_turn": day if turn is None else turn,
        "expires_day": day + 10,
        "perceived_day": perceived,
        "resolution": "",
    }
    sim["rumors"] = [*(sim.get("rumors") or []), inst]
    return digest_item(
        "g312",
        day,
        "rumor",
        region,
        loc,
        f"rumor.{fam}",
        {"seed_id": seed_id, "family": fam, "expires_day": day + 10},
        subject_id=rid,
    )
