"""SPEC-339 — controle/condição de `duracao` 1 aplicado por OUTRO ator vale antes de expirar.

Regra: `duracao` d = o portador atravessa d turnos próprios que começam depois da aplicação.
O marcador `_pula_tick` é posto pelo ORQUESTRADOR (design A) — o golden da SPEC-330 não muda.

O inventário (R7) roda `run_round` real nas duas ordens de iniciativa, trocando só o passo
de ação do ator por um aplicador controlado (a mecânica de tick/expiração é a do motor).
"""

import json
import random
from pathlib import Path

import pytest

import combat_mechanics as cm
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct

_V = {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2}
_TWO_ROUNDS_PLUS = 4


def _actor(aid: str, **kw) -> dict:
    base = {"id": aid, "name": aid, "virtudes": dict(_V)}
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(aid == "player"))


def _scene(*ids) -> dict:
    scene = cs.new_scene()
    for i in ids:
        cs.place(scene, i)
    cs.freeze(scene)
    return scene


# ordem forçada: "hero_first" => jogador age antes; "enemy_first" => inimigo antes
ORDENS = {"hero_first": "heroes", "enemy_first": "enemy"}


def _cond(kind: str, source_actor_id: str) -> dict:
    """Condição `duracao` 1 do catálogo, como o motor a monta."""
    if kind in ("stun", "root", "fear", "silence"):
        return {"name": kind, "dot": 0, "duration": 1, "control": kind, "source": "t"}
    if kind in ("taunt", "marca"):
        return {
            "name": kind,
            "dot": 0,
            "duration": 1,
            "control": kind,
            "source": "t",
            "source_actor_id": source_actor_id,
            "delta": 2,
        }
    if kind == "marca_abismo":
        from services import card_effects as fx

        c = fx.marca_abismo_condition(2, "t", source_actor_id)
        c["duration"] = 1
        return c
    c = cm.parse_condition(kind, source="t")
    c["duration"] = 1
    return c


def _run(kind: str, applier: str, ordem: str, rounds: int = _TWO_ROUNDS_PLUS, monkeypatch=None):
    """Aplicador põe a condição no OUTRO ator no seu 1º turno. Devolve o que cada ator viu
    no início do próprio turno (depois do tick) e os logs."""
    carrier = "e" if applier == "player" else "player"
    actors = {"player": _actor("player"), "e": _actor("e")}
    scene = _scene("player", "e")
    sides = {"hero": ["player"], "enemy": ["e"]}
    seen: list[tuple[int, str, bool]] = []
    state = {"rnd": 0, "applied": False}

    def fake_turn(scene_, actor, actor_id, actors_by_id, sides_, decl, st, out, rng):
        nome = _cond(kind, applier)["name"]
        present = any(c.get("name") == nome for c in actor.get("active_conditions") or [])
        seen.append((state["rnd"], actor_id, present))
        if actor_id == applier and not state["applied"]:
            state["applied"] = True
            out["logs"].append(cm.apply_condition(actors_by_id[carrier], _cond(kind, applier)))

    monkeypatch.setattr(orch, "_resolve_actor_turn", fake_turn)
    logs: list[str] = []
    for rnd in range(1, rounds + 1):
        state["rnd"] = rnd
        out = orch.run_round(
            scene,
            actors,
            sides,
            None,
            declarations={"player": ct.TurnDeclaration(actor_id="player")},
            initiator=ORDENS[ordem],
            rng=random.Random(rnd),
        )
        logs += out["logs"]
    return carrier, seen, logs, actors


def _vistas(seen, who):
    return [(r, p) for r, a, p in seen if a == who]


# --------------------------------------------------------------------------
# R1 — controle de leitura tardia
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ordem", ORDENS)
@pytest.mark.parametrize("applier", ["player", "e"])
@pytest.mark.parametrize("kind", ["taunt", "fear", "silence", "root"])
def test_controle_tardio_d1_vale_no_proximo_turno_do_portador(kind, applier, ordem, monkeypatch):
    carrier, seen, logs, _ = _run(kind, applier, ordem, monkeypatch=monkeypatch)
    # o portador atravessa exatamente 1 turno próprio com a condição ativa
    assert sum(p for _, p in _vistas(seen, carrier)) == 1, seen
    # a condição não some com "terminou" antes de o portador agir: o 1º aviso vem depois
    first_seen = next(i for i, (_, a, p) in enumerate(seen) if a == carrier and p)
    assert first_seen >= 0 and not any(f"{carrier}: {kind} terminou" in ln for ln in logs[:1])


