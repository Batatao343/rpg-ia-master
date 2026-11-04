"""SPEC-389 R1-R4/R6/R24-R26: toda omissao da oferta de retrato tem 1 causa; 1 `offer_view` por resposta;
`price_absent` fora do cache; snapshot do kill switch com idade maxima de 60 s."""

from __future__ import annotations

import sys
import types

import pytest

import api
from services import creature_art, portrait_offer
from services import kill_switches as ks

ENEMY = {"id": "enemy_goblin_1", "name": "Goblin", "categoria": "padrao"}


class _Repo:
    outcomes: list = []

    def __init__(self, *_a, **_k):
        pass

    def peek_ceiling(self, _kind):
        out = _Repo.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


@pytest.fixture
def price_env(monkeypatch):
    _Repo.outcomes = []
    monkeypatch.setitem(
        sys.modules, "services.image_quotes", types.SimpleNamespace(ImageQuoteRepository=_Repo)
    )
    rt = types.SimpleNamespace(resources=[object()])
    monkeypatch.setitem(
        sys.modules, "infrastructure.runtime", types.SimpleNamespace(get_runtime=lambda: rt)
    )
    monkeypatch.setitem(api._PORTRAIT_PRICE_CACHE, "at", 0.0)
    monkeypatch.setitem(api._PORTRAIT_PRICE_CACHE, "value", None)
    return _Repo


def test_price_absent_not_cached(price_env):
    price_env.outcomes = [None, 15]
    assert api._portrait_price_estilhas() is None
    assert api._PORTRAIT_PRICE_CACHE["at"] == 0.0 and api._PORTRAIT_PRICE_CACHE["value"] is None
    assert api._portrait_price_estilhas() == 1  # a próxima view tenta de novo
    price_env.outcomes = []  # preço válido fica em cache: sem nova leitura
    assert api._portrait_price_estilhas() == 1


def test_price_absent_cause_in_tally(price_env):
    price_env.outcomes = [0]
    portrait_offer.begin(True)
    assert api._portrait_price_estilhas() is None
    portrait_offer.record({"gerar": None}, [], True, None)
    assert portrait_offer.finish()["omitted"] == {"price_absent": 1}


@pytest.mark.parametrize(
    ("portrait", "reasons", "live", "art", "gate", "expected"),
    [
        ({"gerar": {"preco_estilhas": 1}}, [], True, None, "", None),
        ({"gerar": None}, ["fallback_enemy"], True, None, "", "fallback_enemy"),
        ({"gerar": None}, ["private_other_game", "pending"], True, None, "", "private_other_game"),
        ({"gerar": None}, ["pending"], True, None, "", "pending"),
        ({"gerar": None}, ["has_own_art"], True, None, "", "has_own_art"),
        ({"gerar": None}, [], False, "art_not_live:profile", "", "art_not_live:profile"),
        ({"gerar": None}, [], False, None, "registry_read_failed", "registry_read_failed"),
        ({"gerar": None}, [], True, None, "switch_off", "switch_off"),
        ({"gerar": None}, [], True, None, "switches_stale", "switches_stale"),
        ({"gerar": None}, [], True, None, "", "price_absent"),
    ],
)
def test_every_omission_has_one_cause(portrait, reasons, live, art, gate, expected):
    portrait_offer.begin(live)
    if gate:
        portrait_offer.note_gate(gate)
    assert portrait_offer.classify(portrait, reasons, live, art) == expected
    assert expected is None or expected in portrait_offer.OFFER_CAUSES
    portrait_offer.finish()


class _Switches:
    def __init__(self, on=True, *, stale=False, unreadable=False):
        self.on, self.stale, self.unreadable, self.age_s = on, stale, unreadable, 2.5

    def is_enabled(self, key):
        return self.on


@pytest.mark.parametrize(
    ("switches", "cause"),
    [
        (_Switches(False), "switch_off"),
        (_Switches(False, stale=True), "switches_stale"),
        (_Switches(False, unreadable=True), "switches_unreadable"),
    ],
)
def test_gate_causes(monkeypatch, switches, cause):
    monkeypatch.setattr(ks, "get_switches", lambda: switches)
    portrait_offer.begin(True)
    assert portrait_offer.gate() == (False, cause)
    portrait_offer.finish()


def test_gate_env_off(monkeypatch):
    monkeypatch.setattr(ks, "get_switches", lambda: _Switches(False))
    monkeypatch.setenv("RPG_KILL_SWITCHES_OFF", "image_generation")
    assert portrait_offer.gate() == (False, "env_off")


