"""Integração pós-smoke: ConflictSummary é consumido uma vez e governa memória."""

from langchain_core.messages import AIMessage, HumanMessage

from agents import archivist, loot, storyteller
from agents import world_simulator
from agents.archivist import MemoryUpdate
import persistence
from services import conflict_summary as summary_service
from services import context_builder
from services.event_processor import process_pending_events
from services.memory_retry import (
    MAX_PENDING_NPC_MEMORY,
    enqueue_npc_memory,
)
from services.prose_guard import sanitize_meta_preamble


def _summary():
    return summary_service.build_summary([
        {"name": "Herói", "dead": False, "conscious": True,
         "ferimentos": {"leve": [], "grave": [], "critico": []}},
        {"name": "Brutamontes", "dead": True, "conscious": False,
         "ferimentos": {"leve": [], "grave": [], "critico": [{"regiao": "torso"}]}},
    ])


class _ArchivistLLM:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return MemoryUpdate(
            new_summary="A luta terminou.",
            important_facts=["O Brutamontes fugiu vivo."],
            chronicle_entry="Abaixo você encontra a narrativa: O aço silenciou.",
        )


class _ContradictoryArchivistLLM:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return MemoryUpdate(
            new_summary="O Brutamontes sobreviveu e fugiu para as montanhas.",
            important_facts=[],
            chronicle_entry="",
        )


class _PolicyArchivistLLM:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return MemoryUpdate(
            new_summary="O rumor mudou o humor da praça.",
            important_facts=["O dragão secreto tomou a cidade."],
            chronicle_entry="O dragão secreto tomou a cidade e virou canção.",
        )


def test_archivist_persiste_summary_uma_vez_e_limpa(monkeypatch):
    saved = []
    monkeypatch.setattr(archivist, "get_llm", lambda **_kwargs: _ArchivistLLM())
    monkeypatch.setattr(
        archivist, "add_memory_to_session",
        lambda game_id, facts: saved.append((game_id, list(facts))) or True,
    )
    state = {
        "game_id": "game-summary",
        "messages": [AIMessage(content="O Brutamontes caiu.")],
        "world": {"turn_count": 7},
        "narrative_summary": "Antes da luta.",
        "archive_due": True,
        "archivist_last_run": 0,
        "chronicle": [],
        "pending_world_events": [],
        "conflict_summary": _summary(),
    }
    out = archivist.archive_node(state)
    assert out["conflict_summary"] is None
    assert saved == [("game-summary", ["Brutamontes morreu no conflito."])]
    assert "Mortos: Brutamontes" in out["narrative_summary"]
    assert any(entry["kind"] == "conflict"
               for chapter in out["chronicle"] for entry in chapter["entries"])
    # O fato contraditório livre não foi promovido.
    assert all("fugiu vivo" not in fact for _game, facts in saved for fact in facts)


