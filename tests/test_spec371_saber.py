"""SPEC-371 R1-R4, R14, R20: registro do saber, absorção por rodada e regra de revelação."""

from __future__ import annotations

import copy
import json

import pytest

from agents.bestiary import template_by_id
from services import conflict_orchestrator as orch
from services import discovery as disc
from services import enemy_decks as edk
from services import fauna_saber as fs

CID = "mon_arame_vivo"
IID = f"{CID}_1"
LEGADO = "enemy_rato_peste_anel_lama"


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    monkeypatch.setenv("RPG_FAUNA_SABER", "on")
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")


def _enemy(n: int = 1) -> dict:
    t = dict(template_by_id(CID, encounter_level=2))
    t["id"] = f"{CID}_{n}"
    t["name"] = "Arame Vivo"
    return orch.ensure_combat_sheet(t)


def _rnd_with_prenuncio(actor: dict) -> int:
    for rnd in range(1, 10):
        if edk.prenuncio(actor, rnd):
            return rnd
    pytest.fail("a assinatura nunca cai")


def _bk(**rec) -> dict:
    base = {"seen": 1, "fought": 1, "defeated": 0}
    base.update(rec)
    return {CID: base}


# --------------------------------------------------------------------- R2
def test_observe_so_com_flag_on(monkeypatch):
    actor = _enemy()
    rnd = _rnd_with_prenuncio(actor)
    scene: dict = {}
    assert edk.record_promise(scene, actor, rnd)
    assert scene["saber_obs"]["telegrafos"][0]["actor_id"] == IID
    monkeypatch.setenv("RPG_FAUNA_SABER", "off")
    scene_off: dict = {}
    assert edk.record_promise(scene_off, actor, rnd)
    assert "saber_obs" not in scene_off
    assert "prenuncios" in scene_off


def test_record_promise_anexa_telegrafo():
    actor = _enemy()
    rnd = _rnd_with_prenuncio(actor)
    scene: dict = {}
    edk.record_promise(scene, actor, rnd)
    row = scene["saber_obs"]["telegrafos"][0]
    assert row["carta"] == edk.assinatura_of(actor)["carta"]
    assert row["texto"] == edk.prenuncio(actor, rnd)
    edk.record_promise(scene, actor, rnd)  # idempotente
    assert len(scene["saber_obs"]["telegrafos"]) == 1


def test_note_declaration_anexa_cumprida():
    actor = _enemy()
    rnd = _rnd_with_prenuncio(actor)
    scene: dict = {}
    edk.record_promise(scene, actor, rnd)
    scene["prenuncios"][IID]["aguarda"] = True
    carta = edk.assinatura_of(actor)["carta"]
    edk.note_declaration(scene, IID, "outra_carta", rnd + 1)
    assert "cumpridas" not in scene["saber_obs"]
    edk.note_declaration(scene, IID, carta, rnd + 1)
    assert scene["saber_obs"]["cumpridas"] == [{"actor_id": IID, "carta": carta, "rnd": rnd + 1}]
    assert IID not in scene["prenuncios"]


# --------------------------------------------------------------------- R3
def _scene(telegrafos=(), cumpridas=()):
    obs: dict = {}
    if telegrafos:
        obs["telegrafos"] = [{"actor_id": IID, "carta": "c", "texto": t} for t in telegrafos]
    if cumpridas:
        obs["cumpridas"] = [{"actor_id": IID, "carta": "c", "rnd": r} for r in cumpridas]
    return {"saber_obs": obs} if obs else {}


def test_absorb_soma_sobrevivida_so_com_jogador_vivo():
    actors = {"player": {"id": "player"}, IID: _enemy()}
    bk, _ = fs.absorb(_bk(), _scene(cumpridas=[3]), actors, True, 5)
    assert bk[CID]["assinaturas_sobrevividas"] == 1
    bk2, _ = fs.absorb(_bk(), _scene(cumpridas=[3]), actors, False, 5)
    assert "assinaturas_sobrevividas" not in bk2[CID]


