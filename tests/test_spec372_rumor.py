"""SPEC-372 R11 — rumor da trama: boost, portao do avistamento, portao de segredo intacto."""

from __future__ import annotations

import pytest

from services import fauna, fauna_tramas
from services import plot_threads as pt

CORPOS = "tr_na_corpos_marcados"
THR = pt.thread(CORPOS)
SEED = THR.rumor_ids[0]


@pytest.fixture
def flags(monkeypatch):
    for k in ("RPG_FAUNA", "RPG_FAUNA_SINAIS", "RPG_PLOT_THREADS", "RPG_FAUNA_TRAMAS"):
        monkeypatch.setenv(k, "on")
    pt.clear_cache()
    yield monkeypatch
    pt.clear_cache()


def _pres(**kw) -> dict:
    return {
        "fauna": {
            "presencas": [
                {
                    "pid": "p1",
                    "creature_id": "x",
                    "region_id": "nova_arcadia",
                    "status": "ativa",
                    "expires_day": 9,
                    **kw,
                }
            ]
        }
    }


def test_boost_dos_rumores_da_trama(flags):
    own = [
        ({"seed_id": SEED, "family": "lore"}, 1.0),
        ({"seed_id": "outra", "family": "lore"}, 1.0),
    ]
    out = fauna_tramas.rumor_adjust({}, _pres(trama_id=CORPOS), "nova_arcadia", 3, own)
    w = {s["seed_id"]: x for s, x in out}
    assert w[SEED] == fauna.const("RUMOR_BOOST") and w["outra"] == 1.0
    out = fauna_tramas.rumor_adjust({}, _pres(), "nova_arcadia", 3, own)  # sem trama_id
    assert [x for _s, x in out] == [1.0, 1.0]


def test_avistamento_dormente_pesa_zero(flags):
    real = fauna.load()
    cid = next(c for c, e in sorted(real.items()) if e.get("regiao") == "nova_arcadia")
    ent = {**real[cid], "tramas": [{"id": CORPOS, "desde": "tocada"}]}
    flags.setattr(fauna, "load", lambda: {**real, cid: ent})
    own = [({"seed_id": "av", "family": "avistamento", "entities": [cid]}, 1.0)]
    assert fauna_tramas.rumor_adjust({}, {}, "nova_arcadia", 3, own)[0][1] == 0.0
    st = {"world_sim": {"rumors": [{"rumor_id": "r", "seed_id": SEED, "perceived_day": 2}]}}
    assert fauna_tramas.rumor_adjust(st, {}, "nova_arcadia", 3, own)[0][1] == 1.0


def test_flag_off_nao_muda(flags):
    flags.setenv("RPG_FAUNA_TRAMAS", "off")
    own = [({"seed_id": SEED, "family": "lore"}, 1.0)]
    assert fauna_tramas.rumor_adjust({}, _pres(trama_id=CORPOS), "nova_arcadia", 3, own) is own


def test_portao_de_segredo_continua(flags):
    """O boost nao reabre semente bloqueada: `candidates` filtra o segredo antes do ajuste."""
    from services import rumors

    locked = next((sid for sid, s in rumors.load_seeds().items() if s.get("secret_id")), None)
    assert locked, "sem semente com secret_id"
    cands = rumors.candidates({"event_log": []}, _pres(trama_id=CORPOS), "nova_arcadia", 3)
    assert locked not in {s["seed_id"] for s, _w in cands}