def test_grafo_real_consume_combate_loot_e_summary_no_mesmo_invoke(monkeypatch):
    import main
    from playtest.runner import _build_initial_state

    writes = []
    monkeypatch.setattr(archivist, "get_llm", lambda **_kwargs: _ArchivistLLM())
    monkeypatch.setattr(
        archivist,
        "add_memory_to_session",
        lambda game_id, facts: writes.append((game_id, list(facts))) or True,
    )
    monkeypatch.setattr(
        loot,
        "get_llm",
        lambda **_kwargs: type(
            "LootNarrator",
            (),
            {
                "is_fallback": False,
                "invoke": lambda self, _messages: AIMessage(
                    content="O saque rende exatamente sete moedas.",
                ),
            },
        )(),
    )
    monkeypatch.setattr(
        loot,
        "get_location",
        lambda location_id: {
            "id": location_id,
            "name": "Ponte Velha",
            "region_id": "planicie",
        },
    )
    monkeypatch.setattr(
        loot.economy,
        "roll_loot",
        lambda *_args, **_kwargs: {
            "gold": 7,
            "item_id": None,
            "rarity": "common",
        },
    )

    state = _build_initial_state("vertical-summary", 0)
    dead_enemy = {
        "id": "brutamontes_vertical",
        "name": "Brutamontes",
        "status": "morto",
        "dead": True,
        "conscious": False,
        "virtudes": {
            "forca": 3,
            "agilidade": 1,
            "corpo": 3,
            "mente": 1,
            "carisma": 1,
        },
        "vitalidade": 0,
        "max_vitalidade": 10,
        "ferimento_espacos": {"leve": 3, "grave": 2, "critico": 1},
        "ferimentos": {
            "leve": [],
            "grave": [],
            "critico": [{"regiao": "torso"}],
        },
        "esquiva": 10,
        "active_conditions": [],
    }
    scene = {
        "encounter_level": 2,
        "zones": [{"id": "z0", "name": "Ponte", "connections": []}],
        "positions": {},
        "objects": [],
        "enemies": [dead_enemy],
        "npcs": [],
    }
    current_location = state["world"]["current_location"]
    state.update({
        "messages": [HumanMessage(content="O combate terminou; vasculho os corpos.")],
        "enemies": [dead_enemy],
        "combat": {
            "active": True,
            "round": 1,
            "idle_turns": 0,
            "encounter_level": 2,
            "scene": scene,
        },
        "campaign_plan": {
            "location": current_location,
            "beats": [{"description": "Cruze a ponte.", "status": "pending"}],
            "climax": "Atravesse o rio.",
            "current_step": 0,
            "last_planned_turn": state["world"]["turn_count"],
            "arc_title": "A Ponte Velha",
        },
        "needs_replan": False,
        "archive_due": False,
        "pending_world_events": [],
        "consumed_conflict_ids": [],
    })

    node_updates = []
    final = state
    for mode, chunk in main.app.stream(
        state,
        stream_mode=["updates", "values"],
    ):
        if mode == "updates":
            node_updates.extend(chunk.items())
        elif mode == "values":
            final = chunk

    node_names = [name for name, _update in node_updates]
    assert node_names[:2] == ["action_guard", "turn_prepare"]
    assert set(node_names[2:4]) == {"campaign_manager", "dm_router"}
    assert node_names[4:] == [
        "dispatch", "combat_agent", "loot_agent", "archivist", "turn_finalizer",
    ]
    updates_by_name = {name: update for name, update in node_updates}
    combat_update = dict(updates_by_name["combat_agent"])
    loot_update = dict(updates_by_name["loot_agent"])
    conflict_id = combat_update["conflict_summary"]["conflict_id"]
    assert loot_update["conflict_summary"]["loot_obtido"] == [
        {"kind": "gold", "amount": 7},
    ]
    assert final.get("conflict_summary") is None
    assert final["consumed_conflict_ids"] == [conflict_id]
    assert len(writes) == 1
    assert writes[0][0] == state["game_id"]
    assert set(writes[0][1]) == {
        "Brutamontes morreu no conflito.",
        "O grupo obteve 7 de ouro no conflito.",
    }