def test_absorb_telegrafo_dedup_e_cap_4():
    actors = {IID: _enemy()}
    bk, _ = fs.absorb(_bk(), _scene(telegrafos=["a", "a", "b", "c", "d", "e"]), actors, True, 5)
    assert bk[CID]["telegrafos_vistos"] == ["a", "b", "c", "d"]
    bk, _ = fs.absorb(bk, _scene(telegrafos=["a", "f"]), actors, True, 6)
    assert bk[CID]["telegrafos_vistos"] == ["a", "b", "c", "d"]
    longo = "x" * 400
    bk, _ = fs.absorb(_bk(), _scene(telegrafos=[longo]), actors, True, 5)
    assert len(bk[CID]["telegrafos_vistos"][0]) == fs.MAX_TEXTO


def test_absorb_ignora_ator_sem_bestiario():
    ad_hoc = {"id": "bandido_xyz_1", "name": "Bandido Xyz"}
    scene = {"saber_obs": {"telegrafos": [{"actor_id": "bandido_xyz_1", "texto": "t"}]}}
    bk, logs = fs.absorb(_bk(), scene, {"bandido_xyz_1": ad_hoc}, True, 5)
    assert bk == _bk() and logs == []


def test_absorb_limpa_saber_obs():
    scene = _scene(telegrafos=["a"], cumpridas=[2])
    fs.absorb(_bk(), scene, {IID: _enemy()}, True, 5)
    assert "saber_obs" not in scene


