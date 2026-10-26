"""Rótulo público da oferta de retrato de NPC usa o nome de exibição, nunca o token runtime."""

import api


def _row(subject_id: str, subject: str) -> dict:
    return {
        "offer_id": "o1",
        "type": "npc",
        "trigger": {"subject_id": subject_id},
        "brief": {"subject": subject},
    }


def test_runtime_token_resolves_to_npc_name_from_state():
    state = {"npcs": {"npc_x": {"name": "Mulher do balde"}}}
    out = api._public_art_offer(
        _row("runtime_npc:mulher_do_balde", "runtime_npc:mulher_do_balde"), state
    )
    assert out["label"] == "Mulher do balde"
    assert out["subject_id"] == "runtime_npc:mulher_do_balde"


def test_runtime_token_without_state_is_humanized():
    out = api._public_art_offer(_row("runtime_npc:homem_do_carrinho_de_sucata", ""))
    assert out["label"] == "Homem do carrinho de sucata"
    assert "runtime_npc" not in out["label"]


def test_plain_name_is_kept():
    out = api._public_art_offer(_row("npc_cego", "O Cego"))
    assert out["label"] == "O Cego"