def test_archivist_nao_reconsome_conflict_id_ja_confirmado(monkeypatch):
    saved = []
    monkeypatch.setattr(archivist, "get_llm", lambda **_kwargs: _ArchivistLLM())
    monkeypatch.setattr(
        archivist,
        "add_memory_to_session",
        lambda game_id, facts: saved.append((game_id, list(facts))) or True,
    )
    pending = summary_service.build_summary(
        [
            {"name": "Herói", "dead": False, "conscious": True},
            {"name": "Brutamontes", "dead": True, "conscious": False},
        ],
        extras={"conflict_id": "conflict-idempotent", "turn": 7},
    )
    state = {
        "game_id": "game-idempotent",
        "messages": [AIMessage(content="O Brutamontes caiu.")],
        "world": {"turn_count": 7},
        "narrative_summary": "Antes da luta.",
        "archive_due": True,
        "archivist_last_run": 0,
        "chronicle": [],
        "pending_world_events": [],
        "consumed_conflict_ids": [],
        "conflict_summary": pending,
    }
    first = archivist.archive_node(state)
    merged = {**state, **first}
    assert merged["consumed_conflict_ids"] == ["conflict-idempotent"]
    assert len(saved) == 1

    monkeypatch.setattr(
        archivist,
        "get_llm",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("conflito consumido não deve chamar LLM")
        ),
    )
    duplicate = archivist.archive_node({
        **merged,
        "conflict_summary": pending,
        "archive_due": True,
    })
    merged_duplicate = {**merged, **duplicate}
    assert merged_duplicate["conflict_summary"] is None
    assert merged_duplicate["consumed_conflict_ids"] == ["conflict-idempotent"]
    assert len(saved) == 1
    assert sum(
        entry["kind"] == "conflict"
        for chapter in merged_duplicate["chronicle"]
        for entry in chapter["entries"]
    ) == 1


def test_archivist_substitui_resumo_que_reverte_morte(monkeypatch):
    monkeypatch.setattr(
        archivist, "get_llm", lambda **_kwargs: _ContradictoryArchivistLLM(),
    )
    monkeypatch.setattr(
        archivist, "add_memory_to_session", lambda _game_id, _facts: True,
    )
    out = archivist.archive_node({
        "game_id": "game-contradiction",
        "messages": [AIMessage(content="O Brutamontes caiu.")],
        "world": {"turn_count": 7},
        "narrative_summary": "Antes da luta.",
        "archive_due": True,
        "archivist_last_run": 0,
        "chronicle": [],
        "pending_world_events": [],
        "conflict_summary": _summary(),
    })
    summary = out["narrative_summary"]
    assert "Mortos: Brutamontes" in summary
    assert "sobreviveu" not in summary.casefold()
    assert "fugiu" not in summary.casefold()


def test_archivist_falha_rag_preserva_summary_e_retry_sem_cronica(monkeypatch):
    attempts = []
    monkeypatch.setattr(archivist, "get_llm", lambda **_kwargs: _ArchivistLLM())
    monkeypatch.setattr(
        archivist,
        "add_memory_to_session",
        lambda game_id, facts: attempts.append((game_id, list(facts))) or False,
    )
    pending = _summary()
    state = {
        "game_id": "game-retry",
        "messages": [AIMessage(content="O Brutamontes caiu.")],
        "world": {"turn_count": 7},
        "narrative_summary": "Antes da luta.",
        "archive_due": True,
        "archivist_last_run": 0,
        "chronicle": [],
        "pending_world_events": [],
        "conflict_summary": pending,
    }

    failed = archivist.archive_node(state)

    assert attempts == [
        ("game-retry", ["Brutamontes morreu no conflito."]),
    ]
    assert failed["conflict_summary"] == pending
    assert failed["archive_due"] is True
    assert failed["rag_persistence_error"]
    assert "chronicle" not in failed
    assert "archivist_last_run" not in failed

    monkeypatch.setattr(
        archivist,
        "add_memory_to_session",
        lambda game_id, facts: attempts.append((game_id, list(facts))) or True,
    )
    retried = archivist.archive_node({**state, **failed})
    assert retried["conflict_summary"] is None
    assert retried["archive_due"] is False
    assert retried["rag_persistence_error"] is None
    assert sum(
        entry["kind"] == "conflict"
        for chapter in retried["chronicle"]
        for entry in chapter["entries"]
    ) == 1


