"""Suíte da spec encontros-dedupe — NPC gerado com vínculo de local + dedupe.

Offline/determinístico. Ver specs/encontros-dedupe.md.
"""
from playtest import invariants as inv
from services.npc_layers import npcs_for_context


def _state(npcs, loc="pantano_melancolia", party=None):
    return {"world": {"current_location_id": loc}, "npcs": npcs, "party": party or []}


# --- R1: vínculo de local + view filtrada -----------------------------------

def test_context_exclui_npc_de_outro_local():
    npcs = {
        "Tomás": {"home_location_id": "pantano_melancolia", "in_scene": False},
        "Bruxa Distante": {"home_location_id": "nova_arcadia", "in_scene": False},
    }
    got = npcs_for_context(_state(npcs))
    assert "Tomás" in got                 # vinculado a este local
    assert "Bruxa Distante" not in got    # de outro local, fora de cena


def test_in_scene_sempre_entra():
    npcs = {"Viajante": {"home_location_id": "outro_lugar", "in_scene": True}}
    assert "Viajante" in npcs_for_context(_state(npcs))


def test_party_sempre_entra():
    npcs = {"Sombra": {"home_location_id": "longe", "in_scene": False}}
    st = _state(npcs, party=[{"name": "Gorim", "active": True, "status": "ativo"}])
    st["npcs"]["Gorim"] = {"home_location_id": "longe", "in_scene": False}
    got = npcs_for_context(st)
    assert "Gorim" in got
    assert "Sombra" not in got


def test_npc_sem_vinculo_fora_de_cena_nao_entra():
    npcs = {"Fantasma": {"home_location_id": "", "in_scene": False}}
    assert npcs_for_context(_state(npcs)) == []


# --- R4: invariante ---------------------------------------------------------

def test_invariante_recycled_npc_dispara():
    npcs = {"Sobrevivente moribundo": {"created_turn": 5, "in_scene": True,
                                       "home_location_id": "caverna_morrakh"}}
    viol = inv.check_recycled_npc(_state(npcs, loc="anel_dourado"), None, 11)
    assert viol and viol[0].check_id == "narrative.recycled_npc"
    assert viol[0].severity == "warning"


def test_invariante_recycled_npc_ok_no_proprio_local():
    npcs = {"Sobrevivente moribundo": {"created_turn": 5, "in_scene": True,
                                       "home_location_id": "caverna_morrakh"}}
    assert inv.check_recycled_npc(_state(npcs, loc="caverna_morrakh"), None, 6) == []


def test_invariante_curado_nao_dispara():
    # NPC curado (sem created_turn) pode estar onde a curadoria mandar.
    npcs = {"Rainha": {"in_scene": True, "home_location_id": "trono"}}
    assert inv.check_recycled_npc(_state(npcs, loc="jardim"), None, 6) == []


# --- exceção narrativa: NPC pode SAIR se re-introduzido em outro local -------

def test_reintroducao_relocaliza_npc():
    # NPC gerado no pântano; a narrativa o traz para o Anel Dourado (re-introduz)
    # → home_location_id atualiza (viajou junto / mandado em missão).
    from agents.storyteller import _with_new_npc
    npcs = {"Gorim": {"name": "Gorim", "in_scene": False,
                      "home_location_id": "pantano_melancolia", "created_turn": 2}}
    out = _with_new_npc(npcs, "Gorim", "Anel Dourado", "Gorim chega com o herói.",
                        game_id="g", home_id="na_anel_dourado", turn=9)
    assert out["Gorim"]["home_location_id"] == "na_anel_dourado"
    assert out["Gorim"]["in_scene"] is True
    # e agora aparece no contexto do novo local (não é mais "preso" ao pântano)
    st = _state(out, loc="na_anel_dourado")
    assert "Gorim" in npcs_for_context(st)
