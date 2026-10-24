"""SPEC-300 Etapa 6 — missão pessoal (origem, revelação, conclusão e falha pelo motor)."""

from spec300_helpers import BRUNNA_ID, comp, make_state, npc

from services import companion_prompt as cp
from services import companion_soul as cs
from services import companion_tags as ctags
from services import quest_log

QID = f"pq_{BRUNNA_ID}"


def _revealed(*, ready_turn=None, location="montanhas_afiadas", approval=60, **kw):
    state = make_state(approval=approval, location=location, **kw)
    quest = cs.build_personal_quest(state, state["party"][0], turn=5)
    state["quests"] = [quest]
    soul = state["companion_souls"][BRUNNA_ID]
    soul["personal_quest"] = "revealed"
    if ready_turn is not None:
        soul.update(personal_quest="ready", quest_ready_turn=ready_turn)
        quest["completion_ready"] = True
    return state


def test_brunna_usa_gancho_mundo_vivo():
    state = make_state()
    spec = cs.personal_quest_spec(state, state["party"][0])
    assert spec["source"] == "hook"
    assert spec["description"].startswith("Firmar uma ponte")
    assert spec["location_id"] == "montanhas_afiadas"


def _other(traits, home="skallgard"):
    state = make_state(party=False)
    row = npc(traits=traits, id="npc_zz", name="Zed", home_location_id=home)
    state["npcs"] = {"Zed": row}
    c = comp(id="npc_zz", origin_npc="npc_zz", name="Zed")
    return state, c


def test_template_por_traco():
    state, c = _other(["tagarela", "luto_recente"])
    spec = cs.personal_quest_spec(state, c)
    assert spec["source"] == "trait:luto_recente" and "Zed" in spec["description"]
    assert spec["title"] == "Uma despedida pendente"


def test_template_generico_por_regiao_e_fallback():
    state, c = _other(["tagarela"], home="skallgard")
    assert cs.personal_quest_spec(state, c)["source"] == "region"
    state, c = _other(["tagarela"], home="")
    spec = cs.personal_quest_spec(state, c)
    assert spec["source"] == "fallback" and spec["location_id"] == ""


def test_revela_so_no_descanso_com_aprovacao_55():
    def run(**kw):
        state = make_state(text="Descanso aqui esta noite.", ack=[f"topic:{BRUNNA_ID}:quest"], **kw)
        state["companion_souls"][BRUNNA_ID]["rests_together"] = 1
        return cs.apply_turn(state)

    out = run(approval=60)
    quest = out["quests"][0]
    assert quest["id"] == QID and quest["personal_of"] == BRUNNA_ID and quest["status"] == "active"
    assert out["companion_souls"][BRUNNA_ID]["personal_quest"] == "revealed"
    assert "quests" not in run(approval=50)  # abaixo de 55
    sem_ack = make_state(text="Descanso aqui esta noite.", approval=60)
    sem_ack["companion_souls"][BRUNNA_ID]["rests_together"] = 1
    assert "quests" not in cs.apply_turn(sem_ack)
    sem_descanso = make_state(text="Sigo andando.", approval=60, ack=[f"topic:{BRUNNA_ID}:quest"])
    sem_descanso["companion_souls"][BRUNNA_ID]["rests_together"] = 1
    assert "quests" not in cs.apply_turn(sem_descanso)


def test_bloco_so_oferece_a_missao_depois_do_primeiro_descanso():
    state = make_state(text="Descanso aqui esta noite.", approval=60)
    block, ack = cp.companion_prompt_block(state, "story")
    assert ack == [f"topic:{BRUNNA_ID}:values"] and "assunto pessoal" not in block
    state["companion_souls"][BRUNNA_ID]["rests_together"] = 1
    block, ack = cp.companion_prompt_block(state, "story")
    assert ack == [f"topic:{BRUNNA_ID}:quest"] and "Firmar uma ponte" in block


def test_uma_missao_por_companheiro():
    state = make_state(
        text="Descanso aqui esta noite.", approval=60, ack=[f"topic:{BRUNNA_ID}:quest"]
    )
    state["companion_souls"][BRUNNA_ID]["rests_together"] = 1
    first = cs.apply_turn(state)
    again = cs.apply_turn({**state, **first, "companion_voice_ack": [f"topic:{BRUNNA_ID}:quest"]})
    quests = again.get("quests", first["quests"])
    assert [q["id"] for q in quests].count(QID) == 1