def test_archivist_canonical_only_bloqueia_so_fatos_e_limpa_apos_commit(
    monkeypatch,
):
    attempts = []
    succeeds = False

    def persist(_game_id, facts):
        attempts.append(list(facts))
        return succeeds

    monkeypatch.setattr(
        archivist, "get_llm", lambda **_kwargs: _PolicyArchivistLLM(),
    )
    monkeypatch.setattr(archivist, "add_memory_to_session", persist)
    state = {
        "game_id": "game-policy",
        "messages": [AIMessage(content="Um rumor atravessa a praça.")],
        "world": {"turn_count": 8},
        "narrative_summary": "A praça estava calma.",
        "archive_due": True,
        "archivist_last_run": 0,
        "chronicle": [],
        "pending_world_events": [],
        "memory_fact_policy": "canonical_only",
        "memory_canonical_facts": ["A praça recebeu um rumor validado."],
    }

    failed = archivist.archive_node(state)
    assert attempts == [["A praça recebeu um rumor validado."]]
    assert "dragão secreto" not in " ".join(attempts[0]).casefold()
    assert failed["narrative_summary"] == "O rumor mudou o humor da praça."
    assert failed["archive_due"] is True
    assert failed["memory_fact_policy"] == "canonical_only"
    assert failed["memory_canonical_facts"] == [
        "A praça recebeu um rumor validado.",
    ]

    succeeds = True
    retried = archivist.archive_node({**state, **failed})
    assert retried["narrative_summary"] == "O rumor mudou o humor da praça."
    assert retried["archive_due"] is False
    assert retried["memory_fact_policy"] is None
    assert retried["memory_canonical_facts"] == []
    assert retried.get("chronicle", []) == []
    assert attempts == [
        ["A praça recebeu um rumor validado."],
        ["A praça recebeu um rumor validado."],
    ]


def test_archivist_nao_confirma_retry_vazio_nem_apaga_erro_previo(monkeypatch):
    monkeypatch.setattr(
        archivist,
        "get_llm",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("retry sem payload não deve gastar LLM")
        ),
    )
    monkeypatch.setattr(
        archivist,
        "add_memory_to_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("persist([]) não é commit")
        ),
    )
    state = {
        "game_id": "game-empty-retry",
        "messages": [AIMessage(content="O NPC respondeu.")],
        "world": {"turn_count": 9},
        "narrative_summary": "A conversa segue.",
        "archive_due": True,
        "archivist_last_run": 0,
        "chronicle": [],
        "pending_world_events": [],
        "memory_fact_policy": "canonical_only",
        "memory_canonical_facts": [],
        "rag_persistence_error": "Falha ao persistir memória de npc_aldric.",
    }

    out = archivist.archive_node(state)

    assert out["archive_due"] is True
    assert out["memory_fact_policy"] == "canonical_only"
    assert out["memory_canonical_facts"] == []
    assert out["rag_persistence_error"] == state["rag_persistence_error"]
    assert "archivist_last_run" not in out