def test_art_cause(monkeypatch):
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1")
    assert portrait_offer.art_cause(False, True) == "art_not_live:flag"
    assert portrait_offer.art_cause(True, False) == "art_not_live:profile"
    assert portrait_offer.art_cause(True, True) is None
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "0")
    assert portrait_offer.art_cause(True, True) == "art_not_live:dynamic_art"


def _registry(value):
    def _fake(*_a, **_k):
        portrait_offer.begin(value is not None)  # o real abre o tally da resposta
        return value

    return _fake


def _wire_live(monkeypatch, *, switch: bool, price):
    monkeypatch.setattr(ks, "get_switches", lambda: _Switches(switch))
    import services.finops_alerts as fa

    monkeypatch.setattr(fa, "require_paid_effect", lambda *a, **k: None)
    monkeypatch.setattr(api, "_portrait_price_estilhas", lambda: price)
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", "1")
    monkeypatch.setattr(creature_art, "mode", lambda: "on")
    monkeypatch.setattr(api, "_portrait_registry", _registry(creature_art.EmptyRegistry()))


def _combat_state(n=2):
    enemies = [{**ENEMY, "id": f"enemy_goblin_{i}"} for i in range(n)]
    return {"game_id": "g389", "player": {}, "enemies": enemies, "combat": {"active": True}}


def test_offer_view_once_per_response(monkeypatch):
    _wire_live(monkeypatch, switch=False, price=3)
    seen = []
    monkeypatch.setattr(portrait_offer, "log_event", lambda *a, **k: seen.append((a, k)))
    api._combat_block(_combat_state(2))
    assert len(seen) == 1
    (args, kw) = seen[0]
    assert args == ("creature_portrait", "offer_view")
    assert kw["omitted"] == {"switch_off": 2} and kw["offered"] == 0
    assert kw["level"] == "warning" and kw["art_live"] is True
    assert kw["instance"] == portrait_offer.INSTANCE and kw["switch_age_s"] == 2.5
    assert "game_id" not in kw  # só game_ref (pseudônimo)


def test_offer_view_levels(monkeypatch):
    _wire_live(monkeypatch, switch=True, price=3)
    seen = []
    monkeypatch.setattr(portrait_offer, "log_event", lambda *a, **k: seen.append(k))
    api._combat_block(_combat_state(1))
    assert seen[0]["offered"] == 1 and seen[0]["omitted"] == {} and seen[0]["level"] == "info"
    monkeypatch.setattr(api, "_portrait_registry", _registry(None))
    monkeypatch.setattr(api, "_creature_art_live", lambda: False)
    monkeypatch.setattr(api, "_database_profile", lambda: False)
    api._combat_block(_combat_state(1))
    assert seen[1]["omitted"] == {"art_not_live:profile": 1} and seen[1]["level"] == "info"


# --- R4: kill switch com idade e log estruturado --------------------------------------------


class _Clock:
    now = 1000.0

    def __call__(self):
        return self.now


class _Store:
    def __init__(self):
        self.value = {"image_generation": False}
        self.fail = False

    def load(self):
        if self.fail:
            raise RuntimeError("db down")
        return dict(self.value)


@pytest.fixture
def sw(monkeypatch):
    monkeypatch.setenv("RPG_KILL_SWITCH_FAIL_CLOSED", "image_generation")
    clock, store = _Clock(), _Store()
    return ks.KillSwitches(store, ttl=5, clock=clock), clock, store


def test_switch_recovers_on_within_ttl(sw):
    switches, clock, store = sw
    assert switches.is_enabled(ks.IMAGE) is False
    store.value = {"image_generation": True}
    clock.now += 5
    assert switches.is_enabled(ks.IMAGE) is True
    assert switches.age_s == 0.0


def test_switch_stale_after_60s_fail_closed(sw):
    switches, clock, store = sw
    store.value = {"image_generation": True}
    assert switches.is_enabled(ks.IMAGE) is True
    store.fail = True
    clock.now += 30
    assert switches.is_enabled(ks.IMAGE) is True  # 30 s: mantém o snapshot bom
    assert not switches.stale
    clock.now += 31
    assert switches.is_enabled(ks.IMAGE) is False  # 61 s: fail-closed
    assert switches.stale and not switches.unreadable
    store.fail = False
    clock.now += 5
    assert switches.is_enabled(ks.IMAGE) is True and not switches.stale


