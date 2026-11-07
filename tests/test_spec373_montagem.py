"""SPEC-373 R2/R9/R10: família como tempero para criatura autoral; população da 332 e `off` intactos."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agents.bestiary import load_bestiary
from services import conflict_orchestrator as orch
from services import enemy_decks as edk
from services import tactical_profile as tp

BASE = Path(__file__).resolve().parents[1] / "docs" / "spec373" / "base"


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.delenv("RPG_ENEMY_DECKS", raising=False)
    edk.reload()
    yield
    edk.reload()


def _autorais() -> dict[str, dict]:
    return {k: v for k, v in load_bestiary().items() if edk._autoral({**v, "id": k})}


def _sig_ids(entry: dict) -> set[str]:
    return {str(s["carta"]) for s in edk._signature_configs(entry)}


def _hash(sheet: dict) -> str:
    blob = json.dumps(sheet, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# Valor do ``action_key`` da prioridade ``absoluta`` na base da 373 (antes da R1 da SPEC-395).
ACTION_KEY_BASE = "flee"


def chave_absoluta_esperada(arquetipo: str) -> str | None:
    """Oráculo da R3 da 395 pela tabela (SPEC-400 D2, não pelo ``normalize_runtime_profile``).

    A ``absoluta`` sai com a chave de ``sempre`` do arquétipo, ou ``attack`` quando ela falta
    ou também é fuga/rendição. ``None``: arquétipo fora da tabela."""
    acoes = tp._ENEMY_ARCHETYPE_ACTIONS.get(arquetipo)
    if acoes is None:
        return None
    chave = acoes.get("sempre", "attack")
    return "attack" if chave in ("flee", "surrender") else chave


def ficha_vs_base(sheet: dict, base_hash: str) -> list[str]:
    """Id em ``fichas``: só o ``action_key`` das prioridades ``absoluta`` pode ter mudado.

    Devolve esse campo ao valor da base e exige o hash da 373; o resto da ficha (HP, cartas,
    dano, perfil) segue travado. Também exige que a chave nova seja a esperada pela tabela
    para ``sheet["arquetipo"]`` (SPEC-400 R4), e não só "qualquer uma que não seja fuga"."""
    restaurada = json.loads(json.dumps(sheet, default=str))
    prios = (restaurada.get("tactical_profile") or {}).get("priorities") or []
    absolutas = [p for p in prios if p.get("resistance") == "absoluta"]
    if not absolutas:
        return ["sem prioridade absoluta (a id não devia estar em fichas)"]
    esperada = chave_absoluta_esperada(str(sheet.get("arquetipo") or ""))
    if esperada is None:
        return [f"arquetipo fora da tabela: {sheet.get('arquetipo')!r}"]
    erros = [
        f"absoluta mapeia para {p.get('action_key')}, esperado {esperada}"
        for p in absolutas
        if p.get("action_key") != esperada
    ]
    for p in absolutas:
        p["action_key"] = ACTION_KEY_BASE
    if _hash(restaurada) != base_hash:
        erros.append("ficha mudou além do action_key da absoluta")
    return erros


def test_ficha_vs_base_known_good_e_bad():
    base = {
        "hp": 12,
        "arquetipo": "conjurador",
        "tactical_profile": {
            "priorities": [
                {"resistance": "absoluta", "action_key": "flee"},
                {"resistance": "flexivel", "action_key": "attack"},
            ]
        },
    }
    h = _hash(base)
    fixed = json.loads(json.dumps(base))
    fixed["tactical_profile"]["priorities"][0]["action_key"] = "control"
    assert ficha_vs_base(fixed, h) == []
    assert ficha_vs_base({**fixed, "hp": 99}, h) == ["ficha mudou além do action_key da absoluta"]
    flex = json.loads(json.dumps(fixed))
    flex["tactical_profile"]["priorities"][1]["action_key"] = "flee"
    assert ficha_vs_base(flex, h)  # só a absoluta pode mudar
    sem_correcao = ["absoluta mapeia para flee, esperado control"]
    assert ficha_vs_base(base, h) == sem_correcao
    rend = json.loads(json.dumps(fixed))
    rend["tactical_profile"]["priorities"][0]["action_key"] = "surrender"
    assert ficha_vs_base(rend, h)
    assert ficha_vs_base({"hp": 12}, h)  # sem absoluta


def test_ficha_vs_base_exige_chave_de_sempre_do_arquetipo():
    """SPEC-400 R4 (P2-7 da 395): a absoluta corrigida tem de sair com a chave de ``sempre``.

    Antes, qualquer chave fora de fuga/rendição passava (a M9, odre com ``flank``, passava)."""
    base = {
        "hp": 12,
        "arquetipo": "conjurador",
        "tactical_profile": {
            "priorities": [
                {"resistance": "absoluta", "action_key": "flee"},
                {"resistance": "flexivel", "action_key": "attack"},
            ]
        },
    }
    h = _hash(base)
    flank = json.loads(json.dumps(base))
    flank["tactical_profile"]["priorities"][0]["action_key"] = "flank"
    assert ficha_vs_base(flank, h) == ["absoluta mapeia para flank, esperado control"]
    # arquétipo com ``sempre`` = attack: attack passa, control (de outro arquétipo) reprova
    abissal = {**json.loads(json.dumps(base)), "arquetipo": "abissal"}
    h_abissal = _hash(abissal)
    abissal["tactical_profile"]["priorities"][0]["action_key"] = "attack"
    assert ficha_vs_base(abissal, h_abissal) == []
    abissal["tactical_profile"]["priorities"][0]["action_key"] = "control"
    assert ficha_vs_base(abissal, h_abissal)
    # sem arquétipo da tabela não há chave esperada: reprova em vez de aceitar qualquer uma
    fora = {**json.loads(json.dumps(base)), "arquetipo": "inventado"}
    fora["tactical_profile"]["priorities"][0]["action_key"] = "control"
    assert ficha_vs_base(fora, _hash({**base, "arquetipo": "inventado"}))
    assert chave_absoluta_esperada("covarde_oportunista") == "flank"
    assert chave_absoluta_esperada("guardiao") == "attack"
    assert chave_absoluta_esperada("inventado") is None


def test_snapshot_off_existe_e_bate(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "off")
    snap = json.loads((BASE / "snapshot-off.json").read_text("utf-8"))
    bestiary = load_bestiary()
    assert set(snap) == set(bestiary)
    recal = set(json.loads((BASE.parent / "recalibradas.json").read_text("utf-8")))  # R8
    # Recalibrações de specs posteriores (registro protegido, validado em test_spec373_artefatos).
    reg = BASE.parents[1] / "bestiario" / "recalibracoes_posteriores.json"
    registro = json.loads(reg.read_text("utf-8"))
    recal |= set(registro["recalibracoes"])
    # ``fichas``: regra de produto de spec posterior, sem dial. Não pula a id: compara com a base
    # da 373 depois de devolver só o ``action_key`` da ``absoluta`` (adendo §12).
    fichas = set(registro.get("fichas", {}))
    for bid, entry in bestiary.items():
        if bid in recal:
            continue
        sheet = orch.ensure_combat_sheet({**json.loads(json.dumps(entry)), "id": bid})
        if bid in fichas:
            assert ficha_vs_base(sheet, snap[bid]) == [], bid
        else:
            assert _hash(sheet) == snap[bid], bid


def test_autoral_sem_assinatura_da_familia(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    pop = _autorais()
    assert len(pop) >= 200
    for bid, entry in pop.items():
        for seed in range(4):
            deck = edk.build_enemy_deck({**entry, "id": bid}, seed)
            assert not (set(deck) & _sig_ids(entry)), (bid, seed)


def test_autoral_familia_1_ou_2(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    pools = edk._pools()
    for bid, entry in _autorais().items():
        fam = edk.family_key(entry)
        if not fam:
            continue
        for seed in range(6):
            creature = {**entry, "id": bid}
            deck = edk.build_enemy_deck(creature, seed)
            n = len(set(deck) & set(pools["familias"].get(fam, [])))
            assert 0 <= n <= 2, (bid, seed, n)
            assert deck == edk.build_enemy_deck(creature, seed)
    assert any(
        len(
            set(edk.build_enemy_deck({**e, "id": b}, 0))
            & set(pools["familias"].get(edk.family_key(e), []))
        )
        >= 1
        for b, e in _autorais().items()
    )


def test_populacao_332_identica(monkeypatch):
    """R9: a regra de montagem não muda a população da 332. As Cartas novas da R14
    (`origem: cartas-373`) mudam os pools de propósito, então a identidade vale com os
    pools da `main` (sem elas)."""
    from services import cards

    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    pools = edk._pools()
    novas = {
        c
        for ids in pools["familias"].values()
        for c in ids
        if (cards.get_card(c) or {}).get("origem") == "cartas-373"
    }
    main_fams = {f: [c for c in ids if c not in novas] for f, ids in pools["familias"].items()}
    monkeypatch.setattr(edk, "_pools_cache", {"familias": main_fams, "faccoes": pools["faccoes"]})
    fixture = json.loads((BASE / "deck-332-main.json").read_text("utf-8"))
    bestiary = load_bestiary()
    assert fixture
    for bid, decks in fixture.items():
        entry = {**bestiary[bid], "id": bid}
        assert [edk.build_enemy_deck(entry, s) for s in range(12)] == decks, bid


def test_save_antigo_nao_remonta(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    bid, entry = next(iter(_autorais().items()))
    fam = edk.family_key(entry)
    pool = [c for c in edk._pools()["familias"][fam] if c not in _sig_ids(entry)]
    # baralho antigo (3-5 da família) sem marcador: não remonta
    old = {
        **json.loads(json.dumps(entry)),
        "id": bid + "_1",
        "cartas": [*edk._own_ids(entry), *pool[:4]],
    }
    got = [c for c in orch.ensure_combat_sheet(old)["cartas"] if c.startswith("inf_")]
    assert got == pool[:4]
    # montado pelo R9 (1 carta de pool), sem marcador: também não remonta
    one = {
        **json.loads(json.dumps(entry)),
        "id": bid + "_1",
        "cartas": [*edk._own_ids(entry), pool[0]],
    }
    got = [c for c in orch.ensure_combat_sheet(one)["cartas"] if c.startswith("inf_")]
    assert got == [pool[0]]


def test_round_trip_save_load_on(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    bid = "mon_borda_que_anda"
    e = orch.ensure_combat_sheet({**json.loads(json.dumps(load_bestiary()[bid])), "id": bid + "_1"})
    e["fase_idx"] = 1
    before = list(e["cartas"])
    assert e.get("_deck332")
    again = orch.ensure_combat_sheet(json.loads(json.dumps(e)))
    assert again["cartas"] == before and again["fase_idx"] == 1
    stripped = json.loads(json.dumps(e))
    stripped.pop("_deck332")
    assert orch.ensure_combat_sheet(stripped)["cartas"] == before


def test_autoral_sem_carta_dos_pools_no_template():
    """P2-4 (Sol): R10 conta 1 Carta dos pools como 'já montada'; nenhuma autoral pode ter
    uma no template do bestiário, senão pularia a montagem da família."""
    pools = edk._pools()
    known = {c for ids in (*pools["familias"].values(), *pools["faccoes"].values()) for c in ids}
    sujas = {
        cid: sorted(known & set(e.get("cartas") or []))
        for cid, e in _autorais().items()
        if known & set(e.get("cartas") or [])
    }
    assert sujas == {}