def test_archivist_retry_npc_falha_depois_confirma_e_limpa(monkeypatch):
    succeeds = False
    attempts = []

    def persist_npc(game_id, npc_id, facts):
        attempts.append((game_id, npc_id, list(facts)))
        return succeeds

    monkeypatch.setattr(archivist, "add_npc_memory", persist_npc)
    monkeypatch.setattr(
        archivist, "get_llm", lambda **_kwargs: _PolicyArchivistLLM(),
    )
    monkeypatch.setattr(
        archivist,
        "add_memory_to_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("retry NPC não deve virar write global")
        ),
    )
    state = {
        "game_id": "game-npc-retry",
        "messages": [AIMessage(content="O NPC respondeu.")],
        "world": {"turn_count": 9},
        "narrative_summary": "A conversa segue.",
        "archive_due": True,
        "archivist_last_run": 0,
        "chronicle": [],
        "pending_world_events": [],
        "memory_fact_policy": "canonical_only",
        "memory_canonical_facts": [],
        "pending_npc_memory": [{
            "operation": "add_npc_memory",
            "npc_id": "npc_aldric",
            "facts": ["Aldric ouviu o juramento do jogador."],
        }],
        "rag_persistence_error": "Falha ao persistir memória de npc_aldric.",
    }

    failed = archivist.archive_node(state)
    assert failed["pending_npc_memory"] == state["pending_npc_memory"]
    assert failed["archive_due"] is True
    assert failed["memory_fact_policy"] == "canonical_only"
    assert failed["rag_persistence_error"]
    assert attempts == [(
        "game-npc-retry",
        "npc_aldric",
        ["Aldric ouviu o juramento do jogador."],
    )]

    succeeds = True
    retried = archivist.archive_node({**state, **failed})
    assert retried["pending_npc_memory"] == []
    assert retried["rag_persistence_error"] is None
    assert retried["archive_due"] is False
    assert retried["memory_fact_policy"] is None
    assert retried["memory_facts"][0]["provenance"] == "npc_claim"
    assert retried["memory_facts"][0]["confidence"] == "reported"
    assert len(attempts) == 2

    # Confirmado: uma chamada trivial posterior não repete a escrita.
    merged = {**state, **failed, **retried}
    monkeypatch.setattr(
        archivist,
        "get_llm",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("turno confirmado não deve reabrir o archivist")
        ),
    )
    third = archivist.archive_node(merged)
    assert third == {"archive_due": False}
    assert len(attempts) == 2


def test_archivist_retry_npc_remove_so_sucessos(monkeypatch):
    attempted_ids = []

    def persist_npc(_game_id, npc_id, _facts):
        attempted_ids.append(npc_id)
        return npc_id == "npc_ok"

    monkeypatch.setattr(archivist, "add_npc_memory", persist_npc)
    monkeypatch.setattr(
        archivist,
        "get_llm",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("fila parcialmente falha não confirma o archive")
        ),
    )
    out = archivist.archive_node({
        "game_id": "game-npc-partial",
        "messages": [],
        "world": {"turn_count": 3},
        "archive_due": True,
        "archivist_last_run": 0,
        "memory_fact_policy": "canonical_only",
        "pending_world_events": [],
        "pending_npc_memory": [
            {
                "operation": "add_npc_memory",
                "npc_id": "npc_ok",
                "facts": ["Fato já confirmado."],
            },
            {
                "operation": "add_npc_memory",
                "npc_id": "npc_falha",
                "facts": ["Fato ainda pendente."],
            },
        ],
        "rag_persistence_error": "falha anterior",
    })

    assert attempted_ids == ["npc_ok", "npc_falha"]
    assert [row["npc_id"] for row in out["pending_npc_memory"]] == [
        "npc_falha",
    ]
    assert out["archive_due"] is True
    assert out["rag_persistence_error"] == "falha anterior"


def test_fila_npc_e_bounded_deduplicada_e_sanitizada():
    queue = []
    for index in range(MAX_PENDING_NPC_MEMORY + 10):
        queue = enqueue_npc_memory(
            queue,
            f" npc_{index} ",
            f" fato   observável {index} ",
        )
    queue = enqueue_npc_memory(
        queue,
        f"npc_{MAX_PENDING_NPC_MEMORY + 9}",
        f"fato observável {MAX_PENDING_NPC_MEMORY + 9}",
    )

    assert len(queue) == MAX_PENDING_NPC_MEMORY
    assert queue[0]["npc_id"] == "npc_10"
    assert queue[-1]["facts"] == [
        f"fato observável {MAX_PENDING_NPC_MEMORY + 9}",
    ]
    assert all(set(row) == {"operation", "npc_id", "facts"} for row in queue)