def test_switch_age_and_structured_log(sw, monkeypatch):
    switches, clock, store = sw
    seen = []
    monkeypatch.setattr(ks, "log_event", lambda *a, **k: seen.append((a, k)))
    switches.snapshot()
    store.fail = True
    clock.now += 7
    switches.snapshot()
    ((args, kw),) = seen
    assert args == ("kill_switches", "load_failed")
    assert kw["error_class"] == "RuntimeError" and kw["snapshot_age_s"] == 7.0
    assert kw["level"] == "warning"


def test_gate_reports_stale_cause(sw, monkeypatch):
    switches, clock, store = sw
    store.value = {"image_generation": True}
    switches.snapshot()
    store.fail = True
    clock.now += 100
    monkeypatch.setattr(ks, "get_switches", lambda: switches)
    portrait_offer.begin(True)
    assert portrait_offer.gate() == (False, "switches_stale")
    portrait_offer.finish()


# --- R5: script de medicao (logs falsos) -----------------------------------------------------


def _log_line(rid, **fields):
    import json

    payload = {"event": "creature_portrait.offer_view", "request_id": rid, **fields}
    return json.dumps({"data": {"message": "INFO " + json.dumps(payload)}})


def test_measure_join_by_request_id():
    from scripts.staging import portrait_offer_measure as m

    logs = m.parse_logs(
        "\n".join(
            [
                _log_line("r1", instance="a", offered=0, omitted={"switch_off": 1}),
                _log_line("r2", instance="b", offered=1, omitted={}),
                "lixo",
            ]
        )
    )
    samples = [
        {"request_id": "r1", "gerar": False, "kind": "api"},
        {"request_id": "r2", "gerar": True, "kind": "browser:390"},
    ]
    joined = m.join_samples(samples, logs)
    assert joined[0]["offer_view"]["omitted"] == {"switch_off": 1}
    summary = m.summarize(joined)
    assert summary["with_offer"] == 1 and summary["causes"] == {"switch_off": 1}
    assert set(summary["per_instance"]) == {"a", "b"}


def test_measure_fails_without_offer_view():
    from scripts.staging import portrait_offer_measure as m

    joined = m.join_samples([{"request_id": "zzz", "gerar": False}], [])
    assert len(m.missing_views(joined)) == 1


# --- R22/R24: guardas de pouso (só valem na branch da spec; depois outras specs mexem nesses arquivos) ---


def _diff_names(*paths: str) -> list[str]:
    import shutil
    import subprocess
    from pathlib import Path

    git, root = shutil.which("git"), Path(__file__).resolve().parents[1]
    if git is None or not (root / ".git").exists():
        pytest.skip("sem git")

    def run(*a):
        return subprocess.run([git, *a], cwd=root, capture_output=True, text=True).stdout.strip()

    if run("rev-parse", "--abbrev-ref", "HEAD") != "spec-389":
        pytest.skip("guarda da SPEC-389: só na branch spec-389")
    base = run("merge-base", "main", "HEAD")
    if not base:
        pytest.skip("merge-base com a main indisponível")
    return [x for x in run("diff", "--name-only", base, "HEAD", "--", *paths).splitlines() if x]


def test_spec389_integrity_and_no_new_flag():
    assert (
        _diff_names(
            "tests/spec330_equivalence.py",
            "tests/fixtures/spec330_legacy_golden.json",
            "evals",
            "web/e2e/contracts",
            "scripts/cards/lint.py",
            "scripts/cards/sim.py",
            "scripts/cards/promote.py",
            "config/flags.yaml",
            "scripts/staging/staging_flags.json",
        )
        == []
    )


# --- Sol P1-1/P1-2: script de medição ----------------------------------------------------------


class _Proc:
    def __init__(self, out, rc=0):
        self.stdout, self.returncode = out, rc


