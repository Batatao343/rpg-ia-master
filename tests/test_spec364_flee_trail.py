"""SPEC-364 R1-R3: a fuga tem uma trilha so, sem ids crus."""

from __future__ import annotations

import re

import agents.combat as combat
from agents.combat import _attempt_flee
from services import chase
from services import combat_preview as cp

_ID_RE = re.compile(r"\b(alcancado|quase_livre)\b")


class _HighRng:
    def randint(self, a, b):
        return b


class _LowRng:
    def randint(self, a, b):
        return a


def _scene(distance="proximo"):
    return {"positions": {"player": {"distance_state": distance}}}


def _player():
    return {"name": "Valen", "conscious": True, "virtudes": {"agilidade": 5}}


def _enemy():
    return {"id": "lobo", "name": "Lobo", "pursuit_policy": "persegue", "virtudes": {"agilidade": 0}}


def _flee(existing, rng, scene=None, **kw):
    return _attempt_flee(scene or _scene(), _player(), [_enemy()], {}, rng, existing_chase=existing, **kw)


def test_two_flees_same_trail():
    fled, _logs, st1 = _flee(None, _LowRng())
    assert st1["alcancado"] is True and not fled
    # 2a fuga: a perseguicao reinicia em "pressionado" e avanca
    fled, logs, st2 = _flee(st1, _HighRng())
    assert st2["_last"]["de"] == "pressionado"
    assert st2["trilha"] == "afastado"
    payload = combat._flee_roll_payload(st2, "alcancado", fled)
    assert payload["de"] == "pressionado" and payload["para"] == "afastado"
    assert payload["veredito"] == "avancou"
    mech = cp._flee_line({"fuga": payload})
    assert mech == "Fuga · total 20 vs 12 · avança (pressionado → afastado)" or "pressionado → afastado" in mech
    assert "pressionado → afastado" in " ".join(logs)
    assert not _ID_RE.search(mech + " ".join(logs))


def test_first_flee_from_distant_starts_afastado():
    fled, logs, st = _flee(None, _HighRng(), scene=_scene("distante"))
    assert st["_last"]["de"] == "afastado"
    payload = combat._flee_roll_payload(st, "pressionado", fled)
    assert payload["de"] == "afastado"
    assert "afastado → quase livre" in " ".join(logs)


def test_lose_ground_and_escape_trails():
    start = {
        "trilha": "afastado",
        "perseguidores": ["lobo"],
        "fugitive_id": "player",
        "alcancado": False,
        "escapou": False,
    }
    fled, logs, st = _flee(start, _LowRng())
    assert st["_last"]["de"] == "afastado" and st["trilha"] == "pressionado"
    assert combat._flee_roll_payload(st, "afastado", fled)["veredito"] == "perdeu_terreno"
    near = {**start, "trilha": "quase_livre"}
    fled, _logs, st = _flee(near, _HighRng())
    assert fled is True and st["_last"]["de"] == "quase_livre"
    payload = combat._flee_roll_payload(st, "quase_livre", fled)
    assert payload["veredito"] == "escapou"


def test_force_escape_trail():
    start = {
        "trilha": "afastado",
        "perseguidores": ["lobo"],
        "fugitive_id": "player",
        "alcancado": False,
        "escapou": False,
    }
    fled, _logs, st = _flee(start, _HighRng(), force_escape=True)
    assert fled is True
    assert st["_last"]["de"] == "afastado"


def test_old_save_fallback_uses_prev_track():
    st = {"trilha": "afastado", "_last": {"total": 14, "difficulty": 12, "sucesso": True}}
    payload = combat._flee_roll_payload(st, "pressionado", False)
    assert payload["de"] == "pressionado"


def test_track_label_never_returns_id():
    assert chase.track_label("alcancado") == "alcançado"
    assert chase.track_label("quase_livre") == "quase livre"
    assert chase.track_label("lixo_interno") == ""
    assert chase.track_label(None) == ""
    line = cp._flee_line(
        {"fuga": {"total": 3, "dificuldade": 12, "veredito": "avancou", "de": "lixo_interno", "para": "afastado"}}
    )
    assert "lixo_interno" not in line and "(" not in line


def test_no_track_ids_anywhere():
    alc = cp._flee_line(
        {"fuga": {"total": 3, "dificuldade": 12, "veredito": "alcancado", "de": "pressionado", "para": "alcancado"}}
    )
    assert not _ID_RE.search(alc)