def test_loot_usa_nivel_do_encontro_e_enriquece_summary(monkeypatch):
    seen = {}

    def roll(region_id, danger, rng, projection, bestiary_knowledge, turn, boost):
        seen.update(region_id=region_id, danger=danger)
        return {"gold": 17, "item_id": None, "rarity": "common"}

    monkeypatch.setattr(loot.economy, "roll_loot", roll)
    monkeypatch.setattr(loot, "get_location",
                        lambda _loc: {"name": "Ponte", "region_id": "planicie"})
    monkeypatch.setattr(loot, "_narrate", lambda *_args, **_kwargs: "Espólio recolhido.")
    state = {
        "player": {"gold": 2, "inventory": []},
        "world": {"current_location_id": "ponte", "danger_level": 2, "turn_count": 4},
        "combat": {"encounter_level": 6},
        "conflict_summary": _summary(),
        "loot_source": "TREASURE",
        "messages": [],
        "world_projection": {},
        "bestiary_knowledge": {},
    }
    out = loot.loot_node(state)
    assert seen == {"region_id": "planicie", "danger": 6}
    assert out["player"]["gold"] == 19
    assert out["conflict_summary"]["loot_obtido"] == [{"kind": "gold", "amount": 17}]


def test_narrativa_contraditoria_cai_no_resumo_canonico():
    summary = _summary()
    proposed = "Brutamontes sobreviveu e foge para as montanhas."
    out = summary_service.narrative_or_fallback(summary, proposed)
    assert out != proposed
    assert "Mortos: Brutamontes" in out


def test_preambulo_meta_e_removido():
    assert sanitize_meta_preamble(
        "Abaixo você encontra a narrativa: A chuva cai sobre a ponte."
    ) == "A chuva cai sobre a ponte."


def test_lore_global_e_memoria_de_sessao_ficam_em_blocos_separados(monkeypatch):
    monkeypatch.setattr(context_builder, "query_rag",
                        lambda *_args, **_kwargs: "LORE CANÔNICO")
    monkeypatch.setattr(context_builder, "query_session_memory",
                        lambda *_args, **_kwargs: "MEMÓRIA DA CAMPANHA")
    pack = context_builder.build_context_pack(
        {"world": {}, "narrative_summary": "Resumo recente.", "npcs": {}},
        query="ponte", purpose="story", game_id="game-1", token_budget=900,
    )
    assert "LORE CANÔNICO" in pack.lore_block
    assert "MEMÓRIA DA CAMPANHA" not in pack.lore_block
    assert "MEMÓRIA DA CAMPANHA" in pack.memory_block


def test_evento_rejeitado_fica_observavel_sem_payload_livre():
    out = process_pending_events({
        "world": {"turn_count": 9},
        "pending_world_events": [{
            "type": "evento_inventado",
            "target_id": "xanadu",
            "payload": {"segredo": "não deve vazar"},
        }],
        "event_log": [],
        "world_projection": {},
        "chronicle": [],
        "quests": [],
    })
    assert out["pending_world_events"] == []
    assert out["event_rejections"][0]["turn"] == 9
    assert out["event_rejections"][0]["type"] == "evento_inventado"
    assert "payload" not in out["event_rejections"][0]


class _WorldLLM:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return world_simulator.WorldPulse(
            rumor="Sinos ecoam ao longe.",
            fact="O dragão secreto tomou a cidade inteira.",
            danger_shift=1,
        )


def test_world_pulse_persiste_so_consequencia_aplicada(monkeypatch):
    saved = []
    monkeypatch.setattr(world_simulator, "get_llm", lambda **_kwargs: _WorldLLM())
    monkeypatch.setattr(
        world_simulator, "add_memory_to_session",
        lambda game_id, facts: saved.extend(facts) or True)
    world_simulator.simulate_world(
        {"game_id": "g"},
        {"current_location_id": "nova_arcadia",
         "current_location": "Nova Arcádia", "danger_level": 1,
         "world_clock": {"day": 1, "period": 1}},
        [], {}, periods=1,
    )
    assert saved
    assert all("dragão secreto" not in fact.casefold() for fact in saved)
    assert any("perigo de Nova Arcádia mudou" in fact for fact in saved)


