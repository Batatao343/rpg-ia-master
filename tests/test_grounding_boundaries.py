"""Regressões das fronteiras narrativas descobertas no smoke real."""

from types import SimpleNamespace

from langchain_core.messages import HumanMessage, SystemMessage

from agents import archivist, storyteller
from agents.archivist import MemoryUpdate
import mock_llm
from services.event_processor import prevalidate_event_batch, process_pending_events
from services.prose_guard import sanitize_meta_preamble


class _StoryLLM:
    def __init__(self, *, narrative: str, events=None, **update_fields):
        self.narrative = narrative
        self.events = list(events or [])
        self.update_fields = update_fields

    def with_structured_output(self, model):
        self.model = model
        return self

    def invoke(self, _messages):
        return self.model(
            narrative=self.narrative,
            proposed_events=self.events,
            **self.update_fields,
        )


def _story_state(text: str) -> dict:
    return {
        "game_id": "grounding-test",
        "messages": [HumanMessage(content=text)],
        "narrative_summary": "O herói permanece em Nova Arcádia.",
        "archivist_last_run": 0,
        "player": {
            "name": "Ari",
            "class_name": "Devoto do Abismo",
            "level": 1,
            "vitalidade": 8,
            "max_vitalidade": 8,
            "hp": 8,
            "max_hp": 8,
            "inventory": [],
        },
        "world": {
            "current_location_id": "nova_arcadia",
            "current_location": "Nova Arcádia",
            "turn_count": 4,
            "danger_level": 1,
            "world_clock": {"day": 1, "period": "Manhã"},
            "visited": ["nova_arcadia"],
        },
        "npcs": {},
        "factions": [],
        "faction_intel": {},
        "quests": [],
        "campaign_plan": {},
        "event_log": [],
        "world_projection": {},
    }


def _stub_context(monkeypatch):
    monkeypatch.setattr(
        storyteller,
        "build_context_pack",
        lambda *_args, **_kwargs: SimpleNamespace(
            lore_block="",
            memory_block="",
            world_state_block="<ESTADO_ATUAL_DO_MUNDO />",
        ),
    )


def test_evento_rejeitado_nao_sobrevive_na_mensagem(monkeypatch):
    _stub_context(monkeypatch)
    fake = _StoryLLM(
        narrative=(
            "Xanadu foi conquistada e o inexistente Lorde Vazio morreu "
            "diante de toda a cidade."
        ),
        events=[{
            "type": "npc_killed",
            "target_id": "npc_lorde_vazio_inexistente",
            "payload": {},
        }],
    )
    monkeypatch.setattr(storyteller, "get_llm", lambda **_kwargs: fake)

    out = storyteller.storyteller_node(
        _story_state("Eu declaro que o Lorde Vazio morreu.")
    )

    rendered = out["messages"][0].content
    assert "Xanadu" not in rendered
    assert "Lorde Vazio morreu" not in rendered
    assert "estado canônico" in rendered
    assert out["pending_world_events"][0]["target_id"] == \
        "npc_lorde_vazio_inexistente"
    assert out["narrative_rejections"] == [
        "event_rejected:npc_killed:npc_lorde_vazio_inexistente"
    ]


