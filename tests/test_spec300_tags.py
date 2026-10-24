"""SPEC-300 Etapa 3 — detecção de tags (só Python) e regra de ouro (testemunha)."""

from spec300_helpers import BRUNNA, BRUNNA_ID, ev, make_state, merged, npc

from services import companion_soul as cs
from services import companion_tags as ctags


def _ids(state):
    return [t["id"] for t in ctags.detect_choice_tags(state)]


def test_aceitou_rendicao_e_fugiu():
    combat = {"phase": "ended", "outcome": "surrendered_enemy", "result": {"result_event_id": "r1"}}
    assert _ids(make_state(combat=combat)) == ["aceitou_rendicao"]
    combat = {"phase": "ended", "outcome": "fled", "result": {"result_event_id": "r2"}}
    assert _ids(make_state(combat=combat)) == ["fugiu_do_combate"]
    combat = {"phase": "ended", "outcome": "victory", "result": {"result_event_id": "r3"}}
    assert _ids(make_state(combat=combat)) == []


def test_combate_encerrado_nao_reconta():
    combat = {"phase": "ended", "outcome": "fled", "result": {"result_event_id": "r2"}}
    state = make_state(combat=combat)
    assert ctags.detect_choice_tags(state, seen_combat_id="r2") == []


def test_matou_nomeado_x_inocente():
    victim = {"id": "npc_v", "name": "Vítima", "relationship": 6}
    killed = ev("e1", "npc_killed", "npc_v")
    outside = make_state(events=[killed])
    outside["npcs"]["Vítima"] = victim
    assert _ids(outside) == ["matou_inocente"]
    in_combat = make_state(events=[killed], combat={"phase": "active"})
    in_combat["npcs"]["Vítima"] = victim
    assert _ids(in_combat) == ["matou_nomeado"]
    stranger = make_state(events=[killed])
    stranger["npcs"]["Vítima"] = {**victim, "relationship": 2}
    assert _ids(stranger) == ["matou_nomeado"]


def test_eventos_de_quest_segredo_e_faccao():
    events = [
        ev("a", "quest_completed", "q1", quest_id="q1"),
        ev("b", "quest_failed", "npc_x", quest_id="q2"),
        ev("c", "secret_revealed", "npc_y"),
        ev("d", "faction_deed", "legiao_ferro", direction="ajudou"),
        ev("e", "faction_deed", "ultimos_anoes_reino", direction="prejudicou"),
    ]
    tags = ctags.detect_choice_tags(make_state(events=events))
    assert [t["id"] for t in tags] == [
        "quest_concluida",
        "quest_falhou",
        "revelou_segredo",
        "ajudou_faccao",
        "prejudicou_faccao",
    ]
    assert tags[3]["faction_id"] == "legiao_ferro" and tags[3]["sign"] == 1
    assert tags[4]["faction_id"] == "ultimos_anoes_reino" and tags[4]["sign"] == -1


def test_eventos_da_spec_299_so_se_existirem():
    events = [ev("a", "crime_witnessed", "npc_z"), ev("b", "fine_paid", "legiao_ferro")]
    assert _ids(make_state(events=events)) == ["crime_testemunhado", "pagou_multa"]


def test_usou_abismo_por_baseline():
    state = make_state()
    state["player"]["abyss_charge"] = 2
    assert _ids(state) == ["usou_abismo"]


def test_evento_antigo_nao_reconta():
    event = ev("old", "secret_revealed", "npc_y")
    assert _ids(make_state(events=[event], baseline_events=["old"])) == []


def test_regex_ameaca_e_doacao_com_negacao():
    assert ctags.detect_action_tags("Ameaço o mercador com a faca até ele baixar o preço.") == [
        "ameacou"
    ]
    assert ctags.detect_action_tags("Não vou te ameaçar, só pergunto.") == []
    assert ctags.detect_action_tags("Nunca ameacei ninguém aqui") == []
    assert ctags.detect_action_tags("Dou 10 moedas ao mendigo") == ["doou_ouro"]
    assert ctags.detect_action_tags("Não dou moedas a ninguém") == []
    assert ctags.detect_action_tags("Olho a paisagem com calma") == []


def test_doacao_exige_queda_de_ouro_sem_gasto_registrado():
    state = make_state(text="Dou 10 moedas ao mendigo", gold=100)
    assert _ids(state) == []  # texto sozinho não basta
    state["player"]["gold"] = 90
    assert _ids(state) == ["doou_ouro"]
    state["turn_baseline"]["gold_spent"] = 10  # foi compra/loja, não doação
    assert _ids(state) == []


def test_nao_le_faction_impacts_nem_narracao():
    from langchain_core.messages import AIMessage

    state = make_state(
        faction_impacts=[{"faction_id": "legiao_ferro", "direction": "ajudou"}],
        narrative_summary="O herói matou todos e ameaçou o mercador.",
    )
    state["messages"].append(AIMessage(content="Você ameaça o mercador e mata o guarda."))
    assert _ids(state) == []


def test_intencao_romantica_regex():
    from services.companion_tags import detect_romance_intent as intent

    assert intent("Flerto com Brunna sob as estrelas")
    assert intent("Gosto muito de você, Brunna")
    assert not intent("Não vou flertar com ninguém")
    assert not intent("Pergunto sobre a ponte")


def test_companheiro_em_espera_nao_reage():
    state = make_state(events=[ev("s", "secret_revealed", "npc_y")], approval=50)
    state["party"][0].update(active=False, waiting_at="montanhas_afiadas")
    out = cs.apply_turn(state)
    assert out["companion_souls"][BRUNNA_ID]["approval"] == 50
    assert out["companion_souls"][BRUNNA_ID]["reactions"] == []


def test_presente_reage_e_mesmo_turno_mesmo_resultado():
    state = make_state(
        traits=["honesto_demais", "generoso_escondido"],
        events=[ev("s", "secret_revealed", "npc_y"), ev("k", "quest_failed", "npc_x")],
    )
    state["npcs"][BRUNNA] = npc(["honesto_demais", "generoso_escondido"])
    a = cs.apply_turn(state)["companion_souls"][BRUNNA_ID]
    b = cs.apply_turn(state)["companion_souls"][BRUNNA_ID]
    assert a == b and a["approval"] < 50
    assert BRUNNA  # nome usado só para clareza do cenário
    assert merged(state, {})["party"][0]["active"]