def test_measure_switch_snapshot_uses_staging_dsn_and_filters(monkeypatch):
    import json

    from scripts.staging import portrait_offer_measure as m

    calls = []

    def fake(cmd, **kw):
        calls.append(cmd)
        if "list" in cmd:
            return _Proc(json.dumps({"a": True, "image_generation": True}))
        rows = [
            {
                "key": "model:x",
                "enabled": False,
                "previous_enabled": True,
                "actor_id": "a",
                "reason": "r",
                "created_at": "t0",
            },
            *[
                {
                    "key": "image_generation",
                    "enabled": i % 2 == 0,
                    "previous_enabled": i % 2 == 1,
                    "actor_id": "secret",
                    "reason": "secret",
                    "created_at": f"t{i}",
                }
                for i in range(1, 8)
            ],
        ]
        return _Proc(json.dumps(rows))

    snap = m.switches_snapshot(run=fake)
    assert all(
        "--dsn-env" in c and "RPG_STAGING_DB_URL" in c and ".env.staging" in c for c in calls
    )
    assert snap["image_generation"] is True
    assert len(snap["audit"]) == 5 and all(
        set(r) == {"key", "previous_enabled", "enabled", "created_at"} for r in snap["audit"]
    )
    assert {r["key"] for r in snap["audit"]} == {"image_generation"}
    assert "secret" not in json.dumps(snap)


def test_measure_switch_snapshot_fails_on_error():
    from scripts.staging import portrait_offer_measure as m

    with pytest.raises(RuntimeError):
        m.switches_snapshot(run=lambda cmd, **kw: _Proc("", 2))


def test_measure_sample_uses_real_game_and_path():
    from scripts.staging import portrait_offer_measure as m

    sample = m.sample_from(
        "browser:390",
        "https://x.test/game/state?game_id=zzz",
        {"x-request-id": "r"},
        200,
        {"game_id": "real-game"},
    )
    assert sample["game"] == m.short_hash("real-game") != m.short_hash("arg-game")
    assert sample["endpoint"] == "/game/state"


def test_measure_problems_require_both_sides():
    from scripts.staging import portrait_offer_measure as m

    ok = {"status": 200, "request_id": "r"}
    api_only = [{**ok, "kind": "api"}] * 6
    assert m.count_problems(api_only, 6, 6)  # navegador sem resposta
    full = api_only + [{**ok, "kind": "browser:1440"}] * 6
    assert m.count_problems(full, 6, 6) == []
    assert m.count_problems(full[:-1] + [{**ok, "kind": "browser:1440", "status": 500}], 6, 6)


# --- Sol P2-1/P2-2/P2-3/P2-4 ----------------------------------------------------------------


class _Rows:
    def __init__(self, row):
        self.row = row

    def get(self, key):
        return self.row if key.startswith("tipo:") else None


def _real_cause(monkeypatch, *, curated: bool, row):
    monkeypatch.setattr(creature_art, "mode", lambda: "on")
    monkeypatch.setattr(
        creature_art,
        "_curated",
        lambda kind, ident: "c.png" if curated and kind == "creature" else None,
    )
    reasons: list[str] = []
    portrait = creature_art.portrait_for(
        ENEMY, None, game_id="g", registry=_Rows(row), quote_price=3, reasons=reasons
    )
    portrait_offer.begin(True)
    return portrait_offer.classify(dict(portrait), reasons, True, None)


def test_classify_precedence_with_real_portrait_for(monkeypatch):
    private = {
        "status": "ready",
        "store": "private",
        "origin_game_id": "other",
        "visibility": "shared",
    }
    assert _real_cause(monkeypatch, curated=True, row=private) == "has_own_art"
    assert _real_cause(monkeypatch, curated=False, row=private) == "private_other_game"
    pending = {"status": "pending", "visibility": "shared"}
    assert _real_cause(monkeypatch, curated=False, row=pending) == "pending"
    portrait_offer.finish()


def test_no_offer_view_without_alive_enemy(monkeypatch):
    _wire_live(monkeypatch, switch=True, price=3)
    monkeypatch.undo()  # usa o _portrait_registry real: sem inimigo vivo ele não abre tally
    seen = []
    monkeypatch.setattr(portrait_offer, "log_event", lambda *a, **k: seen.append(k))
    api._combat_block({"game_id": "g", "player": {}, "enemies": [], "combat": {"active": True}})
    assert seen == []


def test_instance_is_the_boot_instance_ref():
    from observability.boot import INSTANCE_REF

    assert portrait_offer.INSTANCE == INSTANCE_REF


def test_art_live_single_source(monkeypatch):
    for mode_on in (True, False):
        for db in (True, False):
            for env in ("1", "0"):
                monkeypatch.setenv("RPG_DYNAMIC_ART_ENABLED", env)
                monkeypatch.setattr(creature_art, "mode", lambda m=mode_on: "on" if m else "off")
                monkeypatch.setattr(api, "_database_profile", lambda d=db: d)
                assert api._creature_art_live() is (portrait_offer.art_cause(mode_on, db) is None)
