"""SPEC-203 Etapa 0 — reprodução determinística do bug de identidade do encontro.

Cada teste isola UMA hipótese (H1–H7). Os que reproduziram no HEAD pré-mudança
foram marcados `xfail(strict=True)` na Etapa 0 e convertidos a verdes pela
correção (registro em docs/spec203/repro.md). Offline: LLM stubado no módulo de
combate; IDs concretos vêm de data/bestiary.json.
"""

from __future__ import annotations

import random
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import agents.combat as combat
import encounter_budget as eb
import gamedata
import persistence

_LOC = "pantano_melancolia"
_BANDIT = "enemy_bandido"
_CROW = "mon_corvo_gelo"


class _Struct:
    def __init__(self, owner, schema):
        self.owner, self.schema = owner, schema

    def invoke(self, _messages):
        self.owner.calls.append((self.schema.__name__, self.owner.tier))
        if self.schema is combat.EncounterScanner and self.owner.scan is not None:
            return self.owner.scan
        raise RuntimeError("sem structured output neste stub")


class _FakeLLM:
    def __init__(self, calls, tier, scan=None, narration="O combate segue."):
        self.calls, self.tier, self.scan, self.narration = calls, tier, scan, narration
        self.is_fallback = False

    def with_structured_output(self, schema, **_kw):
        return _Struct(self, schema)

    def invoke(self, _messages):
        self.calls.append(("invoke", self.tier))
        return AIMessage(content=self.narration)


def _install_llm(monkeypatch, scan=None, narration="O combate segue."):
    calls: list = []
    monkeypatch.setattr(
        combat,
        "get_llm",
        lambda temperature=0.0, tier=None, **_kw: _FakeLLM(calls, tier, scan, narration),
    )
    return calls


def _scan(*groups, flavor="Eles surgem."):
    return combat.EncounterScanner(
        detected_enemies=[combat.EnemyIdentification(name=n, count=c) for n, c in groups],
        flavor_text=flavor,
    )


def _bestiary_factory(name, **_kw):
    """Factory determinística: nome → entrada curada do bestiário (sem LLM)."""
    folded = name.casefold()
    for bid, entry in gamedata.BESTIARY.items():
        if str(entry.get("name", "")).casefold() == folded:
            return {**entry, "id": bid}
    raise AssertionError(f"nome fora do bestiário no teste: {name}")


def _player():
    from services import conflict_orchestrator as orch

    player = {
        "name": "Kael",
        "class_name": "Devoto do Abismo",
        "level": 3,
        "virtudes": {"forca": 3, "agilidade": 2, "corpo": 5, "mente": 2, "carisma": 1},
        "inventory": [],
        "known_abilities": [],
        "active_conditions": [],
        "ability_cooldowns": {},
    }
    orch.ensure_combat_sheet(player, is_player=True)
    return player


def _world(danger=3):
    return {
        "current_location": "Pântano da Melancolia",
        "current_location_id": _LOC,
        "turn_count": 5,
        "danger_level": danger,
        "visited": [_LOC],
    }


def _start_state(hint="Bandido", **extra):
    state = {
        "game_id": "repro",
        "player": _player(),
        "enemies": [],
        "party": [],
        "combat": {},
        "combat_target": hint,
        "world": _world(),
        "messages": [
            HumanMessage(content="Sigo pela trilha do pântano."),
            SystemMessage(content=f"SYSTEM: COMBAT START. TARGET_HINT: {hint}"),
        ],
    }
    state.update(extra)
    return state


def _base(enemy_id: str) -> str:
    return re.sub(r"_\d+$", "", str(enemy_id))