def _alvo_no_turno_do_aplicador(kind, applier, ordem, monkeypatch):
    """A Marca é lida no PORTADOR quando o aplicador ataca: devolve, por turno do aplicador,
    se o portador ainda a carregava."""
    carrier = "e" if applier == "player" else "player"
    actors = {"player": _actor("player"), "e": _actor("e")}
    scene = _scene("player", "e")
    sides = {"hero": ["player"], "enemy": ["e"]}
    vistas: list[bool] = []
    st = {"applied": False}

    def fake_turn(scene_, actor, actor_id, actors_by_id, sides_, decl, s, out, rng):
        if actor_id == applier:
            vistas.append(
                any(
                    c.get("name") == kind
                    for c in actors_by_id[carrier].get("active_conditions") or []
                )
            )
            if not st["applied"]:
                st["applied"] = True
                cm.apply_condition(actors_by_id[carrier], _cond(kind, applier))

    monkeypatch.setattr(orch, "_resolve_actor_turn", fake_turn)
    for rnd in range(1, 5):
        orch.run_round(
            scene,
            actors,
            sides,
            None,
            declarations={"player": ct.TurnDeclaration(actor_id="player")},
            initiator=ORDENS[ordem],
            rng=random.Random(rnd),
        )
    return vistas


@pytest.mark.parametrize("ordem", ORDENS)
@pytest.mark.parametrize("applier", ["player", "e"])
def test_marca_d1_presente_quando_o_aplicador_age_de_novo(applier, ordem, monkeypatch):
    vistas = _alvo_no_turno_do_aplicador("marca", applier, ordem, monkeypatch)
    # turno 1: antes de aplicar (False); turno 2: Marca de duracao 1 ainda vale; turno 3: sumiu
    assert vistas[:3] == [False, True, False], vistas


@pytest.mark.parametrize("ordem", ORDENS)
def test_marca_do_inimigo_no_jogador_simetria(ordem, monkeypatch):
    vistas = _alvo_no_turno_do_aplicador("marca", "e", ordem, monkeypatch)
    assert vistas[:3] == [False, True, False], vistas


# --------------------------------------------------------------------------
# R2 — stun inalterado; R3 — DoT inalterado
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ordem", ORDENS)
@pytest.mark.parametrize("applier", ["player", "e"])
def test_stun_d1_nega_exatamente_um_turno(applier, ordem, monkeypatch):
    carrier, seen, logs, _ = _run("stun", applier, ordem, monkeypatch=monkeypatch)
    assert sum("perde o turno" in ln for ln in logs) == 1, logs
    # o portador age (não é negado) nos outros turnos: 4 rodadas, 1 negada
    assert len(_vistas(seen, carrier)) == _TWO_ROUNDS_PLUS - 1


@pytest.mark.parametrize("ordem", ORDENS)
@pytest.mark.parametrize("applier", ["player", "e"])
def test_dot_d1_um_tick(applier, ordem, monkeypatch):
    carrier, seen, logs, actors = _run("sangrando", applier, ordem, monkeypatch=monkeypatch)
    assert sum("sofre 1 de" in ln for ln in logs) == 1, logs
    assert actors[carrier]["vitalidade"] == actors[carrier]["max_vitalidade"] - 1


def test_sangria_decai_igual():
    e = _actor("e")
    cm.apply_condition(e, dict(cm.parse_condition("sangria", source="t"), duration=3))
    out = {"logs": []}
    totals = []
    for _ in range(3):
        before = e["vitalidade"]
        orch._tick_conditions_v4(e, out)
        totals.append(before - e["vitalidade"])
    assert totals == [2, 1, 0]


# --------------------------------------------------------------------------
# R5 — compatibilidade
# --------------------------------------------------------------------------
def test_tick_direto_sem_marcador_igual_hoje():
    e = _actor("e")
    cm.apply_condition(e, _cond("taunt", "player"))
    out = {"logs": []}
    orch._tick_conditions_v4(e, out)
    assert e["active_conditions"] == []
    assert any("terminou" in ln for ln in out["logs"])


def test_marcador_pula_so_o_primeiro_tick():
    e = _actor("e")
    cm.apply_condition(e, _cond("fear", "player"))
    e["active_conditions"][0]["_pula_tick"] = True
    out = {"logs": []}
    orch._tick_conditions_v4(e, out)
    assert len(e["active_conditions"]) == 1 and "_pula_tick" not in e["active_conditions"][0]
    orch._tick_conditions_v4(e, out)
    assert e["active_conditions"] == []


