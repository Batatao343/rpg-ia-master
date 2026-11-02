"""SPEC-364 R2/R3/R24: a fuga mostra o mesmo `de -> para` nas superficies (mech_log, round_board, mensagem,
Livro `/game/history`), sem ids da trilha, e a rodada nao chama LLM. Estado semeado, sem depender de sorte."""

from __future__ import annotations

import random
import re
from copy import deepcopy

import pytest

from tests import spec364_board_helpers as hp

ID_RE = re.compile(r"\b(alcancado|quase_livre)\b")
TRAIL_RE = re.compile(r"\((\w[\w çãé]*) → (\w[\w çãé]*)\)")


def _chase(trilha: str, **extra) -> dict:
    base = {
        "trilha": trilha,
        "fugitive_id": "player",
        "alcancado": trilha == "alcancado",
        "escapou": False,
    }
    return {**base, **extra}


def _flee(monkeypatch, *, chase=None, distance=None, want_success: bool, escape: bool = False):
    client, saved, gid = hp.api_client(monkeypatch)
    st = hp.open_combat(client, saved, gid)
    ids = [e["id"] for e in st["enemies"] if not e.get("dead")]
    for enemy in st["enemies"]:
        enemy["pursuit_policy"] = "persegue"
    # Cartas de Cena (R24): condicao e Carga disparam no fim da rodada 1
    st["combat"]["scene"]["cartas_de_cena"] = [
        "nevoa_cinza_do_ermo",
        "vigilia_dos_druidas_cinzentos",
    ]
    if chase is not None:
        st["combat"]["chase"] = {**chase, "perseguidores": ids}
    if distance:
        st["combat"]["scene"]["positions"]["player"]["distance_state"] = distance
    saved[gid] = deepcopy(st)
    # contador de LLM: delega ao Mock e conta; so a ultima rodada (desfecho) pode chamar a IA
    import importlib

    calls: list[str] = []
    for name in (
        "agents.combat",
        "agents.router",
        "agents.loot",
        "agents.npc",
        "agents.storyteller",
        "agents.archivist",
        "agents.campaign_manager",
        "services.death_flow",
    ):
        mod = importlib.import_module(name)
        if hasattr(mod, "get_llm"):
            real = mod.get_llm

            def counting(*a, _real=real, _name=name, **k):
                calls.append(_name)
                return _real(*a, **k)

            monkeypatch.setattr(mod, "get_llm", counting)
    for seed in range(200):
        snapshot = deepcopy(saved[gid])
        calls.clear()
        random.seed(seed)
        r = client.post(
            "/game/action", json={"game_id": gid, "input_text": "Fugir", "action_kind": "flee"}
        )
        assert r.status_code == 200, r.text
        log_lines = (
            r.json()["combat"].get("mech_log")
            or (saved[gid].get("combat") or {}).get("last_mech_log")
            or []
        )
        fuga = [ln for ln in log_lines if ln.startswith("Fuga ·")]
        if escape:  # escapar encerra o conflito: o tabuleiro fecha, sem linha de trilha
            ok = not r.json()["combat"].get("active")
            ok = ok and bool(fuga)  # P3-9: o mech_log salvo traz a linha de trilha do escape
        else:
            ok = bool(fuga) and (
                ("avança" in fuga[0] or "escapou" in fuga[0])
                if want_success
                else "perde terreno" in fuga[0]
            )
        if ok:
            if r.json()["combat"].get("active"):
                assert calls == [], calls  # R24: rodada de meio de luta, zero LLM
            hist = client.get("/game/history", params={"game_id": gid}).json()["entries"]
            return r.json(), hist, fuga[0]
        saved[gid] = snapshot  # tenta outra semente a partir do mesmo estado
    pytest.fail("nenhuma semente produziu o desfecho pedido")


def _surfaces(resp, hist):
    combat = resp["combat"]
    board = " | ".join(str(e) for e in (combat.get("registro_rodada") or []))
    return {
        "mech_log": " | ".join(combat.get("mech_log") or []),
        "round_board": board,
        "mensagem": resp["message"],
        "livro": "\n".join(str(e.get("text") or "") for e in hist),
    }


@pytest.mark.parametrize(
    ("label", "chase", "distance", "success", "de", "para"),
    [
        ("a_alcancado_depois_avanca", _chase("alcancado"), None, True, "pressionado", "afastado"),
        ("b_primeira_fuga_distante", None, "distante", True, "afastado", "quase livre"),
        ("c_perde_terreno", _chase("afastado"), None, False, "afastado", "pressionado"),
        ("d_escapa", _chase("quase_livre"), None, True, "quase livre", "livre"),
    ],
)
def test_same_trail_on_every_surface(monkeypatch, label, chase, distance, success, de, para):
    resp, hist, line = _flee(
        monkeypatch,
        chase=chase,
        distance=distance,
        want_success=success,
        escape=label.startswith("d_"),
    )
    surf = _surfaces(resp, hist)
    expected = f"{de} → {para}"
    if label.startswith("d_"):
        assert (
            resp["combat"]["active"] is False
        )  # escapou: sem trilha a mostrar, mas sem ids em nenhuma superficie
        assert line.endswith(f"escapou ({expected})"), line  # P3-9: quase livre → livre no mech_log
        for name, text in surf.items():
            assert not ID_RE.search(text), (label, name)
        return
    assert expected in surf["mech_log"], (label, surf["mech_log"])
    # mensagem do turno e Livro falam a mesma trilha (quando ha trilha na frase)
    if "escapou" not in line:
        assert expected in surf["mensagem"], (label, surf["mensagem"])
        assert expected in surf["livro"], (label, surf["livro"])
    for name, text in surf.items():
        assert not ID_RE.search(text), (label, name)
    # R16: nenhuma linha do registro/mech_log comeca com o nome do heroi nem contem "<nome>:"
    hero = "Smoke4A"
    for name in ("mech_log", "mensagem", "livro"):
        for ln in surf[name].replace(" | ", "\n").splitlines():
            assert not ln.strip().startswith(hero) and f"{hero}:" not in ln, (label, name, ln)
    if resp["combat"].get("active"):  # a Carta de Cena realmente disparou (condicao ou Carga)
        assert "Carga" in surf["mensagem"] or "condição" in surf["mensagem"], surf["mensagem"]


def test_force_escape_has_no_stale_roll():
    from agents.combat import _attempt_flee, _flee_roll_payload
    from services import combat_preview as cp

    start = {
        "trilha": "afastado",
        "perseguidores": ["lobo"],
        "fugitive_id": "player",
        "alcancado": False,
        "escapou": False,
        "_last": {
            "total": 9,
            "difficulty": 12,
            "sucesso": False,
            "de": "pressionado",
        },  # dado velho
    }
    scene = {"positions": {"player": {"distance_state": "proximo"}}}
    player = {"name": "V", "conscious": True, "virtudes": {"agilidade": 1}}
    enemy = {"id": "lobo", "name": "Lobo", "pursuit_policy": "persegue"}
    fled, logs, st = _attempt_flee(
        scene, player, [enemy], {}, random, existing_chase=start, force_escape=True
    )
    assert fled is True and "FOGE" in " ".join(logs)
    payload = _flee_roll_payload(st, "afastado", True)
    line = cp._flee_line({"fuga": payload})
    assert "total 9" not in line and line == "Fuga · sacrifício aceito · escapou (afastado → livre)"
