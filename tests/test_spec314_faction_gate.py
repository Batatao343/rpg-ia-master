"""SPEC-314 Etapa 1 — gate puro do bloco <FACÇÕES_DO_MUNDO> (R1-R8, R16)."""

from __future__ import annotations

import pytest

import gamedata
from services import faction_gate as fg
from tests.spec310_helpers import make_state, sergeant

SECRETAS = ("mao_sombria", "filhos_chama_azul", "druidas_renegados", "cultistas_destilacao")


def _goal(fid: str) -> str:
    return next(f["goal"] for f in gamedata.seed_factions() if f["id"] == fid)


def _name(fid: str) -> str:
    return next(f["name"] for f in gamedata.seed_factions() if f["id"] == fid)


def _view(intel=None, row=None, tier="neutro", **over):
    st = make_state(**over)
    if intel is not None:
        st["faction_intel"] = intel
    return fg.npc_faction_view(st, "Ruiva", row or sergeant(), tier)


def test_secretas_conhecidas_do_catalogo():
    assert all(fg.is_secret(f) for f in SECRETAS)
    assert not fg.is_secret("legiao_ferro")
    assert not fg.is_secret("na_anel_ferro")  # local oculto não é fação


def test_secreta_desconhecida_some():
    v = _view({})
    for fid in SECRETAS:
        assert fid not in v.visible
        assert _name(fid) not in v.block and _goal(fid) not in v.block
    assert v.counts["hidden_secret"] == 4


def test_plano_outra_faccao_por_intel_e_faixa():
    # pública: plano só em amistoso/leal (ou knows_goal)
    for tier, shows in (("neutro", False), ("amistoso", True), ("leal", True), ("hostil", False)):
        v = _view({}, tier=tier)
        assert (_goal("clas_combate") in v.block) is shows
    # secreta conhecida: sem plano em neutro; knows_goal libera
    v = _view({"filhos_chama_azul": {"known": True}})
    assert _name("filhos_chama_azul") in v.block and _goal("filhos_chama_azul") not in v.block
    v = _view({"filhos_chama_azul": {"known": True, "knows_goal": True}})
    assert _goal("filhos_chama_azul") in v.block
    # D2: rival da fação do NPC, conhecida, faixa amistoso -> plano
    v = _view({"mao_sombria": {"known": True}}, tier="amistoso")  # legiao_ferro é rival
    assert _goal("mao_sombria") in v.block
    v = _view({"mao_sombria": {"known": True}}, tier="neutro")
    assert _goal("mao_sombria") not in v.block
    # D2 só vale com 'known'
    assert _goal("mao_sombria") not in _view({}, tier="leal").block


def test_publica_desconhecida_listada_sem_plano():
    v = _view({})
    pub = [
        f
        for f in gamedata.seed_factions()
        if not fg.is_secret(f["id"]) and f["id"] != "legiao_ferro"
    ]
    assert pub
    for f in pub:
        assert f["id"] in v.visible and f["name"] in v.block
        assert f"id={f['id']} · {f['name']} ({f['region']}) · plano: você não sabe" in v.block


def test_propria_publica_com_plano():
    v = _view({})
    assert "(a sua) · plano: " + _goal("legiao_ferro") in v.block
    assert "legiao_ferro" in v.goal_shown


def test_propria_secreta_alias_nome_plano():
    row = sergeant(id="npc_pardal", faction_id="mao_sombria")
    v = _view({}, row=row, tier="neutro")
    assert fg.ALIAS_OWN in v.visible and v.visible[fg.ALIAS_OWN] == "mao_sombria"
    assert _name("mao_sombria") not in v.block and _goal("mao_sombria") not in v.block
    assert "nunca nomeie nem descreva o plano" in v.block
    # leal: nome sim, plano não
    v = _view({}, row=row, tier="leal")
    assert _name("mao_sombria") in v.block and _goal("mao_sombria") not in v.block
    # conhecida pelo jogador: nome; knows_goal: plano
    v = _view({"mao_sombria": {"known": True, "knows_goal": True}}, row=row)
    assert _name("mao_sombria") in v.block and _goal("mao_sombria") in v.block
    # membro ativo: nome + plano
    v = _view({}, row=row, faction_membership={"mao_sombria": {"status": "ativo", "rank": 0}})
    assert _goal("mao_sombria") in v.block


def test_derrotada_fora():
    facs = gamedata.seed_factions()
    for f in facs:
        if f["id"] == "clas_combate":
            f["defeated"] = True
    v = _view({}, factions=facs)
    assert "clas_combate" not in v.visible


def test_bloco_deterministico_e_nao_cresce():
    a, b = _view({}), _view({})
    assert a.block == b.block
    old = "\n".join(
        f"- id={f['id']} · {f['name']} ({f['region']}) · plano: {f['goal']}"
        for f in gamedata.seed_factions()
    )
    assert len(a.block.split("Fale do plano")[0]) < len(old)


@pytest.mark.parametrize("bad", ["ausente", None, [], "x"])
def test_intel_ausente_falha_fechado(bad):
    st = make_state()
    if bad == "ausente":
        st.pop("faction_intel")
    else:
        st["faction_intel"] = bad
    v = fg.npc_faction_view(st, "Ruiva", sergeant(), "neutro")
    for fid in SECRETAS:
        assert fid not in v.visible and _goal(fid) not in v.block
    assert fg.redacted_lore_ids(st) == frozenset(SECRETAS)


def test_helpers_publicos_para_315():
    st = make_state(faction_intel={"mao_sombria": {"known": True}})
    assert fg.known_to_player(st, "mao_sombria") and not fg.known_to_player(st, "filhos_chama_azul")
    assert not fg.goal_known_to_player(st, "mao_sombria")
    assert fg.display_faction(st, "filhos_chama_azul") == fg.UNKNOWN_FACTION
    assert fg.display_faction(st, "mao_sombria") == _name("mao_sombria")
    assert fg.display_faction(st, "legiao_ferro") == _name("legiao_ferro")
