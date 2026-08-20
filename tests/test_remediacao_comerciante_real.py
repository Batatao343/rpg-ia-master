from __future__ import annotations

import copy

from langchain_core.messages import HumanMessage

from agents import loot
import llm_setup
import party
from services import npc_layers, prose_guard


def _market_state(message: str = "Examino o estoque e anoto os preços.") -> dict:
    return {
        "game_id": "merchant-remediation",
        "messages": [HumanMessage(content=message)],
        "loot_source": "SHOP",
        "player": {
            "name": "Iria", "class_name": "Sangromante", "level": 4,
            "gold": 500, "vitalidade": 18, "max_vitalidade": 18,
            "inventory": [{"id": "corda", "qty": 2}], "equipment": {},
        },
        "world": {
            "current_location_id": "na_anel_dourado", "visited": ["na_anel_dourado"],
            "turn_count": 3, "world_clock": {"day": 1, "period": "manha"},
            "merchant_stocks": {}, "merchant_restock_day": {}, "danger_level": 1,
        },
        "world_projection": {}, "factions": [], "npcs": {}, "enemies": [],
    }


def test_observar_mercado_nao_cria_transacao_nem_muta_player():
    state = _market_state()
    before = copy.deepcopy(state["player"])

    out = loot.loot_node(state)

    assert out.get("player") is None
    assert out.get("last_economy_action") is None
    assert state["player"] == before
    assert "consulta sem transação" in out["messages"][0].content
    assert "compra" in out["messages"][0].content


def test_verbo_de_compra_explicito_vence_vocabulario_de_observacao(monkeypatch):
    class FakeStructured:
        def invoke(self, _messages):
            return loot.TradeIntent(mode="observe", item_ref="corda", qty=1)

    class FakeLLM:
        def with_structured_output(self, _schema):
            return FakeStructured()

    monkeypatch.setattr(loot, "get_llm", lambda **_kwargs: FakeLLM())
    intent = loot._parse_trade_intent(
        _market_state(), "SHOP", "Confiro o preço e compro uma corda."
    )
    assert intent.mode == "buy"
    assert intent.item_ref == "corda"


def test_venda_exibe_delta_negativo_de_item(monkeypatch):
    monkeypatch.setattr(
        loot, "_parse_trade_intent",
        lambda *_args: loot.TradeIntent(mode="sell", item_ref="corda", qty=1),
    )
    monkeypatch.setattr(loot, "_narrate", lambda *_args, **_kwargs: "Negócio fechado.")
    out = loot.loot_node(_market_state("Vendo uma corda."))
    assert "[SISTEMA] -1x" in out["messages"][0].content


def test_npc_remoto_nao_entra_em_contexto_nem_combate():
    remote = {
        "Mercador": {"name": "Mercador", "in_scene": True, "relationship": 9,
                     "home_location_id": "dz_borda_do_vazio", "role": "guerreiro"}
    }
    state = {
        "world": {"current_location_id": "deserto_zhur"},
        "npcs": remote, "party": [], "factions": [],
    }
    assert npc_layers.npcs_in_scene(state) == []
    assert npc_layers.npcs_for_context(state) == []
    assert party.scene_allies(state) == []


def test_saldo_do_heroi_e_reconciliado_sem_alterar_preco():
    text = (
        "As 84 moedas de ouro pesando no fundo da bolsa lembram o risco. "
        "A corda custa 84 moedas de ouro."
    )
    fixed = prose_guard.reconcile_player_gold_claims(text, 148)
    assert "As 148 moedas de ouro" in fixed
    assert "custa 84 moedas" in fixed


def test_fast_tenta_groq_logo_apos_deepseek():
    assert [provider for provider, _model in llm_setup.ROUTES[llm_setup.ModelTier.FAST]][:2] == [
        "deepseek", "groq",
    ]

