"""SPEC-300 Etapa 7 — romance em estágios (Python decide), fade-to-black e interruptor de loja."""

import pytest
from spec300_helpers import BRUNNA, BRUNNA_ID, make_state

from services import companion_prompt as cp
from services import companion_soul as cs
from services import companion_tags as ctags


def _soul(**kw):
    base = {"approval": 70, "romance": "none", "romance_rests": 0, "personal_quest": "none"}
    base.update(kw)
    return base


def step(soul, *, traits=(), intent=False, rest=False, day=3, adult=True):
    return cs.step_romance(
        soul, traits=list(traits), intent=intent, rest=rest, day=day, adult=adult
    )


def test_regex_intencao_romantica():
    assert ctags.detect_romance_intent("Beijo Brunna")
    assert ctags.detect_romance_intent("Tento cortejar Brunna")
    assert not ctags.detect_romance_intent("Não quero flertar agora")
    assert not ctags.detect_romance_intent("Afio minha espada")


def test_interesse_exige_65_e_intencao():
    assert step(_soul(approval=64), intent=True)["romance"] == "none"
    assert step(_soul(approval=65), intent=False)["romance"] == "none"
    assert step(_soul(approval=65), intent=True)["romance"] == "interesse"


def test_vinculo_exige_75_e_dois_descansos():
    soul = _soul(approval=80, romance="interesse")
    soul = step(soul, rest=True)
    assert soul["romance"] == "interesse" and soul["romance_rests"] == 1
    soul = step(soul, rest=True)
    assert soul["romance"] == "vinculo"
    baixo = _soul(approval=74, romance="interesse", romance_rests=5)
    assert step(baixo, rest=True)["romance"] == "interesse"


def test_compromisso_exige_missao_e_85():
    assert step(_soul(approval=90, romance="vinculo"), rest=True)["romance"] == "vinculo"
    sem_85 = _soul(approval=84, romance="vinculo", personal_quest="completed")
    assert step(sem_85, rest=True)["romance"] == "vinculo"
    ok = _soul(approval=85, romance="vinculo", personal_quest="completed")
    assert step(ok, rest=True)["romance"] == "compromisso"


def test_rompido_abaixo_de_40_e_reabre_em_5_dias():
    broken = step(_soul(approval=39, romance="vinculo"), day=3)
    assert broken["romance"] == "rompido" and broken["romance_reopen_day"] == 8
    assert step({**broken, "approval": 90}, day=7)["romance"] == "rompido"
    assert step({**broken, "approval": 90}, day=8)["romance"] == "none"


def test_blocker_luto_ate_missao_pessoal():
    assert step(_soul(), traits=["luto_recente"], intent=True)["romance"] == "none"
    liberado = _soul(personal_quest="completed")
    assert step(liberado, traits=["luto_recente"], intent=True)["romance"] == "interesse"


def test_so_adultos():
    assert step(_soul(), intent=True, adult=False)["romance"] == "none"


def test_flag_romance_off_recusa_e_sem_regra(monkeypatch):
    monkeypatch.setenv("RPG_COMPANION_ROMANCE", "off")
    assert step(_soul(), intent=True)["romance"] == "none"
    state = make_state(approval=80, text="Flerto com Brunna sob as estrelas")
    state["companion_souls"][BRUNNA_ID]["romance"] = "vinculo"
    block, _ = cp.companion_prompt_block(state, "npc", target=BRUNNA)
    assert "recuse com delicadeza" in block and "REGRA FIXA" not in block
    story, _ = cp.companion_prompt_block(make_state(text="Descansamos."), "story")
    assert "REGRA FIXA" not in story


def test_regra_fade_to_black_no_bloco(monkeypatch):
    monkeypatch.delenv("RPG_COMPANION_ROMANCE", raising=False)
    state = make_state(approval=80, text="Descansamos juntos.")
    assert "REGRA FIXA" not in cp.companion_prompt_block(state, "story")[0]  # sem romance ativo
    state["companion_souls"][BRUNNA_ID]["romance"] = "interesse"
    for purpose in ("story", "npc"):
        block, _ = cp.companion_prompt_block(state, purpose, target=BRUNNA)
        assert "termina em corte antes de qualquer contato físico explícito" in block
        assert "nada sexual" in block


@pytest.mark.parametrize("approval,expect", [(70, "interesse"), (60, "none")])
def test_apply_turn_avanca_com_intencao_narrada(approval, expect):
    state = make_state(approval=approval, ack=[f"intent:{BRUNNA_ID}:romance"])
    out = cs.apply_turn(state)
    soul = out["companion_souls"][BRUNNA_ID]
    assert soul["romance"] == expect
    if expect == "interesse":
        assert any(r["tag"] == "estagio" for r in soul["reactions"])
        assert out["companion_voice_ack"] is None


def test_apply_turn_nao_romanceia_menor_de_idade():
    state = make_state(approval=80, ack=[f"intent:{BRUNNA_ID}:romance"])
    state["npcs"][BRUNNA]["age"] = 16
    assert cs.apply_turn(state)["companion_souls"][BRUNNA_ID]["romance"] == "none"


def test_vinculo_vira_topico_de_acampamento():
    state = make_state(approval=80, text="Descansamos juntos.")
    soul = state["companion_souls"][BRUNNA_ID]
    soul.update(
        romance="vinculo", reactions=[{"id": "9:estagio", "tag": "estagio", "delta": 0, "turn": 9}]
    )
    block, ack = cp.companion_prompt_block(state, "story")
    assert f"topic:{BRUNNA_ID}:romance" in ack and "vínculo" in block
    assert "termina em corte antes" in block
