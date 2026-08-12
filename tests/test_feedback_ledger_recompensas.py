from agents.storyteller import (
    _is_monetary_claim,
    _reward_confirmation,
)


def test_claim_monetario_nao_e_item():
    assert _is_monetary_claim("15 de ouro")
    assert _is_monetary_claim("uma bolsa de moedas")
    assert not _is_monetary_claim("Adaga de Ferro")


def test_confirmacao_usa_delta_real_do_ledger():
    before = {"gold": 10, "inventory": []}
    after = {
        "gold": 25,
        "inventory": [{"id": "espada_curta", "qty": 1}],
    }
    note = _reward_confirmation(before, after)
    assert "+15 de ouro" in note
    assert "Espada Curta" in note


def test_sem_delta_nao_confirma_claim_textual():
    player = {"gold": 10, "inventory": []}
    assert _reward_confirmation(player, player) == ""
