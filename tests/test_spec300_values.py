"""SPEC-300 Etapa 0 — dados e contratos (traços, fações, catálogo, templates, ganchos)."""

import json
import re
from pathlib import Path
from typing import get_args

from services import companion_soul as cs
from services import companion_tags as ctags
from services import reputation

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_todo_trait_tem_vetor():
    traits = {t["id"] for t in _load("traits.json")["traits"]}
    assert len(traits) == 80
    assert traits <= set(_load("companion_values.json")["traits"])


def test_toda_faccao_tem_vetor():
    factions = set(_load("factions.json"))
    assert len(factions) == 19
    assert factions <= set(_load("companion_values.json")["factions"])


def test_valores_no_intervalo_e_eixos_fechados():
    tab = _load("companion_values.json")
    assert tuple(tab["axes"]) == cs.AXES
    for group in ("traits", "factions", "races", "regions"):
        for key, vec in tab[group].items():
            for axis, val in vec.items():
                assert axis in cs.AXES, (group, key, axis)
                assert val in (-2, -1, 0, 1, 2), (group, key, axis)


def test_raca_e_regiao_cobrem_origins():
    origins = _load("origins.json")
    tab = _load("companion_values.json")
    assert {r["id"] for r in origins["races"]} <= set(tab["races"])
    assert {r["id"] for r in origins["regions"]} <= set(tab["regions"])


def test_betrayal_traits_existem_no_catalogo():
    traits = {t["id"] for t in _load("traits.json")["traits"]}
    tab = _load("companion_values.json")
    listed = set(tab["betrayal_blockers"]) | set(tab["romance_blockers_until_personal_quest"])
    for ids in tab["betrayal_traits"].values():
        listed |= set(ids)
    assert listed <= traits
    # traição por traço (dono): ganancioso rouba, rancoroso entrega
    assert "ganancioso" in tab["betrayal_traits"]["steal"]
    assert "rancoroso" in tab["betrayal_traits"]["deliver"]


def test_catalogo_de_tags_schema():
    cat = ctags.catalog()
    assert len(cat) == 16  # +poupou_inimigo (SPEC-325)
    for tid, tag in cat.items():
        assert tag["source"] in {"event", "combat", "baseline", "action_regex", "engine"}
        assert 1 <= tag["magnitude"] <= 3
        assert set(tag["axes"]) <= set(cs.AXES)
        if tag["source"] == "action_regex":
            assert tag["magnitude"] == 1, tid


def test_templates_de_missao_pessoal_referenciam_traits_reais():
    traits = {t["id"] for t in _load("traits.json")["traits"]}
    regions = {r["id"] for r in _load("origins.json")["regions"]}
    quests = _load("companion_quests.json")
    assert set(quests["by_trait"]) <= traits
    assert set(quests["by_region"]) <= regions
    for tpl in [*quests["by_trait"].values(), *quests["by_region"].values(), quests["fallback"]]:
        assert {"title", "description", "reward_hint"} <= set(tpl)


def test_hook_mundo_vivo_em_entities():
    entities = _load("graph/entities.json")
    mv = {k: v for k, v in entities.items() if k.startswith("npc_mv_")}
    assert len(mv) == 36
    for npc_id, ent in mv.items():
        hook = ent["components"].get("hook")
        assert hook, npc_id
        body = (DATA / "codex" / "npcs" / "mundo_vivo" / f"{npc_id}.md").read_text(encoding="utf-8")
        match = re.search(r"^Gancho: (.+)$", body, re.M)
        assert match and match.group(1).strip() == hook


def test_rotulos_usam_vocabulario_de_reputacao():
    assert {cs.approval_label(a) for a in range(0, 101)} <= set(get_args(reputation.NpcTier))