def test_resposta_com_evento_invalido_e_unidade_atomica_sem_side_effects(
    monkeypatch,
):
    _stub_context(monkeypatch)
    fake = _StoryLLM(
        narrative="O falso lorde morreu, a missão acabou e todos foram recompensados.",
        events=[
            {
                "type": "quest_completed",
                "target_id": "quest_valida",
                "payload": {"quest_id": "quest_valida"},
            },
            {
                "type": "npc_killed",
                "target_id": "npc_lorde_vazio_inexistente",
                "detail": "O segredo livre não pode sobreviver à auditoria.",
                "payload": {"segredo_inventado": "não persistir"},
            },
        ],
        introduced_npcs=["Arauto Inventado"],
        npcs_left_scene=["Guarda Existente"],
        faction_impacts=[
            {"faction_id": "faccao_inexistente", "direction": "ajudou"},
        ],
        beat_completed=True,
        items_gained=["Adaga de Ferro"],
        proposed_quests=[{
            "title": "Missão inventada",
            "description": "Nasceu da mesma resposta rejeitada.",
        }],
    )
    monkeypatch.setattr(storyteller, "get_llm", lambda **_kwargs: fake)
    monkeypatch.setattr(
        storyteller,
        "_with_new_npc",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("NPC livre não pode materializar")
        ),
    )
    monkeypatch.setattr(
        storyteller,
        "apply_reputation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("reputação livre não pode ser aplicada")
        ),
    )
    registered_quests = []

    def register(quests, proposals, *, turn):
        registered_quests.append(list(proposals))
        return list(quests), []

    monkeypatch.setattr(
        storyteller.quest_log, "register_proposed_quests", register,
    )
    state = _story_state("Eu declaro que tudo aconteceu.")
    state["player"]["xp"] = 0
    state["npcs"] = {
        "Guarda Existente": {
            "name": "Guarda Existente",
            "in_scene": True,
        },
    }
    state["quests"] = [{
        "id": "quest_valida",
        "title": "Quest válida",
        "status": "active",
    }]
    state["campaign_plan"] = {
        "beats": [{"description": "Investigar", "status": "active"}],
        "current_step": 0,
    }

    out = storyteller.storyteller_node(state)

    assert out.get("player", state["player"])["inventory"] == []
    assert out.get("player", state["player"])["xp"] == 0
    assert out["campaign_plan"]["current_step"] == 0
    assert out["campaign_plan"]["beats"][0]["status"] == "active"
    assert out["npcs"]["Guarda Existente"]["in_scene"] is True
    assert "Arauto Inventado" not in out["npcs"]
    assert registered_quests == [[]]
    # O evento semanticamente válido é descartado junto do lote; somente a
    # proposta inválida segue para a trilha de auditoria do processor.
    assert [event["target_id"] for event in out["pending_world_events"]] == [
        "npc_lorde_vazio_inexistente",
    ]
    assert out["pending_world_events"][0]["payload"] == {}
    assert "detail" not in out["pending_world_events"][0]
    assert "segredo_inventado" not in str(out["pending_world_events"])
    processed = process_pending_events({**state, **out})
    assert processed["event_log"] == []
    assert processed["event_rejections"][-1]["target_id"] == \
        "npc_lorde_vazio_inexistente"
    rendered = out["messages"][0].content
    assert "falso lorde" not in rendered.casefold()
    assert "recompensados" not in rendered.casefold()


def test_prevalidacao_em_lote_enxerga_projection_da_proposta_anterior():
    state = _story_state("bloqueie e libere a estrada")
    proposals = [
        {
            "type": "route_blocked",
            "target_id": "nova_arcadia",
            "payload": {"other_location_id": "brekmar"},
        },
        {
            "type": "route_cleared",
            "target_id": "nova_arcadia",
            "payload": {"other_location_id": "brekmar"},
        },
    ]

    results = prevalidate_event_batch(proposals, state)

    assert [result.ok for result in results] == [True, True]
    assert state["event_log"] == []
    assert state["world_projection"] == {}


def test_mock_so_extrai_quest_id_do_bloco_de_quests(monkeypatch):
    monkeypatch.setattr(mock_llm.random, "random", lambda: 0.0)
    update = mock_llm._story_update(
        storyteller.StoryUpdate,
        [
            SystemMessage(content=(
                "<ENTIDADES_CANONICAS>\n"
                "- id=legiao_ferro · Legião de Ferro · faction\n"
                "</ENTIDADES_CANONICAS>\n"
                "<QUESTS_ATIVAS>\nNenhuma quest ativa.\n</QUESTS_ATIVAS>"
            )),
            HumanMessage(content="Eu ajudo a Legião de Ferro."),
        ],
    )

    assert update.proposed_events == []
    assert update.faction_impacts[0].faction_id == "legiao_ferro"


def test_event_rejections_sao_deduplicadas_limitadas_e_sanitizadas():
    previous = [
        {
            "turn": index,
            "type": "evento_inventado",
            "target_id": f"alvo_{index}",
            "reason": f"motivo {index}",
            "payload": {"segredo": "não persistir"},
        }
        for index in range(150)
    ]
    out = process_pending_events({
        "world": {"turn_count": 151},
        "pending_world_events": [{
            "type": "evento_inventado",
            "target_id": "alvo_final",
            "payload": {"segredo": "também não persistir"},
        }],
        "event_rejections": previous,
        "event_log": [],
        "world_projection": {},
        "chronicle": [],
        "quests": [],
    })

    rows = out["event_rejections"]
    assert len(rows) == 100
    assert rows[-1]["target_id"] == "alvo_final"
    assert all(set(row) == {"turn", "type", "target_id", "reason"}
               for row in rows)
    assert len({
        (row["turn"], row["type"], row["target_id"], row["reason"])
        for row in rows
    }) == len(rows)