def test_absorb_off_nao_mexe(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA_SABER", "off")
    scene = _scene(telegrafos=["a"], cumpridas=[2])
    bk0 = _bk()
    bk, logs = fs.absorb(bk0, scene, {IID: _enemy()}, True, 5)
    assert bk is bk0 and logs == [] and "saber_obs" in scene


def test_absorb_nao_muta_o_bk_de_entrada():
    bk0 = _bk()
    snap = copy.deepcopy(bk0)
    fs.absorb(bk0, _scene(telegrafos=["a"], cumpridas=[2]), {IID: _enemy()}, True, 5)
    assert bk0 == snap


# --------------------------------------------------------------------- R4
_REVELADO = {"motivo": "estudada", "turn": 1}


@pytest.mark.parametrize(
    ("rec", "cid", "esperado"),
    [
        ({"assinaturas_sobrevividas": 1}, CID, "sobreviveu"),
        ({"defeated": 3}, CID, "estudada"),
        ({"sinais_vistos": ["rastro", "som"], "fought": 1}, CID, "rastreada"),
        ({"assinaturas_sobrevividas": 2, "defeated": 5}, LEGADO, None),
        ({"assinaturas_sobrevividas": 1, "saber_revelado": _REVELADO}, CID, None),
    ],
)
def test_regra_tabela_3_5(rec, cid, esperado):
    assert fs.reveal_reason(rec, cid) == esperado


def test_rastreada_exige_dois_sinais_e_luta():
    assert fs.reveal_reason({"sinais_vistos": ["rastro"], "fought": 1}, CID) is None
    assert fs.reveal_reason({"sinais_vistos": ["rastro", "som"], "fought": 0}, CID) is None


def test_ordem_dos_motivos():
    rec = {"assinaturas_sobrevividas": 1, "defeated": 3, "sinais_vistos": ["a", "b"], "fought": 1}
    assert fs.reveal_reason(rec, CID) == "sobreviveu"
    rec["assinaturas_sobrevividas"] = 0
    assert fs.reveal_reason(rec, CID) == "estudada"


def test_revelacao_pegajosa():
    actors = {IID: _enemy()}
    bk, logs = fs.absorb(_bk(), _scene(cumpridas=[2]), actors, True, 7)
    assert bk[CID]["saber_revelado"] == {"motivo": "sobreviveu", "turn": 7}
    assert len(logs) == 1
    bk2, logs2 = fs.absorb(bk, _scene(cumpridas=[5]), actors, True, 9)
    assert bk2[CID]["saber_revelado"] == {"motivo": "sobreviveu", "turn": 7}
    assert logs2 == []
    bk3, logs3 = fs.finish_combat(bk2, [_enemy()], 12)
    assert bk3[CID]["saber_revelado"]["turn"] == 7 and logs3 == []


def test_linha_de_log_uma_vez():
    actors = {IID: _enemy()}
    bk, logs = fs.absorb(_bk(), _scene(cumpridas=[2]), actors, True, 7)
    assert logs == ["Você aprendeu como enfrentar Arame Vivo: veja o Bestiário."]
    bk, logs = fs.absorb(bk, {}, actors, True, 8)
    assert logs == []


def test_finish_combat_estudada():
    bk, logs = fs.finish_combat(_bk(defeated=3), [_enemy()], 9)
    assert bk[CID]["saber_revelado"]["motivo"] == "estudada" and len(logs) == 1


def test_sem_fonte_nao_revela():
    bk0 = {LEGADO: {"seen": 1, "fought": 1, "assinaturas_sobrevividas": 3}}
    t = {**template_by_id(LEGADO, encounter_level=2), "id": f"{LEGADO}_1"}
    bk, logs = fs.finish_combat(bk0, [orch.ensure_combat_sheet(t)], 3)
    assert "saber_revelado" not in bk[LEGADO] and logs == []


# ----------------------------------------------------------- R3 (combate real)
def test_simulacao_e_previa_nao_absorvem():
    """`agents/combat.py` so chama absorb/finish_combat fora de `is_simulation`."""
    import inspect

    from agents import combat

    src = inspect.getsource(combat)
    assert "if not is_simulation and _fauna_saber.active()" in src
    assert "if combat_over and not is_simulation and _fauna_saber.active()" in src


# --------------------------------------------------------------------- R20
def test_saber_obs_de_save_no_meio_do_combate():
    scene = json.loads(json.dumps(_scene(telegrafos=["a"], cumpridas=[2])))  # round-trip do save
    bk, _ = fs.absorb(_bk(), scene, {IID: _enemy()}, True, 5)
    assert bk[CID]["telegrafos_vistos"] == ["a"]
    assert bk[CID]["assinaturas_sobrevividas"] == 1
    bk2, _ = fs.absorb(bk, scene, {IID: _enemy()}, True, 6)  # nao duplica
    assert bk2[CID]["assinaturas_sobrevividas"] == 1


def test_round_trip_campos_novos():
    bk, _ = fs.absorb(_bk(), _scene(telegrafos=["a"], cumpridas=[2]), {IID: _enemy()}, True, 5)
    assert json.loads(json.dumps(bk)) == bk


def test_save_antigo_sem_campos():
    bk = _bk(defeated=1)
    view = disc.bestiary_view(bk)
    assert view and "contra_jogo" not in view[0]
    enemy = _enemy()
    fs.stamp_actor(enemy, bk)
    assert enemy["saber_jogador"] == {"contra_jogo": None, "assinaturas": []}
    assert disc.knowledge_tier(bk[CID]) == 2


def test_round_trip_save_game_state_load_game_state():
    """P2-4 (Sol): os três campos e `combat.scene.saber_obs` passam por save/load reais."""
    from tests.test_spec360_saves import _roundtrip
    from tests.test_spec360_sinais import sim_with, state_at

    bk = _bk(
        sinais_vistos=["rastro", "som"],
        telegrafos_vistos=["O arame abre os ganchos."],
        assinaturas_sobrevividas=2,
        saber_revelado={"motivo": "sobreviveu", "turn": 7},
    )
    scene = _scene(telegrafos=["a"], cumpridas=[3])
    st = state_at(sim=sim_with())
    st["bestiary_knowledge"] = bk
    st["combat"] = {"active": True, "round": 2, "scene": scene}
    loaded = _roundtrip(st)
    assert loaded["bestiary_knowledge"] == bk
    assert loaded["combat"]["scene"]["saber_obs"] == scene["saber_obs"]
    # o turno seguinte absorve a observação guardada, uma vez só
    cena = loaded["combat"]["scene"]
    novo, _ = fs.absorb(loaded["bestiary_knowledge"], cena, {IID: _enemy()}, True, 9)
    assert novo[CID]["assinaturas_sobrevividas"] == 3 and "saber_obs" not in cena