def test_marcador_nao_vaza_na_view():
    import api

    e = _actor("e", id="e")
    cm.apply_condition(e, _cond("taunt", "player"))
    e["active_conditions"][0]["_pula_tick"] = True
    state = {"player": _actor("player"), "enemies": [e], "combat": {"active": True}}
    blob = json.dumps(api._combat_block(state), default=str)
    assert "_pula_tick" not in blob and "_renovada" not in blob


def test_marcador_nao_afeta_dot():
    e = _actor("e")
    c = cm.parse_condition("sangrando", source="t")
    c["duration"] = 1
    cm.apply_condition(e, c)
    e["active_conditions"][0]["_pula_tick"] = True
    out = {"logs": []}
    orch._tick_conditions_v4(e, out)
    assert e["active_conditions"] == []  # DoT d1: 1 tick e some (R3)


# --------------------------------------------------------------------------
# _mark_fresh_conditions (unitário)
# --------------------------------------------------------------------------
def test_mark_stun_nunca_e_marcado():
    a, b = _actor("a"), _actor("b")
    actors = {"a": a, "b": b}
    before = orch._snapshot_conditions(actors)
    cm.apply_condition(b, _cond("stun", "a"))
    assert orch._mark_fresh_conditions(before, actors, "a") == 0


def test_mark_autoaplicado_no_proprio_turno_nao_e_marcado():
    a, b = _actor("a"), _actor("b")
    actors = {"a": a, "b": b}
    before = orch._snapshot_conditions(actors)
    cm.apply_condition(a, _cond("taunt", "a"))
    assert orch._mark_fresh_conditions(before, actors, "a") == 0


def test_mark_reacao_de_outro_no_turno_do_portador_e_marcada():
    a, b = _actor("a"), _actor("b")
    actors = {"a": a, "b": b}
    before = orch._snapshot_conditions(actors)
    cm.apply_condition(a, _cond("taunt", "b"))  # b reagiu e provocou o atacante a
    assert orch._mark_fresh_conditions(before, actors, "a") == 1


def test_mark_refresh_tambem_recebe_o_marcador():
    a, b = _actor("a"), _actor("b")
    actors = {"a": a, "b": b}
    cm.apply_condition(b, _cond("taunt", "a"))  # já existia, duracao 1, sem marcador
    before = orch._snapshot_conditions(actors)
    cm.apply_condition(b, _cond("taunt", "a"))  # reaplicada (mesma duracao)
    assert orch._mark_fresh_conditions(before, actors, "a") == 1
    assert b["active_conditions"][0].get("_pula_tick") is True


def test_mark_stat_defensivo_so_fora_do_proprio_turno():
    a, b = _actor("a"), _actor("b")
    actors = {"a": a, "b": b}
    before = orch._snapshot_conditions(actors)
    cm.apply_condition(b, dict(cm.parse_condition("exposto", source="t"), duration=1))
    assert orch._mark_fresh_conditions(before, actors, None) == 0  # fora de turno: não
    before = orch._snapshot_conditions({"a": a, "b": _actor("c")})
    b2 = _actor("b2")
    actors2 = {"a": a, "b": b2}
    before = orch._snapshot_conditions(actors2)
    cm.apply_condition(b2, dict(cm.parse_condition("exposto", source="t"), duration=1))
    assert orch._mark_fresh_conditions(before, actors2, "a") == 1


def test_stat_ofensivo_nao_e_marcado():
    a, b = _actor("a"), _actor("b")
    actors = {"a": a, "b": b}
    before = orch._snapshot_conditions(actors)
    cm.apply_condition(b, dict(cm.parse_condition("enfraquecido", source="t"), duration=1))
    assert orch._mark_fresh_conditions(before, actors, "a") == 0


def test_todo_control_do_acervo_esta_classificado():
    root = Path(__file__).resolve().parent.parent / "data" / "cards"
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            ctl = node.get("control")
            if isinstance(ctl, str):
                found.add(ctl)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for path in root.rglob("*.json"):
        walk(json.loads(path.read_text(encoding="utf-8")))
    for kind in ("silence", "root", "fear"):
        found.add(kind)
    desconhecidos = found - orch._LATE_READ_CONTROLS - {"stun"}
    assert not desconhecidos, f"control novo sem classificação (SPEC-339 §3.1): {desconhecidos}"