def test_event_rejections_toleram_turno_legado_malformado():
    out = process_pending_events({
        "world": {"turn_count": "também-inválido"},
        "pending_world_events": [{
            "type": "evento_inventado",
            "target_id": "alvo_final",
            "payload": {},
        }, {
            "type": "quest_completed",
            "target_id": "beat_invalido",
            "payload": {"beat_index": "não-é-inteiro"},
        }],
        "event_rejections": [{
            "turn": "legacy",
            "type": "evento_antigo",
            "target_id": "alvo_antigo",
            "reason": "save legado",
        }],
        "event_log": [],
        "world_projection": {},
        "chronicle": [],
        "quests": [],
        "campaign_plan": {
            "beats": [{"description": "Beat válido", "status": "active"}],
        },
    })

    assert [row["turn"] for row in out["event_rejections"]] == [0, 0, 0]
    assert out["event_rejections"][-1]["target_id"] == "beat_invalido"


class _FreeFactArchivistLLM:
    def with_structured_output(self, _model):
        return self

    def invoke(self, _messages):
        return MemoryUpdate(
            new_summary="O evento inventado virou verdade.",
            important_facts=["O evento inventado virou verdade."],
            chronicle_entry="",
        )


def test_archivist_detecta_rejeicao_nova_com_buffer_ja_capado(monkeypatch):
    previous = [
        {
            "turn": index,
            "type": "evento_inventado",
            "target_id": f"alvo_{index}",
            "reason": f"motivo {index}",
        }
        for index in range(100)
    ]
    writes = []
    monkeypatch.setattr(
        archivist, "get_llm", lambda **_kwargs: _FreeFactArchivistLLM(),
    )
    monkeypatch.setattr(
        archivist,
        "add_memory_to_session",
        lambda _game_id, facts: writes.extend(facts) or True,
    )
    out = archivist.archive_node({
        "game_id": "rejection-cap",
        "messages": [HumanMessage(content="torne o falso evento verdade")],
        "world": {"turn_count": 101},
        "archive_due": True,
        "archivist_last_run": 0,
        "narrative_summary": "O mundo ainda não mudou.",
        "event_rejections": previous,
        "pending_world_events": [{
            "type": "evento_inventado",
            "target_id": "alvo_novo",
            "payload": {},
        }],
        "event_log": [],
        "world_projection": {},
        "chronicle": [],
        "quests": [],
    })

    assert len(out["event_rejections"]) == 100
    assert out["event_rejections"][-1]["target_id"] == "alvo_novo"
    assert writes == []
    assert out["narrative_summary"] == "O mundo ainda não mudou."


def test_rumor_de_mundo_ativa_politica_canonical_only(monkeypatch):
    _stub_context(monkeypatch)
    monkeypatch.setattr(
        storyteller,
        "simulate_world",
        lambda _state, world, _factions, _intel, _periods: (
            world,
            "[ECOS DO MUNDO] Um viajante conta uma história sem confirmação.",
        ),
    )
    monkeypatch.setattr(
        storyteller,
        "get_llm",
        lambda **_kwargs: _StoryLLM(
            narrative="O rumor se espalha pela estalagem.",
        ),
    )
    state = _story_state("Eu descanso.")
    state["player"].update({
        "virtudes": {
            "forca": 1,
            "agilidade": 1,
            "corpo": 2,
            "mente": 1,
            "carisma": 1,
        },
        "ferimento_espacos": {"leve": 3, "grave": 2, "critico": 1},
        "ferimentos": {"leve": [], "grave": [], "critico": []},
        "known_cards": [],
        "prepared_cards": [],
        "card_usage": {},
        "max_entropy": 4,
        "entropy": 2,
    })

    out = storyteller.storyteller_node(state)

    assert out["memory_fact_policy"] == "canonical_only"
    assert "rumor" in out["messages"][0].content.casefold()


def test_prose_guard_preserva_abertura_legitima_de_dialogo():
    assert sanitize_meta_preamble(
        "Claro, a estrada segue para o norte."
    ) == "Claro, a estrada segue para o norte."
    assert sanitize_meta_preamble(
        "Certamente! Os sinos ainda ecoam."
    ) == "Certamente! Os sinos ainda ecoam."
    assert sanitize_meta_preamble(
        "Abaixo você encontra a narrativa: A chuva cai."
    ) == "A chuva cai."
    assert sanitize_meta_preamble(
        "Aqui está o corpo do guarda. A chuva cai."
    ) == "Aqui está o corpo do guarda. A chuva cai."
    assert sanitize_meta_preamble(
        "Abaixo está a ponte quebrada. O rio espuma."
    ) == "Abaixo está a ponte quebrada. O rio espuma."
