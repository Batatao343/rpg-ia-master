import json
import uuid

import persistence
from services import context_builder
from services.memory_summary import (
    NARRATIVE_SUMMARY_MAX_CHARS,
    compact_summary,
)


def test_compactacao_preserva_o_final_recente_dentro_do_limite():
    old = "Passado remoto. " * 200
    recent = "Agora Valen está em Brekmar diante do portão."
    compact = compact_summary(old + recent)
    assert len(compact) <= NARRATIVE_SUMMARY_MAX_CHARS
    assert compact.endswith(recent)
    assert compact.startswith("… ")


def test_save_e_load_compactam_resumo_legado(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    state = {
        "game_id": gid,
        "player": {"name": "Valen"},
        "world": {},
        "messages": [],
        "narrative_summary": "antigo. " * 1000,
    }
    assert persistence.save_game_state(state)
    raw = json.loads((tmp_path / f"{gid}.json").read_text(encoding="utf-8"))
    assert len(raw["narrative_summary"]) <= NARRATIVE_SUMMARY_MAX_CHARS
    loaded = persistence.load_game_state(str(tmp_path / f"{gid}.json"))
    assert len(loaded["narrative_summary"]) <= NARRATIVE_SUMMARY_MAX_CHARS


def test_memoria_grande_e_particionada_e_nao_desaparece():
    memory = "\n".join(f"[FATO {i}] " + ("x" * 300) for i in range(30))
    pack = context_builder.assemble_pack(
        [], context_builder.ContextBudget(max_tokens=1000), memory_text=memory,
    )
    assert pack.memory_block
    assert pack.total_tokens_est <= 1050
    assert pack.dropped > 0


def test_resumo_compacto_cabe_no_pack_de_story():
    state = {
        "world": {"current_location": "Brekmar", "turn_count": 8},
        "narrative_summary": "passado. " * 500 + "Valen chegou agora ao cais.",
        "memory_facts": [],
        "npcs": {},
    }
    pack = context_builder.build_context_pack(
        state, "cais", "story", token_budget=3500,
    )
    assert "Valen chegou agora ao cais" in pack.memory_block