# --- H1: scanner lê fauna da prosa ------------------------------------------
def test_h1_scanner_le_fauna_da_prosa(monkeypatch):
    """Prosa com bandidos + corvos e dica 'Bandido': o scanner (stub que repete a
    prosa) devolve só corvos; o elenco não pode perder o bandido."""
    random.seed(11)
    _install_llm(monkeypatch, scan=_scan(("Corvo de Gelo Negro", 3)))
    monkeypatch.setattr(combat, "generate_new_enemy", _bestiary_factory)
    state = _start_state(
        messages=[
            AIMessage(content="Bandidos saltam da mata; corvos grasnam nos galhos."),
            SystemMessage(content="SYSTEM: COMBAT START. TARGET_HINT: Bandido"),
        ]
    )
    enemies, _ = combat._spawn_v4_enemies(state["messages"], "Bandido", state)
    bases = {_base(e["id"]) for e in enemies}
    assert _BANDIT in bases
    assert _CROW not in bases


# --- H2: orçamento corta bandido por variedade e injeta fauna ---------------
def test_h2_budget_corta_bandido_e_injeta_fauna():
    bandits = [{**gamedata.BESTIARY[_BANDIT], "id": f"{_BANDIT}_{i}"} for i in (1, 2, 3)]
    crow = {**gamedata.BESTIARY[_CROW], "id": f"{_CROW}_1"}
    state = {
        "player": {"level": 1},
        "world": _world(danger=2),
        "party": [],
        "combat_target": "Bandido",
    }
    kept, _flavor = combat._apply_encounter_budget(bandits + [crow], state, "")
    bases = [_base(e["id"]) for e in kept]
    # Canônico (bandido, alvo resolvido) não é trocado por fauna via variedade.
    assert bases.count(_BANDIT) >= 2, bases


def test_h2b_fill_injeta_fauna_sem_evento(monkeypatch):
    """Reforço regional pode existir, mas só com evento `joined` registrado."""
    from services import encounter_manifest as em

    random.seed(5)
    _install_llm(monkeypatch)
    state = _start_state(
        player={**_player(), "level": 3},
        world=_world(danger=4),
        combat_encounter_hint={"enemy_id": _BANDIT, "reason": "random", "hint": "Bandido"},
    )
    out = combat.combat_node(state)
    manifest = out["combat"]["encounter"]
    joined = {ev["participant_id"] for ev in manifest["events"] if ev["kind"] == "joined"}
    for p in manifest["participants"]:
        if p["bestiary_id"] != _BANDIT:
            assert p["participant_id"] in joined
            assert p["presence"] == "arrived"
    assert em.validate_roster(manifest, out["enemies"]) == []


# --- H3: librarian mapeia "Bandido" para outra espécie ----------------------
def test_h3_librarian_dedupe_mapeia_outra_especie(monkeypatch):
    import agents.bestiary as bestiary

    _install_llm(monkeypatch, scan=_scan(("Bandido", 1)))
    monkeypatch.setattr(bestiary, "find_existing_entity", lambda *_a, **_k: _CROW)
    state = _start_state(hint="o grupo hostil")
    enemies, _ = combat._spawn_v4_enemies(state["messages"], "o grupo hostil", state)
    names = [e["name"] for e in enemies]
    assert all("Corvo" not in n for n in names), names
    assert any("Bandido" in n for n in names), names


# --- H4: enemy_id do encontro sistêmico é descartado ------------------------
def test_h4_enemy_id_sistemico_descartado(monkeypatch):
    random.seed(3)
    calls = _install_llm(monkeypatch, scan=_scan(("Lobo Sombrio", 2)))
    monkeypatch.setattr(combat, "generate_new_enemy", _bestiary_factory)
    state = _start_state(
        hint="Bandido",
        combat_encounter_hint={"enemy_id": _BANDIT, "reason": "random", "hint": "Bandido"},
    )
    enemies, _ = combat._spawn_v4_enemies(state["messages"], "Bandido", state)
    roster = {_base(e["id"]) for e in enemies}
    assert _BANDIT in roster and "enemy_lobo_sombrio" not in roster, roster
    # Fonte canônica: o scanner (CLASSIFY) nem é consultado.
    assert not [c for c in calls if c[0] == "EncounterScanner"]


