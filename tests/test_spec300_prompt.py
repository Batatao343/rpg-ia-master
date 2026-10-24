"""SPEC-300 Etapa 4 — bloco <COMPANHEIROS>, fala espontânea e zero chamadas LLM extras."""

import re

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from spec300_helpers import BRUNNA, BRUNNA_ID, comp, make_state, npc

import agents.npc as npc_mod
import agents.storyteller as stt
from services import companion_prompt as cp
from services import companion_soul as cs

BRUNO_ID = "npc_bruno"


def _add_companion(state, cid, name, approval=50, values=None):
    c = comp(id=cid, origin_npc=cid, name=name)
    state["party"].append(c)
    state["npcs"][name] = npc(id=cid, name=name)
    soul = cs.ensure_soul(state, c)
    soul["approval"] = approval
    if values is not None:
        soul["values"] = values
    state["companion_souls"][cid] = soul
    return soul


def _react(state, cid, tag, delta, turn=9):
    soul = state["companion_souls"][cid]
    soul["reactions"] = [
        *soul["reactions"],
        {"id": f"{turn}:{tag}", "tag": tag, "delta": delta, "turn": turn},
    ]


def test_sem_companheiro_bloco_vazio():
    assert cp.companion_prompt_block(make_state(party=False), "story") == ("", [])
    assert cp.companion_prompt_block(make_state(party=False), "npc", target=BRUNNA) == ("", [])


def test_flag_off_bloco_vazio(monkeypatch):
    monkeypatch.setenv("RPG_COMPANION_SOUL", "shadow")
    assert cp.companion_prompt_block(make_state(), "story") == ("", [])


def test_prioridade_despedida_aviso_reacao_descanso():
    state = make_state(text="Descanso aqui esta noite.")
    soul = state["companion_souls"][BRUNNA_ID]
    # 5. silêncio (sem descanso) / 4. descanso
    quiet = make_state(text="Olho a paisagem.")
    assert "calados" in cp.companion_prompt_block(quiet, "story")[0]
    block, ack = cp.companion_prompt_block(state, "story")
    assert "Acampamento" in block and ack == [f"topic:{BRUNNA_ID}:values"]
    # 3. reação forte vence o descanso
    _react(state, BRUNNA_ID, "ameacou", -6)
    block, ack = cp.companion_prompt_block(state, "story")
    assert "ameaçou alguém" in block and "não gostou disso" in block
    assert ack == [f"r:{BRUNNA_ID}:9:ameacou"]
    # 2. aviso vence a reação
    soul["warned_turn"] = 8
    _react(state, BRUNNA_ID, "aviso", 0)
    block, ack = cp.companion_prompt_block(state, "story")
    assert "perdendo a paciência" in block and ack == [f"r:{BRUNNA_ID}:9:aviso"]
    # 1. despedida vence tudo
    soul["departure_pending"] = "leave"
    soul["departure_turn"] = 9
    _react(state, BRUNNA_ID, "despedida", 0)
    block, ack = cp.companion_prompt_block(state, "story")
    assert "se despede" in block and ack == [f"r:{BRUNNA_ID}:9:despedida"]


def test_reacao_fraca_nao_fala():
    state = make_state()
    _react(state, BRUNNA_ID, "quest_falhou", -3)
    assert "calados" in cp.companion_prompt_block(state, "story")[0]


def test_um_companheiro_por_reacao_empate_seeded():
    state = make_state()
    _add_companion(state, BRUNO_ID, "Bruno Pedra")
    _react(state, BRUNNA_ID, "ameacou", -6)
    _react(state, BRUNO_ID, "ameacou", -6)
    first = cp.companion_prompt_block(state, "story")
    assert first == cp.companion_prompt_block(state, "story")  # determinístico
    block, ack = first
    assert len(ack) == 1
    assert block.count("FAÇA:") == 1
    seen = set()
    for turn in range(10, 40):  # o empate cai nos dois lados conforme o turno
        s = {**state, "world": {**state["world"], "turn_count": turn}}
        for cid in ("npc_mv_brunna_ponte_alta", BRUNO_ID):
            for r in s["companion_souls"][cid]["reactions"]:
                r["turn"] = turn - 1
        seen.add(cp.companion_prompt_block(s, "story")[1][0].split(":")[1])
    assert seen == {BRUNNA_ID, BRUNO_ID}


