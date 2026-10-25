"""Helpers dos testes da SPEC-313 (quests ancoradas em lore)."""

from __future__ import annotations

from tests.spec305_helpers import base_state

NPC_KEY = "Rolf"
NPC_REF = "npc_rolf"


def setup_env(monkeypatch, lore: str = "on", npc_world: str = "on") -> None:
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_WORLD_QUESTS", "on")
    monkeypatch.setenv("RPG_LORE_QUESTS", lore)
    monkeypatch.setenv("RPG_NPC_WORLD", npc_world)
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def npc_state(
    loc: str = "skallgard",
    role: str = "caçador",
    archetype: str = "sedentario",
    day: int = 17,
    **extra,
) -> dict:
    """Jogador em `loc` conversando com Rolf (em cena), simulado pela SPEC-304."""
    st = base_state(day=day, loc=loc, **extra)
    st["npcs"] = {
        NPC_KEY: {
            "id": NPC_REF,
            "name": "Rolf",
            "role": role,
            "in_scene": True,
            "known_by_player": True,
            "home_location_id": loc,
            "relationship": 5,
        }
    }
    st["npc_sim"] = {
        "version": 1,
        "enabled_from_day": 1,
        "roster": [NPC_REF],
        "roster_fingerprint": "",
        "npcs": {
            NPC_REF: {
                "archetype": archetype,
                "home": loc,
                "pos": {"location_id": loc, "since_day": 1, "arrive_day": None},
                "status": "",
                "frozen": False,
            }
        },
        "perils": [],
        "tick_log": [],
    }
    st["player"] = {"level": 1, "gold": 10, "inventory": []}
    return st


def proposal(kind: str, anchor_id: str, title: str = "", description: str = "") -> dict:
    return {
        "title": title or "Um pedido",
        "description": description,
        "kind": kind,
        "anchor_id": anchor_id,
        "reward_hint": "50 moedas de ouro",
    }


def first_anchor(menu: list[dict], kind: str) -> str:
    return next(i["anchor_id"] for i in menu if i["kind"] == kind)


RUMOR_SEED = "rumor_a_legiao_esta_fabricando_soldados_a_partir_de_mortos"
RUMOR_LOC = "na_anel_ferro"


def add_rumor(st: dict, *, truth: bool = True, perceived: int = 15, day: int = 15) -> str:
    """Injeta um rumor da lore (sem `secret_id`) em `st["world_sim"]` e devolve o `rumor_id`."""
    from tests.spec312_helpers import make_rumor

    item = make_rumor(
        st["world_sim"],
        RUMOR_SEED,
        region="nova_arcadia",
        loc=RUMOR_LOC,
        day=day,
        perceived=perceived,
        truth=truth,
    )
    return str(item["subject_id"])