def test_h4b_storyteller_propaga_enemy_id(monkeypatch):
    """Contrato storyteller→combat: o encontro sistêmico entrega `enemy_id`."""
    from agents import storyteller

    hint = storyteller.encounter_handoff(
        {"hint": "Bandido", "flavor": "x", "reason": "random", "enemy_id": _BANDIT}
    )
    assert hint == {"enemy_id": _BANDIT, "reason": "random", "hint": "Bandido"}


# --- H5: prosa renomeia sem mudar estado ------------------------------------
def test_h5_prosa_renomeia_sem_mudar_estado(monkeypatch):
    random.seed(7)
    _install_llm(
        monkeypatch,
        scan=_scan(("Bandido", 1)),
        narration="O corvo mergulha sobre você, bicando seu ombro.",
    )
    monkeypatch.setattr(combat, "generate_new_enemy", _bestiary_factory)
    out = combat.combat_node(_start_state())
    enemies = out["enemies"] or []
    assert enemies
    # Estado intacto: cada participante segue com a identidade do seu id
    # (a troca de espécie aqui é só narrativa).
    for e in enemies:
        assert gamedata.BESTIARY[_base(e["id"])]["name"] in e["name"]


def test_h5b_prose_guard_detecta_especie_divergente():
    from services import prose_guard

    manifest = {
        "participants": [
            {
                "participant_id": f"{_BANDIT}_1",
                "bestiary_id": _BANDIT,
                "species_label": "Bandido",
                "status": "ativo",
            }
        ]
    }
    flags = prose_guard.species_drift("O corvo mergulha e bica seu ombro.", manifest)
    assert flags and flags[0]["species"] == "corvo"
    assert prose_guard.species_drift("O Bandido avança com a faca.", manifest) == []


# --- H6: save/reload no meio do combate preserva elenco ---------------------
def test_h6_reload_preserva_elenco():
    import json
    import uuid

    gid = str(uuid.uuid4())
    enemies = [
        {
            **gamedata.BESTIARY[_BANDIT],
            "id": f"{_BANDIT}_{i}",
            "name": f"Bandido {i}",
            "status": "ativo",
        }
        for i in (1, 2)
    ]
    state = {
        "game_id": gid,
        "player": _player(),
        "world": _world(),
        "messages": [],
        "enemies": enemies,
        "combat": {"active": True, "round": 1},
    }
    raw = json.loads(json.dumps(persistence._state_to_save_data(state, gid), default=str))
    loaded = persistence._raw_to_state(raw)
    assert [(e["id"], e["name"]) for e in loaded["enemies"]] == [
        (e["id"], e["name"]) for e in enemies
    ]


# --- H7: inimigo ativo em alcance declara e causa dano ----------------------
def test_h7_inimigo_ativo_nao_causa_dano(monkeypatch):
    """Diagnóstico: inimigo ativo em alcance age na rodada e causa dano."""
    random.seed(1234)
    _install_llm(monkeypatch)
    enemy = {
        **gamedata.BESTIARY[_BANDIT],
        "id": f"{_BANDIT}_1",
        "name": "Bandido",
        "status": "ativo",
    }
    state = _start_state(enemies=[enemy])
    damage_seen = False
    for _ in range(6):
        state["combat_declaration"] = {"actor_id": "player", "acao": {"kind": "pass"}}
        before = int(state["player"].get("vitalidade", 0) or 0)
        out = combat.combat_node(state)
        assert "enemy" in (out["combat"].get("initiative") or [])
        if int(out["player"].get("vitalidade", 0) or 0) < before:
            damage_seen = True
            break
        if not out["combat"].get("active"):
            break
        state = {
            **state,
            **{k: v for k, v in out.items() if k != "messages"},
            "messages": state["messages"] + out["messages"],
        }
    assert damage_seen
