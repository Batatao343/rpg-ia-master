"""SPEC-313 Etapa 1: catalogo, schema e lint de lore."""

from __future__ import annotations

import ast
import itertools
import pathlib
import re
import unicodedata

import gamedata
from services import lore_quests as lq
from services import world_pressures as wp
from services.structured_outputs import ProposedQuest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIRED = (
    "origin",
    "anchor_type",
    "deadline_rule",
    "reward_rule",
    "lore_refs",
    "lore_keyword",
    "action_vocab",
    "combat_counts",
    "relief",
    "title",
    "description",
    "fail_text",
)


def _fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )


def _lines(ref: str) -> str:
    """Lê SÓ o intervalo citado (`arquivo:a-b`), sem abrir o arquivo inteiro."""
    path, _sep, span = ref.partition(":")
    a, _sep, b = span.partition("-")
    file = ROOT / path
    assert file.exists(), ref
    with file.open(encoding="utf-8") as fh:
        rows = list(itertools.islice(fh, int(a) - 1, int(b)))
    assert rows, f"intervalo fora do arquivo: {ref}"
    return " ".join(rows)


def test_five_lore_kinds_in_catalog_with_required_fields():
    kinds = wp._load_json("world_quests.json")["kinds"]
    assert lq.LORE_KINDS <= set(kinds)
    for kind in lq.LORE_KINDS:
        row = kinds[kind]
        missing = [f for f in REQUIRED if f not in row]
        assert not missing, (kind, missing)
        assert row["lore_refs"], kind


def test_lore_refs_exist_and_keyword_in_range():
    kinds = wp._load_json("world_quests.json")["kinds"]
    for kind in lq.LORE_KINDS:
        row = kinds[kind]
        text = _fold(" ".join(_lines(ref) for ref in row["lore_refs"]))
        assert _fold(row["lore_keyword"]) in text, (kind, row["lore_keyword"])


def test_delivery_routes_reference_real_ids():
    regions = set(wp.region_ids())
    for r in lq.cfg()["delivery_routes"]:
        art = gamedata.ARTIFACTS_DB[r["item_id"]]
        assert art["type"] == "material", r["id"]
        assert gamedata.get_location(r["to"]), r["id"]
        assert r["origin_region"] in regions, r["id"]
        assert _fold(r["lore_keyword"]) in _fold(_lines(r["lore_ref"])), r["id"]


def test_proposed_quest_has_kind_and_anchor_only():
    fields = set(ProposedQuest.model_fields)
    assert {"kind", "anchor_id"} <= fields
    assert not [f for f in fields if re.search(r"deadline|reward_gold|days|prazo", f)]
    q = ProposedQuest(title="x")
    assert q.kind == "comum" and q.anchor_id == ""


def test_legacy_quest_and_npc_sim_roundtrip(monkeypatch):
    """R30: quest sem os campos novos e npc_sim sem `escort` seguem as regras atuais."""
    from services import npc_world, quest_log
    from tests.spec313_helpers import NPC_KEY, npc_state, setup_env

    setup_env(monkeypatch)
    quest = {"id": "q1", "title": "x", "status": "active", "progress_log": []}
    done, gold = quest_log.complete_quest_with_reward([quest], "q1", 3)
    assert gold == quest_log.QUEST_REWARD_GOLD and done[0]["status"] == "completed"
    assert "outcome_label" not in quest_log.public_quest_view(quest, 5)
    st = npc_state()
    assert npc_world.presence(st, NPC_KEY) == ("skallgard", False)
    assert npc_world.escort_sync(st) == {}


def test_no_global_random_in_lore_quests():
    tree = ast.parse((ROOT / "services" / "lore_quests.py").read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    imports = {
        a.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
        for a in n.names
    }
    assert "random" not in names and "random" not in imports


def test_lore_module_builds_no_quest_dict_and_calls_no_llm():
    """R7: so `world_quests` monta dict com `world_kind`; R29: nenhuma chamada LLM nova."""
    src = (ROOT / "services" / "lore_quests.py").read_text(encoding="utf-8")
    assert '"world_kind":' not in src
    assert "get_llm" not in src and "invoke(" not in src