# --------------------------------------------------------------------------
# R7/R8 — inventário: onde o efeito é lido
# --------------------------------------------------------------------------
# kind -> lido onde: "portador" (turno do portador) | "aplicador" (turno do aplicador, no alvo)
#         | "tick" (o próprio tick) | "ja_ok" (já funcionava)
INVENTARIO = {
    "stun": "ja_ok",
    "taunt": "portador",
    "fear": "portador",
    "silence": "portador",
    "root": "portador",
    "marca": "aplicador",
    "marca_abismo": "aplicador",
    "sangrando": "tick",
    "sangria": "tick",
    "torpor": "ja_ok",
    "enfraquecido": "ja_ok",
    "desmoralizado": "ja_ok",
    "cego": "ja_ok",
    "desarmado_risco": "ja_ok",
    "exposto": "aplicador",
    "rachadura": "aplicador",
    "armadura_comprometida": "aplicador",
}


@pytest.mark.parametrize("ordem", ORDENS)
@pytest.mark.parametrize("applier", ["player", "e"])
@pytest.mark.parametrize("kind", sorted(INVENTARIO))
def test_inventario_duracao(kind, applier, ordem, monkeypatch):
    onde = INVENTARIO[kind]
    if onde == "portador":
        carrier, seen, _, _ = _run(kind, applier, ordem, monkeypatch=monkeypatch)
        assert sum(p for _, p in _vistas(seen, carrier)) == 1
    elif onde == "aplicador":
        if kind == "marca_abismo":
            pytest.skip("coberta por test_marca_do_abismo_*")
        vistas = _alvo_no_turno_do_aplicador(
            _cond(kind, applier)["name"], applier, ordem, monkeypatch
        )
        assert vistas[:3] == [False, True, False], vistas
    elif onde == "tick":
        carrier, _, logs, actors = _run(kind, applier, ordem, monkeypatch=monkeypatch)
        assert sum("sofre" in ln for ln in logs) >= 1
    elif kind == "stun":  # lido ANTES do tick: nega exatamente 1 turno (R2)
        _, _, logs, _ = _run(kind, applier, ordem, monkeypatch=monkeypatch)
        assert sum("perde o turno" in ln for ln in logs) == 1
    else:  # ja_ok: o portador lê no próprio turno, como hoje
        carrier, seen, _, _ = _run(kind, applier, ordem, monkeypatch=monkeypatch)
        assert sum(p for _, p in _vistas(seen, carrier)) >= 1


# --------------------------------------------------------------------------
# R6/D3 — Marca do Abismo: 3 turnos efetivos
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ordem", ORDENS)
def test_marca_do_abismo_aplicada_por_oponente_dura_tres_turnos_efetivos(ordem, monkeypatch):
    from services import card_effects as fx

    actors = {"player": _actor("player"), "e": _actor("e")}
    scene = _scene("player", "e")
    sides = {"hero": ["player"], "enemy": ["e"]}
    st = {"applied": False}
    vistas: list[bool] = []

    def fake_turn(scene_, actor, actor_id, abid, sides_, decl, s, out, rng):
        if actor_id == "e":
            vistas.append(
                any(c.get("keyword") == "marca_do_abismo" for c in actor["active_conditions"])
            )
        if actor_id == "player" and not st["applied"]:
            st["applied"] = True
            cm.apply_condition(abid["e"], fx.marca_abismo_condition(2, "t", "player"))

    monkeypatch.setattr(orch, "_resolve_actor_turn", fake_turn)
    for rnd in range(1, 6):
        orch.run_round(
            scene,
            actors,
            sides,
            None,
            declarations={"player": ct.TurnDeclaration(actor_id="player")},
            initiator=ORDENS[ordem],
            rng=random.Random(rnd),
        )
    # d=3: o portador atravessa 3 turnos próprios que começam depois da aplicação
    assert sum(vistas) == 3, vistas


