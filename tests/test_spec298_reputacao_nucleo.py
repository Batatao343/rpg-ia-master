"""SPEC-298 Etapa 1 — núcleo puro: faixas, fama, teto por turno, avisos."""

import re

import pytest

from services import reputation as rep
from services.dossiers import disposition_label

NPC_TIERS = ("hostil", "desconfiado", "neutro", "amistoso", "leal")


def test_npc_tier_faixas_iguais_dossie():
    for value in range(0, 11):
        assert disposition_label(value) == rep.npc_tier(value).capitalize()
    assert [rep.npc_tier(v) for v in (0, 1, 2, 3, 4, 6, 7, 8, 9, 10)] == [
        "hostil",
        "hostil",
        "desconfiado",
        "desconfiado",
        "neutro",
        "neutro",
        "amistoso",
        "amistoso",
        "leal",
        "leal",
    ]
    assert rep.npc_tier("lixo") == "neutro"


@pytest.mark.parametrize(
    ("value", "tier"),
    [
        (-100, "hostil"),
        (-40, "hostil"),
        (-39, "desconfiado"),
        (-10, "desconfiado"),
        (-9, "neutro"),
        (9, "neutro"),
        (10, "amistoso"),
        (39, "amistoso"),
        (40, "aliado"),
    ],
)
def test_faction_tier_limiares(value, tier):
    assert rep.faction_tier(value) == tier


def test_fame_view_rotulos_e_clamp():
    assert rep.fame_view(0, 0) == {"renown_label": "desconhecido", "infamy_label": "—"}
    assert rep.fame_view(10, 10) == {"renown_label": "conhecido", "infamy_label": "malvisto"}
    assert rep.fame_view(30, 30) == {"renown_label": "afamado", "infamy_label": "temido"}
    assert rep.fame_view(60, 60) == {"renown_label": "lendário", "infamy_label": "odiado"}
    assert rep.fame_view(999, -5) == {"renown_label": "lendário", "infamy_label": "—"}


def _state(rel=5, turn=3):
    return {
        "world": {"turn_count": turn},
        "npcs": {"Brenna": {"id": "npc_brenna", "name": "Brenna", "relationship": rel}},
    }


def test_apply_npc_delta_clamp_0_10_e_teto_turno():
    st = _state(rel=10)
    row, notice = rep.apply_npc_delta(st, "Brenna", 1, reason="t", source="llm")
    assert row["relationship"] == 10 and notice is None
    st = _state(rel=5)
    row, n1 = rep.apply_npc_delta(st, "Brenna", 5, reason="t", source="llm")
    assert row["relationship"] == 6 and n1
    st["npcs"]["Brenna"] = row
    row, _ = rep.apply_npc_delta(st, "Brenna", 1, reason="t", source="llm")
    assert row["relationship"] == 6  # LLM já usou o +1 do turno
    st["npcs"]["Brenna"] = row
    row, _ = rep.apply_npc_delta(st, "Brenna", 3, reason="t", source="engine")
    assert row["relationship"] == 7  # motor soma +1 => teto efetivo ±2
    st["npcs"]["Brenna"] = row
    row, _ = rep.apply_npc_delta(st, "Brenna", 1, reason="t", source="engine")
    assert row["relationship"] == 7
    st["world"]["turn_count"] = 4  # turno novo zera o orçamento
    st["npcs"]["Brenna"] = row
    row, _ = rep.apply_npc_delta(st, "Brenna", -1, reason="t", source="llm")
    assert row["relationship"] == 6


def test_aviso_template_sem_numero():
    _, bad = rep.apply_npc_delta(_state(), "Brenna", -1, reason="t", source="llm")
    _, good = rep.apply_npc_delta(_state(), "Brenna", 1, reason="t", source="llm")
    assert bad["text"] == "Brenna não gostou disso."
    assert good["text"] == "Brenna parece mais à vontade com você."
    assert bad["kind"] == "npc" and bad["turn"] == 3
    assert not re.search(r"\d", bad["text"] + good["text"])


def test_reveal_e_linhas_por_faixa():
    assert [rep.reveal_ceiling(t) for t in NPC_TIERS] == [
        "",
        "",
        "existencia",
        "objetivo",
        "progresso",
    ]
    assert [rep.knowledge_lines_cap(t) for t in NPC_TIERS] == [0, 2, 4, 6, 8]