def test_evento_rejeitado_nao_vira_fato_do_archivist(monkeypatch):
    saved = []
    monkeypatch.setattr(archivist, "get_llm", lambda **_kwargs: _ArchivistLLM())
    monkeypatch.setattr(
        archivist, "add_memory_to_session",
        lambda _game_id, facts: saved.extend(facts) or True)
    state = {
        "game_id": "game-rejected",
        "messages": [AIMessage(content="Xanadu agora pertence ao herói.")],
        "world": {"turn_count": 8},
        "narrative_summary": "O herói segue na ponte.",
        "archive_due": True,
        "archivist_last_run": 0,
        "chronicle": [],
        "event_log": [],
        "world_projection": {},
        "quests": [],
        "pending_world_events": [{
            "type": "evento_inventado", "target_id": "xanadu", "payload": {}}],
    }
    out = archivist.archive_node(state)
    assert saved == []
    assert out["narrative_summary"] == "O herói segue na ponte."
    assert out["event_rejections"]


def test_viagem_impossivel_e_recusada_antes_da_llm(monkeypatch):
    monkeypatch.setattr(
        storyteller, "get_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("LLM não deve ser chamada")))
    out = storyteller.storyteller_node({
        "messages": [HumanMessage(content="Viajo agora para Xanadu.")],
        "world": {"current_location_id": "nova_arcadia"},
        "player": {},
        "factions": [],
        "npcs": {},
    })
    text = out["messages"][0].content
    assert "Não há rota direta" in text
    assert out["world"]["current_location_id"] == "nova_arcadia"
    assert "Xanadu" not in out["world"].get("current_location", "")


def test_pergunta_sobre_local_distante_nao_vira_intencao_de_viagem(monkeypatch):
    class ReachedLLM(RuntimeError):
        pass

    monkeypatch.setattr(
        storyteller,
        "get_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ReachedLLM),
    )
    state = {
        "messages": [
            HumanMessage(content="O que você sabe sobre Skallgard e sua história?")
        ],
        "world": {"current_location_id": "nova_arcadia"},
        "player": {},
        "factions": [],
        "npcs": {},
    }
    try:
        storyteller.storyteller_node(state)
    except ReachedLLM:
        pass
    else:
        raise AssertionError("pergunta factual foi recusada como viagem impossível")


def test_save_roundtrip_preserva_summary_pendente():
    pending = _summary()
    raw = persistence._state_to_save_data({
        "game_id": "g",
        "player": {"vitalidade": 4, "max_vitalidade": 8},
        "conflict_summary": pending,
        "consumed_conflict_ids": ["conflict-old"],
        "archive_due": True,
        "memory_fact_policy": "canonical_only",
        "memory_canonical_facts": ["Fato aguardando retry."],
        "pending_npc_memory": [
            {
                "operation": "add_npc_memory",
                "npc_id": "npc_aldric",
                "facts": ["Aldric ouviu o juramento."],
            },
            {
                "operation": "add_npc_memory",
                "npc_id": "npc_aldric",
                "facts": ["Aldric ouviu o juramento."],
            },
        ],
        "rag_persistence_error": "embeddings_unavailable",
        "event_rejections": [{"turn": 1, "type": "x", "reason": "inválido"}],
        "messages": [],
    }, "g")
    loaded = persistence._raw_to_state(raw)
    assert loaded["conflict_summary"] == pending
    assert loaded["consumed_conflict_ids"] == ["conflict-old"]
    assert loaded["archive_due"] is True
    assert loaded["memory_fact_policy"] == "canonical_only"
    assert loaded["memory_canonical_facts"] == ["Fato aguardando retry."]
    assert loaded["pending_npc_memory"] == [{
        "operation": "add_npc_memory",
        "npc_id": "npc_aldric",
        "facts": ["Aldric ouviu o juramento."],
    }]
    assert loaded["rag_persistence_error"] == "embeddings_unavailable"
    assert loaded["event_rejections"] == raw["event_rejections"]