def test_completion_ready_so_com_companheiro_ativo_no_local():
    out = cs.apply_turn(_revealed())
    assert out["companion_souls"][BRUNNA_ID]["personal_quest"] == "ready"
    assert out["quests"][0]["completion_ready"] is True
    longe = cs.apply_turn(_revealed(location="skallgard"))
    assert longe["companion_souls"][BRUNNA_ID]["personal_quest"] == "revealed"
    espera = _revealed()
    espera["party"][0].update(active=False, waiting_at="montanhas_afiadas")
    assert cs.apply_turn(espera)["companion_souls"][BRUNNA_ID]["personal_quest"] == "revealed"


def test_conclusao_pelo_motor_mais_15_e_loyal():
    state = _revealed(ready_turn=9, approval=60, ack=[f"topic:{BRUNNA_ID}:resolve"])
    out = cs.apply_turn(state)
    soul = out["companion_souls"][BRUNNA_ID]
    assert soul["personal_quest"] == "completed" and soul["approval"] == 75 and soul["loyal"]
    assert out["quests"][0]["status"] == "completed"
    done = [e for e in out["event_log"] if e["type"] == "quest_completed"]
    assert done and done[0]["payload"]["personal_of"] == BRUNNA_ID
    # sem tag para o dono: a conclusão pessoal não conta como quest_concluida
    after = {**state, **out, "turn_baseline": {**state["turn_baseline"], "event_ids": []}}
    assert "quest_concluida" not in [t["id"] for t in ctags.detect_choice_tags(after)]
    baixo = cs.apply_turn(_revealed(ready_turn=9, approval=40, ack=[f"topic:{BRUNNA_ID}:resolve"]))
    assert baixo["companion_souls"][BRUNNA_ID]["approval"] == 55
    assert not baixo["companion_souls"][BRUNNA_ID]["loyal"]


def test_conclusao_aguarda_narracao_ou_expira():
    sem = _revealed(ready_turn=9)
    assert cs.apply_turn(sem)["companion_souls"][BRUNNA_ID]["personal_quest"] == "ready"
    velha = _revealed(ready_turn=7)
    assert cs.apply_turn(velha)["companion_souls"][BRUNNA_ID]["personal_quest"] == "completed"
    mesmo_turno = _revealed(ready_turn=10, ack=[f"topic:{BRUNNA_ID}:resolve"])
    assert cs.apply_turn(mesmo_turno)["companion_souls"][BRUNNA_ID]["personal_quest"] == "ready"


def test_bloco_pede_a_cena_de_resolucao():
    block, ack = cp.companion_prompt_block(_revealed(ready_turn=9), "story")
    assert "resolve esse assunto" in block and ack == [f"topic:{BRUNNA_ID}:resolve"]


def test_falha_quando_companheiro_parte_ou_morre():
    dispensada = _revealed()
    dispensada["party"] = []
    out = cs.apply_turn(dispensada)
    assert out["quests"][0]["status"] == "failed"
    assert out["companion_souls"][BRUNNA_ID]["personal_quest"] == "failed"
    assert out["companion_souls"][BRUNNA_ID]["departed"] == "dismissed"
    morta = _revealed()
    morta["party"][0].update(dead=True, status="morto")
    out = cs.apply_turn(morta)
    assert out["companion_souls"][BRUNNA_ID]["departed"] == "dead"
    assert out["quests"][0]["status"] == "failed"
    failed = [e for e in out["event_log"] if e["type"] == "quest_failed"]
    assert failed[0]["payload"]["reason"] == "companion_gone"
    # e isso não vira tag de "missão falhou" para os outros


def test_llm_nao_conclui_missao_pessoal():
    state = _revealed()
    quest = state["quests"][0]
    quest["progress_log"] = [
        {"kind": "location_reached", "turn": 6},
        {"kind": "npc_interaction", "turn": 7},
    ]
    ok, why = quest_log.has_completion_proof(quest, state)
    assert not ok and "motor" in why
    # e a investigação genérica não a marca como pronta
    quests, ready = quest_log.sync_action_progress(
        [quest], "montanhas_afiadas", "investigo a missão e examino a ponte", turn=11
    )
    assert ready == [] and not quests[0].get("completion_ready")