def test_descanso_ate_dois_companheiros():
    state = make_state(text="Descansamos junto à fogueira.")
    _add_companion(state, BRUNO_ID, "Bruno Pedra")
    _add_companion(state, "npc_cida", "Cida Vale")
    block, ack = cp.companion_prompt_block(state, "story")
    assert block.count("Acampamento:") == 2 and len(ack) == 2


def test_orcamento_600_e_1200():
    state = make_state(text="Descansamos junto à fogueira.")
    _add_companion(state, BRUNO_ID, "Bruno Pedra")
    _add_companion(state, "npc_cida", "Cida Vale")
    for soul in state["companion_souls"].values():
        soul["romance"] = "vinculo"
        soul["reactions"] = [{"id": "9:estagio", "tag": "estagio", "delta": 0, "turn": 9}]
    block, _ = cp.companion_prompt_block(state, "story")
    assert len(block) <= cp.BLOCK_CAP_TOTAL
    assert "corte antes de qualquer contato físico explícito" in block  # nunca cortada
    solo = make_state()
    solo["companion_souls"][BRUNNA_ID]["romance"] = "compromisso"
    long_role = "x" * 900
    solo["npcs"][BRUNNA]["role"] = long_role
    block, _ = cp.companion_prompt_block(solo, "story")
    assert len(block) <= cp.BLOCK_CAP_TOTAL


def test_bloco_sem_numero_nem_nome_de_traco_oculto():
    state = make_state(traits=["ganancioso", "luto_recente"], text="Descanso aqui.")
    _react(state, BRUNNA_ID, "ameacou", -6)
    for purpose in ("story", "npc"):
        block, _ = cp.companion_prompt_block(state, purpose, target=BRUNNA)
        assert block
        assert not re.search(r"\d", block), block
        low = block.lower()
        for hidden in ("ganancioso", "luto_recente", "luto recente", "hidden"):
            assert hidden not in low


def test_npc_actor_recebe_bloco_do_alvo():
    state = make_state(approval=70)
    _react(state, BRUNNA_ID, "ameacou", -6)
    block, ack = cp.companion_prompt_block(state, "npc", target=BRUNNA_ID)
    assert "Brunna Ponte-Alta" in block and "amistoso" in block
    assert "ameaçou alguém" in block and ack == [f"r:{BRUNNA_ID}:9:ameacou"]
    assert cp.companion_prompt_block(state, "npc", target="Outro Alguém") == ("", [])


def test_intencao_romantica_gate_aberto_x_fechado(monkeypatch):
    state = make_state(approval=70, text="Flerto com Brunna sob as estrelas")
    block, ack = cp.companion_prompt_block(state, "npc", target=BRUNNA)
    assert "corresponder com delicadeza" in block and f"intent:{BRUNNA_ID}:romance" in ack
    closed = make_state(approval=50, text="Flerto com Brunna sob as estrelas")
    block, _ = cp.companion_prompt_block(closed, "npc", target=BRUNNA)
    assert "recuse com delicadeza" in block
    monkeypatch.setenv("RPG_COMPANION_ROMANCE", "off")
    block, _ = cp.companion_prompt_block(state, "npc", target=BRUNNA)
    assert "recuse com delicadeza" in block and "corte antes" not in block


def test_reacao_expira_em_3_turnos():
    state = make_state()
    _react(state, BRUNNA_ID, "ameacou", -6, turn=5)  # idade 5 > 3
    assert "calados" in cp.companion_prompt_block(state, "story")[0]
    out = cs.apply_turn(state)
    assert out["companion_souls"][BRUNNA_ID]["reactions"] == []