# --------------------------------------------------------------------------
# R8b — stat defensivo
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ordem", ORDENS)
def test_exposto_aplicado_pelo_jogador_vale_no_proximo_turno_dele(ordem, monkeypatch):
    actors = {"player": _actor("player"), "e": _actor("e")}
    scene = _scene("player", "e")
    sides = {"hero": ["player"], "enemy": ["e"]}
    st = {"applied": False}
    vistas = []

    def fake_turn(scene_, actor, actor_id, abid, sides_, decl, s, out, rng):
        if actor_id == "player":
            vistas.append(any(c.get("stat") == "ac" for c in abid["e"]["active_conditions"]))
            if not st["applied"]:
                st["applied"] = True
                cm.apply_condition(
                    abid["e"], dict(cm.parse_condition("exposto", source="t"), duration=1)
                )

    monkeypatch.setattr(orch, "_resolve_actor_turn", fake_turn)
    for rnd in range(1, 5):
        orch.run_round(
            scene,
            actors,
            sides,
            None,
            declarations={"player": ct.TurnDeclaration(actor_id="player")},
            initiator=ORDENS[ordem],
            rng=random.Random(rnd),
        )
    assert vistas[:3] == [False, True, False], vistas


# --------------------------------------------------------------------------
# Cartas reais: Provocar (bas_dev_voto) e presságio (R9)
# --------------------------------------------------------------------------
def _cena_devoto():
    aliado = _actor("ally", categoria="companheiro", transient=True, virtudes=dict(_V, agilidade=9))
    player = _actor(
        "player",
        class_name="Devoto do Abismo",
        known_cards=["bas_dev_voto"],
        prepared_cards=["bas_dev_voto"],
        entropy=0,
        max_entropy=10,
        level=1,
        virtudes=dict(_V, agilidade=1),
    )
    enemy = _actor("e", virtudes=dict(_V, agilidade=1))
    actors = {"player": player, "ally": aliado, "e": enemy}
    scene = _scene("player", "ally", "e")
    sides = {"hero": ["player"], "ally": ["ally"], "enemy": ["e"]}
    return actors, scene, sides


class _Rng0(random.Random):
    """random() sempre 0.0 => a chance de Provocação (<= 0,9) sempre passa."""

    def random(self):
        return 0.0


def _voto():
    return ct.TurnDeclaration(
        actor_id="player", acao=ct.TurnStep(kind="card", card_id="bas_dev_voto", target_id="e")
    )


@pytest.mark.parametrize("ordem", ORDENS)
def test_taunt_d1_do_jogador_redireciona_proximo_turno_inimigo(ordem):
    actors, scene, sides = _cena_devoto()
    out = orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _voto()},
        initiator=ORDENS[ordem],
        rng=_Rng0(1),
    )
    logs = list(out["logs"])
    if ordem == "enemy_first":  # inimigo age antes da aplicação; o efeito vale na rodada 2
        out2 = orch.run_round(
            scene,
            actors,
            sides,
            {"player": actors["player"]},
            declarations={"player": ct.TurnDeclaration(actor_id="player")},
            initiator="enemy",
            rng=_Rng0(2),
        )
        logs += out2["logs"]
        alvo_logs = out2["logs"]
    else:
        alvo_logs = out["logs"]
    assert not any("Provocação terminou" in ln or "Voto Sussurrado terminou" in ln for ln in logs)
    assert not any(
        "terminou" in ln for ln in logs[: logs.index(next(x for x in logs if "e → " in x))]
    )
    ataque = next(x for x in alvo_logs if x.startswith("e → "))
    assert ataque.startswith("e → player"), ataque


def test_reacao_aplica_taunt_no_turno_do_inimigo_vale_no_turno_seguinte():
    a, b = _actor("e"), _actor("player")
    actors = {"e": a, "player": b}
    before = orch._snapshot_conditions(actors)
    cm.apply_condition(a, _cond("taunt", "player"))  # reação do jogador no turno do inimigo
    orch._mark_fresh_conditions(before, actors, "e")
    out = {"logs": []}
    orch._tick_conditions_v4(a, out)  # início do PRÓXIMO turno do inimigo
    assert a["active_conditions"] and not out["logs"]


@pytest.mark.parametrize("ordem", ["hero_first"])
def test_presagio_on_congela_alvo_provocado_na_rodada_seguinte(ordem, monkeypatch):
    from services import enemy_intent as ei

    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    actors, scene, sides = _cena_devoto()
    orch.run_round(
        scene,
        actors,
        sides,
        {"player": actors["player"]},
        declarations={"player": _voto()},
        initiator=ORDENS[ordem],
        rng=_Rng0(1),
    )
    frozen = ei.forecast_round(scene, actors, sides, _Rng0(3))
    assert frozen["e"][0]["alvo_id"] == "player", frozen


def test_carta_bas_dev_voto_continua_sem_duracao_explicita():
    from services import cards

    assert "duracao" not in (cards.get_card("bas_dev_voto").get("efeito") or {})
