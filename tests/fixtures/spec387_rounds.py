"""SPEC-387 R22/R24 - roda UMA rodada do motor (MockLLM, sem rede) sobre um save semeado, com semente fixa.

O RNG da rodada e o modulo `random` global (`agents/combat.py`), entao a semente nao fixa o dado: cada
variante garante o resultado pelos NUMEROS da cena (Esquiva baixa, presságio congelado) e os testes rodam
50 sementes de `random` exigindo o mesmo resultado em todas.
"""

from __future__ import annotations

import copy
import random
from typing import Any

from langchain_core.messages import HumanMessage

from tests.fixtures import spec368_seed as sd


def load(item: int, variant: str, saves_dir: str) -> tuple[str, dict]:
    import persistence

    gid = sd.seed_save(item, variant=variant, saves_dir=saves_dir)
    with sd._legacy(saves_dir):
        state = persistence.load_game_state(persistence.save_path(gid))
    return gid, state


def step_card(card_id: str, target: str | None = None) -> dict:
    return {"kind": "card", "card_id": card_id, "target_id": target, "params": {"ruptura": False}}


def play(
    state: dict, steps: list[dict], seed: int, *, reaction: str | None = None
) -> tuple[dict, str, dict]:
    """Uma rodada (copia do estado). Devolve `(out_do_no, texto_da_mensagem, saida_crua_do_run_round)`."""
    import agents.combat as combat
    from services import conflict_orchestrator as orch

    st = copy.deepcopy(state)
    st["messages"] = [*st.get("messages", []), HumanMessage(content="Encerro a rodada.")]
    st["player_reaction_card_id"] = reaction
    st["combat_declaration"] = {
        "actor_id": "player",
        "acao": steps[0] if steps else {"kind": "pass"},
        "jogadas": steps,
        "reaction_card_id": reaction,
    }
    random.seed(seed)
    raw: dict[str, Any] = {}
    real = orch.run_round

    def spy(*a: Any, **k: Any) -> dict:
        raw.update(real(*a, **k))
        return raw

    orch.run_round = spy
    try:
        out: dict[str, Any] = combat.combat_node(st)
    finally:
        orch.run_round = real
    text = "\n".join(str(getattr(m, "content", m)) for m in out.get("messages", []))
    return out, text, raw