# --- integração com os nós (spy no LLM) ---------------------------------------- #
class _Counting:
    def __init__(self, result=None):
        self.calls = 0
        self.prompts: list[str] = []
        self.result = result

    def with_structured_output(self, *_a, **_k):
        return self

    def invoke(self, msgs, *_a, **_k):
        self.calls += 1
        self.prompts.append("\n".join(str(getattr(m, "content", m)) for m in msgs))
        return self.result if self.result is not None else AIMessage(content="falha")


def _story_state(**kw):
    state = make_state(**kw)
    state.update(
        narrative_summary="",
        archivist_last_run=0,
        faction_intel={},
        campaign_plan={},
    )
    state["player"].update(class_name="Guerreiro", level=1, vitalidade=10, max_vitalidade=10)
    state["world"].update(
        current_location="Montanhas Afiadas",
        time_of_day="Manhã",
        danger_level=2,
        quest_plan=[],
    )
    return state


def test_zero_chamadas_llm_extras(monkeypatch):
    counts = []
    for with_party in (False, True):
        spy = _Counting()
        monkeypatch.setattr(stt, "get_llm", lambda *a, _s=spy, **k: _s)
        state = _story_state(party=with_party)
        if with_party:
            _react(state, BRUNNA_ID, "ameacou", -6)
        stt.storyteller_node(state)
        counts.append(spy.calls)
    assert counts[0] == counts[1] == 1


def test_storyteller_injeta_bloco_e_ack_so_no_caminho_feliz(monkeypatch):
    state = _story_state()
    _react(state, BRUNNA_ID, "ameacou", -6)
    sad = _Counting()  # FallbackLLM-like: devolve AIMessage, não StoryUpdate
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: sad)
    out = stt.storyteller_node(state)
    assert "<COMPANHEIROS>" in sad.prompts[0]
    assert "companion_voice_ack" not in out  # reação continua pendente
    happy = _Counting(stt.StoryUpdate(narrative="Brunna franze o cenho e resmunga."))
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: happy)
    out = stt.storyteller_node(state)
    assert out["companion_voice_ack"] == [f"r:{BRUNNA_ID}:9:ameacou"]
    # o writer único consome só o que foi narrado
    merged = {**state, **out}
    assert cs.apply_turn(merged)["companion_souls"][BRUNNA_ID]["reactions"] == []
    assert cs.apply_turn(state)["companion_souls"][BRUNNA_ID]["reactions"] != []


def test_npc_actor_injeta_bloco_do_companheiro(monkeypatch):
    seen = {}

    class _NPCLLM(_Counting):
        def invoke(self, msgs, *a, **k):
            seen["prompt"] = str(msgs[0].content)
            return npc_mod.NPCResponse(
                dialogue="Hm.", action_description="", memory_update="", relationship_change=0
            )

    monkeypatch.setattr(npc_mod, "get_llm", lambda *a, **k: _NPCLLM())
    state = _story_state(text="Brunna, o que você acha do que eu fiz?")
    state["active_npc_name"] = BRUNNA
    state["messages"] = [HumanMessage(content="Brunna, o que você acha do que eu fiz?")]
    _react(state, BRUNNA_ID, "ameacou", -6)
    out = npc_mod.npc_actor_node(state)
    assert "<COMPANHEIROS>" in seen["prompt"] and "ameaçou alguém" in seen["prompt"]
    assert out["companion_voice_ack"] == [f"r:{BRUNNA_ID}:9:ameacou"]


@pytest.mark.parametrize("flag", ["off", "shadow"])
def test_flag_nao_injeta_bloco(monkeypatch, flag):
    monkeypatch.setenv("RPG_COMPANION_SOUL", flag)
    spy = _Counting()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    stt.storyteller_node(_story_state())
    assert "<COMPANHEIROS>" not in spy.prompts[0]
