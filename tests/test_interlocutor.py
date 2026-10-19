"""SPEC-202 Etapa 1 — política de interlocutor (Python puro, zero LLM extra)."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

import agents.router as router_mod
from agents.router import RouterDecision, RouteType, dm_router_node
from services import interlocutor as itl


class _CountingLLM:
    """CLASSIFY fake: devolve uma decisão fixa e conta invokes."""

    def __init__(self, route=RouteType.STORY, target=None):
        self.calls = 0
        self.decision = RouterDecision(
            route=route, loot_context=None, target=target, reasoning="fake", confidence=0.9
        )

    def with_structured_output(self, *_a, **_k):
        return self

    def invoke(self, _messages):
        self.calls += 1
        return self.decision


def _state(text: str = "", *, loc_id: str = "brekmar", turn: int = 10, **extra) -> dict:
    st = {
        "game_id": "g-spec202",
        "messages": [HumanMessage(content=text)] if text else [],
        "world": {"current_location": "Brekmar", "current_location_id": loc_id, "turn_count": turn},
        "npcs": {
            "Brunna Ponte-Alta": {
                "name": "Brunna Ponte-Alta",
                "role": "Barqueira",
                "in_scene": True,
                "home_location_id": loc_id,
            },
            "Velha Magda": {
                "name": "Velha Magda",
                "role": "Vidente",
                "in_scene": True,
                "home_location_id": loc_id,
            },
            "Gorim": {
                "name": "Gorim",
                "role": "Ferreiro",
                "in_scene": False,
                "home_location_id": "skallgard",
            },
        },
        "party": [],
        "combat": None,
    }
    st.update(extra)
    return st


def _only(state: dict, name: str) -> dict:
    """Deixa só `name` em cena (os demais saem)."""
    npcs = {
        k: {**v, "in_scene": (k == name) and v.get("in_scene", True)}
        for k, v in state["npcs"].items()
    }
    return {**state, "npcs": npcs}


def _route(monkeypatch, state, route=RouteType.STORY, target=None):
    llm = _CountingLLM(route, target)
    monkeypatch.setattr(router_mod, "get_llm", lambda *a, **k: llm)
    return dm_router_node(state), llm


# --- R2: meta-pergunta ao narrador -----------------------------------------


def test_meta_narrador_sobre_npc_vai_story(monkeypatch):
    out, llm = _route(
        monkeypatch,
        _state("Pergunto ao narrador o que a Velha Magda sente"),
        route=RouteType.NPC,
        target="Velha Magda",
    )
    assert llm.calls == 0
    assert out["next"] == RouteType.STORY.value
    assert out["active_npc_name"] is None
    assert out["interlocutor_reason"] == "meta_to_narrator"
    assert out["mediated_subject_id"] == "npc_velha_magda"


@pytest.mark.parametrize(
    "text",
    [
        "Narrador, a Brunna parece mentir?",
        "((fora do jogo: a Brunna é confiável?))",
        "OOC: quanto tempo falta pro anoitecer?",
    ],
)
def test_meta_marcadores(monkeypatch, text):
    out, llm = _route(monkeypatch, _state(text), route=RouteType.NPC, target="Brunna")
    assert llm.calls == 0
    assert out["next"] == RouteType.STORY.value
    assert out["interlocutor_reason"] == "meta_to_narrator"


def test_sobre_nome_sem_verbo_de_fala_e_meta(monkeypatch):
    out, llm = _route(
        monkeypatch, _state("O que eu sei sobre a Brunna?"), route=RouteType.NPC, target="Brunna"
    )
    assert llm.calls == 0
    assert out["next"] == RouteType.STORY.value
    assert out["mediated_subject_id"] == "npc_mv_brunna_ponte_alta"


def test_narrador_como_personagem_nao_e_meta():
    st = _state()
    assert itl.pre_classify(st, "O narrador da taverna começa a cantar") is None


def test_mestre_com_nome_ou_papel_e_personagem_nao_meta(monkeypatch):
    """Astra: "mestre Orlan"/"mestre ferreiro" são personagens, não o mestre do jogo."""
    st = _state()
    st["npcs"]["Mestre Orlan"] = {
        "name": "Mestre Orlan",
        "role": "Ferreiro",
        "in_scene": True,
        "home_location_id": "brekmar",
    }
    for text in (
        "Pergunto ao mestre Orlan sobre a espada",
        "Falo com o mestre da guilda",
        "Falo com o mestre ferreiro",
    ):
        assert itl.pre_classify(st, text) is None, text
    out, llm = _route(
        monkeypatch,
        {**st, "messages": [HumanMessage(content="Pergunto ao mestre Orlan sobre a espada")]},
        RouteType.NPC,
        "Mestre Orlan",
    )
    assert out["next"] == RouteType.NPC.value and out["active_npc_name"] == "Mestre Orlan"
    assert llm.calls == 1
    for text in (
        "Pergunto ao mestre se a Brunna mente",
        "Falo com o mestre",
        "Pergunto ao mestre o que a Magda sente",
    ):
        res = itl.pre_classify(st, text)
        assert res is not None and res.reason == "meta_to_narrator", text


# --- R3: descrição de cena -------------------------------------------------


@pytest.mark.parametrize("text", ["Descreva a taverna", "O que eu vejo?", "Quem está aqui?"])
def test_descricao_de_cena_nunca_npc(monkeypatch, text):
    out, llm = _route(monkeypatch, _state(text), route=RouteType.NPC, target="Brunna")
    assert llm.calls == 0
    assert out["next"] == RouteType.STORY.value
    assert out["active_npc_name"] is None
    assert out["interlocutor_reason"] == "scene_description"


def test_descricao_override_pos_classify():
    res = itl.post_classify(_state(), "descrevo o ambiente ao redor", "npc_actor", "Brunna")
    assert res.route == "storyteller" and res.speaker_kind == "narrator"


# --- R4: fala direta -------------------------------------------------------


def test_vocativo_npc_presente(monkeypatch):
    out, llm = _route(
        monkeypatch, _state("Brunna, você viu o barco?"), route=RouteType.NPC, target="Brunna"
    )
    assert llm.calls == 1
    assert out["next"] == RouteType.NPC.value
    assert out["active_npc_name"] == "Brunna Ponte-Alta"
    assert out["interlocutor_reason"] == "direct_address"


def test_vocativo_promove_story_do_classify(monkeypatch):
    out, _ = _route(monkeypatch, _state("Magda: o que as cartas dizem?"), route=RouteType.STORY)
    assert out["next"] == RouteType.NPC.value
    assert out["active_npc_name"] == "Velha Magda"


def test_aspas_com_alias(monkeypatch):
    out, _ = _route(
        monkeypatch,
        _state('Olho para Magda e digo "a maré mudou"'),
        route=RouteType.NPC,
        target=None,
    )
    assert out["active_npc_name"] == "Velha Magda"
    assert out["interlocutor_reason"] in {"quoted_vocative", "direct_address"}


def test_alias_curto_nao_casa():
    st = {
        **_state(),
        "npcs": {"Bo": {"name": "Bo", "in_scene": True, "home_location_id": "brekmar"}},
    }
    assert itl.addressed_in_scene(st, "Bo, venha cá") is None
    assert itl.addressed_in_scene(st, "Pergunto ao bote se afunda") is None


def test_pergunto_a_nome_presente_vai_npc(monkeypatch):
    out, _ = _route(monkeypatch, _state("Pergunto à Brunna sobre o barco"), route=RouteType.STORY)
    assert out["next"] == RouteType.NPC.value
    assert out["active_npc_name"] == "Brunna Ponte-Alta"


def test_texto_transcrito_com_pausas(monkeypatch):
    out, _ = _route(
        monkeypatch, _state("é... Brunna... você viu o barco?"), route=RouteType.NPC, target=None
    )
    assert out["active_npc_name"] == "Brunna Ponte-Alta"
    assert out["interlocutor_reason"] == "direct_address"


# --- R5: alvo cru nunca vira identidade ------------------------------------


def test_nome_alucinado_nao_vira_active_npc(monkeypatch):
    out, _ = _route(monkeypatch, _state("Falo com Halveth"), route=RouteType.NPC, target="Halveth")
    assert out["next"] == RouteType.STORY.value
    assert out["active_npc_name"] is None
    assert out["interlocutor_reason"] == "npc_unknown_absent"
    assert out["npc_fallback_hint"]


def test_npc_conhecido_fora_de_cena_reason_absent_known(monkeypatch):
    out, _ = _route(monkeypatch, _state("Falo com Gorim"), route=RouteType.NPC, target="Gorim")
    assert out["next"] == RouteType.NPC.value
    assert out["active_npc_name"] == "Gorim"
    assert out["interlocutor_reason"] == "npc_absent_known"


def test_npc_ausente_nunca_fala_em_primeira_pessoa(monkeypatch):
    import agents.npc as npc_mod

    def _boom(*_a, **_k):
        raise AssertionError("generate_new_npc não pode ser chamado")

    monkeypatch.setattr(npc_mod, "generate_new_npc", _boom)
    st = _state("Falo com Halveth", active_npc_name="Halveth")
    out = npc_mod.npc_actor_node(st)
    assert out.get("next") == "storyteller"
    assert out.get("npc_fallback_hint")
    assert not any(
        str(getattr(m, "content", "")).startswith("**Halveth") for m in out.get("messages") or []
    )


# --- R6: papel genérico ----------------------------------------------------


def test_papel_generico_em_assentamento_spawn(monkeypatch):
    st = {**_state("Falo com o taverneiro"), "npcs": {}}
    out, _ = _route(monkeypatch, st, route=RouteType.NPC, target="taverneiro")
    assert out["next"] == RouteType.NPC.value
    assert out["interlocutor_reason"] == "generic_role_spawn"
    assert out["active_npc_name"] == "taverneiro"


def test_papel_generico_em_ermo_nao_spawn(monkeypatch):
    st = {**_state("Falo com o taverneiro", loc_id="deserto_zhur"), "npcs": {}}
    out, _ = _route(monkeypatch, st, route=RouteType.NPC, target="taverneiro")
    # Ninguém em cena: rota NPC SEM alvo (caminho SPEC-041) → o ator delega ao
    # narrador; nenhum NPC é gerado.
    assert out["interlocutor_reason"] == "npc_unknown_absent"
    assert out["active_npc_name"] is None
    import agents.npc as npc_mod

    monkeypatch.setattr(
        npc_mod, "generate_new_npc", lambda *a, **k: (_ for _ in ()).throw(AssertionError("gerou"))
    )
    actor = npc_mod.npc_actor_node({**st, **out})
    assert actor.get("next") == "storyteller"


def test_papel_generico_casa_npc_em_cena_pelo_papel(monkeypatch):
    out, _ = _route(
        monkeypatch, _state("Chamo a barqueira"), route=RouteType.NPC, target="a barqueira"
    )
    assert out["active_npc_name"] == "Brunna Ponte-Alta"


# --- R7/R8: múltiplos NPCs e pronomes --------------------------------------


def _last(key: str, name: str, turn: int) -> dict:
    return {
        "kind": "npc",
        "id": "x",
        "name": name,
        "reason": "direct_address",
        "turn": turn,
        "state_key": key,
    }


def test_multiplos_sem_nome_continuidade(monkeypatch):
    st = _state("E o que mais?", last_speaker=_last("Brunna Ponte-Alta", "Brunna Ponte-Alta", 9))
    out, _ = _route(monkeypatch, st, route=RouteType.NPC, target=None)
    assert out["active_npc_name"] == "Brunna Ponte-Alta"
    assert out["interlocutor_reason"] == "continuity_last_speaker"


def test_multiplos_sem_nome_sem_continuidade_media(monkeypatch):
    st = _state("E o que mais?", last_speaker=_last("Brunna Ponte-Alta", "Brunna Ponte-Alta", 5))
    out, _ = _route(monkeypatch, st, route=RouteType.NPC, target=None)
    assert out["next"] == RouteType.STORY.value
    assert out["interlocutor_reason"] == "ambiguous_multi_mediated"
    assert out["active_npc_name"] is None


def test_pronome_resolve_last_speaker(monkeypatch):
    st = _state(
        "E você?",
        last_speaker={
            "kind": "narrator",
            "id": "narrator",
            "name": "Narrador",
            "reason": "x",
            "turn": 9,
            "last_npc": _last("Velha Magda", "Velha Magda", 8),
        },
    )
    out, _ = _route(monkeypatch, st, route=RouteType.STORY)
    assert out["next"] == RouteType.NPC.value
    assert out["active_npc_name"] == "Velha Magda"


def test_pronome_sem_candidato_media(monkeypatch):
    out, _ = _route(
        monkeypatch, _state("Pergunto a ela o que houve"), route=RouteType.NPC, target="ela"
    )
    assert out["next"] == RouteType.STORY.value
    assert out["interlocutor_reason"] == "ambiguous_multi_mediated"


def test_npc_unico_sem_nome(monkeypatch):
    out, _ = _route(
        monkeypatch, _only(_state("Oi, tudo bem?"), "Velha Magda"), route=RouteType.NPC, target=None
    )
    assert out["active_npc_name"] == "Velha Magda"
    assert out["interlocutor_reason"] == "single_in_scene"


# --- R9/R15: speaker canônico ----------------------------------------------


def test_speaker_name_canonico_com_alias(monkeypatch):
    import agents.npc as npc_mod

    out, _ = _route(
        monkeypatch, _state("Brunna, você viu o barco?"), route=RouteType.NPC, target="brunna"
    )
    st = {**_state("Brunna, você viu o barco?"), **out}
    actor = npc_mod.npc_actor_node(st)
    assert str(actor["messages"][0].content).startswith("**Brunna Ponte-Alta:**")
    final = {**st, **actor}
    speaker = itl.speaker_for_turn(final)
    assert speaker["kind"] == "npc"
    assert speaker["name"] == "Brunna Ponte-Alta"
    assert speaker["id"] == "npc_mv_brunna_ponte_alta"


def test_speaker_meta_e_narrador():
    st = {**_state(), "next": "storyteller", "interlocutor_reason": "meta_to_narrator"}
    sp = itl.speaker_for_turn(st)
    assert itl.public_speaker(sp) == {
        "kind": "narrator",
        "id": "narrator",
        "name": "Narrador",
        "reason": "meta_to_narrator",
    }
