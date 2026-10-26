"""SPEC-319 R10: o campo de narracao tem de ser o 1o campo dos schemas de narracao.

O extrator incremental so enxerga a string se ela abrir o objeto JSON da tool call; reordenar
os campos silenciaria o streaming de tokens (cai no pseudo-streaming da SPEC-316)."""

from __future__ import annotations

import pytest

from agents.npc import NPCResponse
from agents.storyteller import (
    StoryUpdate,
    StoryUpdateWithRumorClaims,
    StoryUpdateWithRumors,
)


@pytest.mark.parametrize(
    ("schema", "first"),
    [
        (StoryUpdate, "narrative"),
        (StoryUpdateWithRumors, "narrative"),
        (StoryUpdateWithRumorClaims, "narrative"),
        (NPCResponse, "dialogue"),  # a fala do NPC e a "narrativa" desse no
    ],
)
def test_narrative_is_first_field(schema, first):
    assert next(iter(schema.model_fields)) == first
    props = list(schema.model_json_schema()["properties"])
    assert props[0] == first
