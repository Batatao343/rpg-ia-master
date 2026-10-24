"""SPEC-300 Etapa 1 — valores derivados, aprovação inicial, deltas e rótulos."""

from spec300_helpers import BRUNNA_ID, npc

from services import companion_soul as cs


def _soul(values, approval=50, faction="ultimos_anoes_reino"):
    return {"values": values, "approval": approval, "reactions": [], "companion_id": BRUNNA_ID}


def _tag(tag_id, faction_id="", sign=0):
    return {"id": tag_id, "faction_id": faction_id, "sign": sign, "source_ref": "x"}


def test_derive_values_deterministico():
    n = npc(traits=["honesto_demais", "veterano_de_guerra"])
    assert cs.derive_values(n) == cs.derive_values(dict(n))
    vals = cs.derive_values(n)
    assert vals["honra"] == 2 and vals["ordem"] == 2 and vals["coragem"] == 2


def test_derive_values_clamp():
    n = npc(traits=["honesto_demais", "divida_de_sangue", "orgulho_de_cla", "sangue_da_montanha"])
    assert all(-2 <= v <= 2 for v in cs.derive_values(n).values())
    assert cs.derive_values(n)["honra"] == 2


def test_initial_approval_por_relationship():
    assert cs.initial_approval({"relationship": 7}) == 50
    assert cs.initial_approval({"relationship": 10}) == 59
    assert cs.initial_approval({"relationship": 3}) == 40
    assert cs.initial_approval({"relationship": 0}) == 40


def test_prisioneiro_comeca_em_20():
    assert cs.initial_approval({"relationship": 9}, origin="prisoner") == 20


def test_delta_alinhado_positivo_e_desalinhado_negativo():
    honra = _soul({"honra": 2})
    assert cs.tag_delta(honra, _tag("quest_concluida"), companion_faction="") == 8
    soul, delta = cs.apply_tags(
        _soul({"compaixao": 2, "honra": 2}), [_tag("ameacou")], turn=5, companion_faction=""
    )
    assert delta == -8 and soul["approval"] == 42
    assert soul["reactions"][-1]["tag"] == "ameacou"


def test_faction_direct_soma_sinal():
    soul = _soul({})
    up = _tag("ajudou_faccao", "ultimos_anoes_reino", +1)
    down = _tag("prejudicou_faccao", "ultimos_anoes_reino", -1)
    other = _tag("ajudou_faccao", "legiao_ferro", +1)
    assert cs.tag_delta(soul, up, companion_faction="ultimos_anoes_reino") == 8
    assert cs.tag_delta(soul, down, companion_faction="ultimos_anoes_reino") == -8
    assert cs.tag_delta(soul, other, companion_faction="ultimos_anoes_reino") == 0


def test_tag_cap_e_turn_cap():
    soul = _soul({a: 2 for a in cs.AXES})
    assert cs.tag_delta(soul, _tag("matou_inocente"), companion_faction="") == -10  # TAG_CAP
    _, total = cs.apply_tags(soul, [_tag("quest_concluida")] * 3, turn=5, companion_faction="")
    assert total == 15  # TURN_CAP


def test_aprovacao_limitada_0_100():
    low, _ = cs.apply_tags(
        _soul({"compaixao": 2, "honra": 2}, approval=3),
        [_tag("ameacou")],
        turn=5,
        companion_faction="",
    )
    assert low["approval"] == 0
    high, _ = cs.apply_tags(
        _soul({"honra": 2}, approval=98), [_tag("quest_concluida")], turn=5, companion_faction=""
    )
    assert high["approval"] == 100


def test_change_phrase_buckets():
    assert cs.change_phrase("Brunna", 1) is None
    assert cs.change_phrase("Brunna", 2) == "Brunna reparou nisso."
    assert cs.change_phrase("Brunna", -4) == "Brunna não gostou disso."
    assert cs.change_phrase("Brunna", 5) == "Brunna gostou disso."
    assert cs.change_phrase("Brunna", -8) == "Brunna não vai esquecer isso."
    assert cs.change_phrase("Brunna", 9) == "Brunna aprovou muito."


def test_approval_label_faixas():
    assert cs.approval_label(0) == "hostil" and cs.approval_label(14) == "hostil"
    assert cs.approval_label(15) == "desconfiado" and cs.approval_label(34) == "desconfiado"
    assert cs.approval_label(35) == "neutro" and cs.approval_label(59) == "neutro"
    assert cs.approval_label(60) == "amistoso" and cs.approval_label(79) == "amistoso"
    assert cs.approval_label(80) == "leal" and cs.approval_label(100) == "leal"
