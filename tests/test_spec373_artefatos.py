"""SPEC-373 — portões congelados pelo autor de eval (Etapa E; ``handoffs/SPEC-373-eval-authoring.md``).

O executor de produto NÃO edita este arquivo, ``scripts/bestiario/arena.py`` nem ``docs/spec373/base/eval/``.
Os portões leem artefatos que o executor gera com o avaliador sem mudança e falham enquanto eles
não existem (é o alvo da spec, não um teste quebrado):

- R17 veredito cheio: ``docs/spec373/arena-<regiao>.json`` (12 regiões, sementes 0-39, ``off,on``,
  ``--baseline docs/spec349/arena-slots-baseline.json``) com >= 250 de 281 no ``ok`` do ``arena.py``;
- R17 regressões: contra a linha de base congelada ``docs/spec373/base/eval/arena-<regiao>.json``, nenhuma
  criatura que passava passa a falhar por mais de 3 pp; no máximo 5 falham por até 3 pp (borda);
- R2/R17 ``off``: células ``off`` idênticas à base para toda criatura fora de
  ``docs/spec373/recalibradas.json`` (lista de ids que o R8 recalibrou; ``[]`` se nenhuma);
- R13 chefes: os 13 chefes da esteira com ``L5|off`` e ``L5|on`` em 45-85 %; slots com ``ok``;
- R18 Posturas: ``docs/spec373/posturas-ab-0-19.json`` (``arena_spec355.py base --seeds 0:20``, depois
  das Partes A/B e antes da Parte C) com ``posturas`` idêntico a ``docs/spec373/base/eval/posturas-0-19.json``;
- R3 confirmação: ``docs/spec373/confirmacao-40-119.json`` gerado pelo ``arena.py`` com
  ``--seed-inicio 40 --seeds 80`` para os 13 chefes (o resultado vai para a §9; não é reajustado).

Denominador congelado: as 281 criaturas da linha de base (mesmos ids). Unidade: taxa de vitória do
herói por célula (5 Posturas x 40 sementes = 200 lutas). Nada é excluído.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "spec373"
BASE = DOCS / "base" / "eval"  # congelada pelo autor de eval (protegida)
SLOTS_BASELINE = ROOT / "docs" / "spec349" / "arena-slots-baseline.json"

REGIOES = (
    "aethelgard",
    "brekmar",
    "costa_negra",
    "deserto_zhur",
    "floresta_sussurros",
    "montanhas_afiadas",
    "nova_arcadia",
    "ophidia",
    "pantano_melancolia",
    "pradaria_ruinas",
    "selva_xylos",
    "skallgard",
)
CHEFES_FORA = (
    "mon_borda_que_anda",
    "mon_chifres_travados",
    "mon_casco_de_costelas",
    "enemy_aranha_de_cristal",
    "enemy_boss_general_escorpiao",
    "mon_hospede_do_estomago",
    "mon_toldo_das_clareiras",
    "mon_peso_dos_vencidos",
    "mon_escavador_das_camaras",
)
CHEFES_NA_FAIXA = (
    "mon_cacao_de_lastro",
    "mon_roda_de_mandibulas",
    "mon_mastro_dos_ultimos",
    "mon_colecionador_de_poses",
)
CHEFES = CHEFES_FORA + CHEFES_NA_FAIXA
SLOTS = ("enemy_aranha_de_cristal", "enemy_boss_general_escorpiao")

# Limiares congelados (R13/R17/R3). Faixa e delta repetem os do arena.py, que não mudam (R1).
FAIXA = (0.45, 0.85)
DELTA_MAX_PP = 8.0
TOTAL_CRIATURAS = 281
MIN_OK = 250  # 241 da main 9468d058 + os 9 chefes (decisão do dono 04/11; era 256 = 247 + 9)
BORDA_PP = 3.0
MAX_BORDA = 5
CONF_INICIO, CONF_SEEDS = 40, 80


def _load(path: Path) -> dict:
    assert path.exists(), f"artefato ausente: {path.relative_to(ROOT)} (gerar com o avaliador)"
    return json.loads(path.read_text(encoding="utf-8"))


def _arena_dir(d: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in REGIOES:
        payload = _load(d / f"arena-{r}.json")
        assert payload["regiao"] == r and payload["seeds"] == 40, (r, payload.get("seeds"))
        assert "seed_inicio" not in payload, f"{r}: o ajuste usa as sementes 0-39"
        for bid, rec in payload["criaturas"].items():
            assert bid not in out, f"{bid} em duas regiões"
            out[bid] = rec
    return out


def _slot_base() -> dict[str, dict]:
    return {
        b: r["cells"] for b, r in json.loads(SLOTS_BASELINE.read_text("utf-8"))["criaturas"].items()
    }


def excesso_pp(cells: dict, slot_cells: dict | None) -> float:
    """Quanto (pp) a pior célula passa do critério do ``arena.py``; 0 = dentro.

    Faixa: distância até 45-85 %. Slot: |delta| acima de 8 pp, só se o slot ANTES estava na faixa."""
    pior = 0.0
    for key, w in cells.items():
        pior = max(pior, (FAIXA[0] - w) * 100, (w - FAIXA[1]) * 100)
        b = (slot_cells or {}).get(key)
        if b is not None and FAIXA[0] <= b <= FAIXA[1]:
            pior = max(pior, round(abs(w - b) * 100, 1) - DELTA_MAX_PP)
    return round(max(pior, 0.0), 1)


def regressoes(
    base: dict[str, dict], pos: dict[str, dict], slots: dict[str, dict]
) -> dict[str, float]:
    """Criaturas que passavam na base e falham depois -> excesso em pp."""
    return {
        bid: excesso_pp(rec["cells"], slots.get(bid))
        for bid, rec in pos.items()
        if base[bid]["ok"] and not rec["ok"]
    }


def avaliar_regressoes(regs: dict[str, float]) -> list[str]:
    erros = [
        f"{b} falha por {e:.1f} pp (> {BORDA_PP:.0f})" for b, e in regs.items() if e > BORDA_PP
    ]
    if len(regs) > MAX_BORDA:
        erros.append(f"{len(regs)} regressões de borda (máx. {MAX_BORDA}): {sorted(regs)}")
    return erros


# --- known-good / known-bad das funções do portão ---------------------------------------------


def test_excesso_known_good_e_bad():
    assert excesso_pp({"L3|off": 0.45, "L3|on": 0.85}, None) == 0.0
    assert excesso_pp({"L3|off": 0.42, "L3|on": 0.60}, None) == 3.0
    assert excesso_pp({"L5|on": 0.90}, None) == 5.0
    # slot: delta 10 pp contra base na faixa = 2 pp de excesso; base fora da faixa não conta delta
    assert excesso_pp({"L5|on": 0.60}, {"L5|on": 0.70}) == 2.0
    assert excesso_pp({"L5|on": 0.60}, {"L5|on": 0.30}) == 0.0


def test_regressoes_known_good_e_bad():
    base = {f"c{i}": {"ok": True} for i in range(8)}
    ok = {f"c{i}": {"ok": True, "cells": {"L3|on": 0.6}} for i in range(8)}
    assert avaliar_regressoes(regressoes(base, ok, {})) == []
    borda = dict(ok) | {f"c{i}": {"ok": False, "cells": {"L3|on": 0.43}} for i in range(5)}
    assert avaliar_regressoes(regressoes(base, borda, {})) == []
    seis = dict(ok) | {f"c{i}": {"ok": False, "cells": {"L3|on": 0.43}} for i in range(6)}
    assert any("6 regressões" in e for e in avaliar_regressoes(regressoes(base, seis, {})))
    longe = dict(ok) | {"c0": {"ok": False, "cells": {"L3|on": 0.40}}}
    assert any("5.0 pp" in e for e in avaliar_regressoes(regressoes(base, longe, {})))
    # quem já falhava na base não conta como regressão
    base_fora = base | {"c0": {"ok": False}}
    assert regressoes(base_fora, longe, {}) == {}


# --- avaliador: --seed-inicio (Etapa E) ------------------------------------------------------


def _arena_module(monkeypatch):
    monkeypatch.chdir(os.getcwd())  # o módulo faz os.chdir(ROOT) ao importar; o teardown restaura
    spec = importlib.util.spec_from_file_location("arena373", ROOT / "scripts/bestiario/arena.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_arena_seed_inicio_default_identico(monkeypatch, tmp_path):
    arena = _arena_module(monkeypatch)
    args = ["--ids", "enemy_gargula_ferro", "--seeds", "2"]
    sem, com = tmp_path / "sem.json", tmp_path / "com.json"
    arena.main([*args, "--json", str(sem)])
    arena.main([*args, "--seed-inicio", "0", "--json", str(com)])
    a, b = (json.loads(p.read_text("utf-8")) for p in (sem, com))
    a.pop("elapsed_s"), b.pop("elapsed_s")
    assert a == b and "seed_inicio" not in a


def test_arena_seed_inicio_usa_as_sementes_pedidas(monkeypatch, tmp_path):
    arena = _arena_module(monkeypatch)
    vistas: list[int] = []

    def fake_fight(bid, n, cls, level, seed, modo):
        vistas.append(seed)
        return ("win" if seed % 2 else "loss"), None

    monkeypatch.setattr(arena.M, "fight", fake_fight)
    out = tmp_path / "c.json"
    arena.main(
        ["--ids", "enemy_gargula_ferro", "--seed-inicio", "40", "--seeds", "2", "--json", str(out)]
    )
    assert set(vistas) == {40, 41}
    payload = json.loads(out.read_text("utf-8"))
    assert payload["seed_inicio"] == 40 and payload["seeds"] == 2


# --- portões (artefatos do executor) ----------------------------------------------------------


def test_linha_de_base_congelada_tem_281():
    base = _arena_dir(BASE)
    assert len(base) == TOTAL_CRIATURAS
    assert set(CHEFES) <= set(base)


def test_portao_veredito_cheio_250_de_281():
    base, pos = _arena_dir(BASE), _arena_dir(DOCS)
    assert set(pos) == set(base), "denominador congelado: mesmas 281 criaturas"
    n_ok = sum(r["ok"] for r in pos.values())
    assert n_ok >= MIN_OK, f"{n_ok}/{TOTAL_CRIATURAS} no veredito cheio (mín. {MIN_OK})"


def test_portao_regressoes_de_borda():
    base, pos = _arena_dir(BASE), _arena_dir(DOCS)
    slots = _slot_base()
    for bid, rec in pos.items():  # o ok gravado é o do arena.py; o portão confere a leitura
        assert (excesso_pp(rec["cells"], slots.get(bid)) == 0.0) == rec["ok"], bid
    assert avaliar_regressoes(regressoes(base, pos, slots)) == []


def test_portao_off_identico_fora_das_recalibradas():
    base, pos = _arena_dir(BASE), _arena_dir(DOCS)
    recal = set(_load(DOCS / "recalibradas.json"))
    assert recal <= set(base), recal - set(base)
    mudou = {
        bid: (base[bid]["cells"][k], rec["cells"][k])
        for bid, rec in pos.items()
        if bid not in recal
        for k in rec["cells"]
        if k.endswith("|off") and rec["cells"][k] != base[bid]["cells"].get(k)
    }
    assert not mudou, mudou


def test_portao_chefes_na_faixa_off_e_on():
    pos = _arena_dir(DOCS)
    fora = {
        bid: {k: pos[bid]["cells"][k] for k in ("L5|off", "L5|on")}
        for bid in CHEFES
        if not all(FAIXA[0] <= pos[bid]["cells"][k] <= FAIXA[1] for k in ("L5|off", "L5|on"))
    }
    assert not fora, fora
    assert all(pos[s]["ok"] for s in SLOTS), {s: pos[s]["motivos"] for s in SLOTS}


def test_portao_posturas_identicas_depois_de_a_e_b():
    base = _load(BASE / "posturas-0-19.json")
    pos = _load(DOCS / "posturas-ab-0-19.json")
    assert base["seeds"] == pos["seeds"] == [0, 20]
    assert pos["posturas"] == base["posturas"]


def test_portao_confirmacao_40_119_gravada():
    conf = _load(DOCS / "confirmacao-40-119.json")
    assert conf.get("seed_inicio") == CONF_INICIO and conf["seeds"] == CONF_SEEDS
    assert set(CHEFES) <= set(conf["criaturas"]), set(CHEFES) - set(conf["criaturas"])
    for bid in CHEFES:
        assert {"L5|off", "L5|on"} <= set(conf["criaturas"][bid]["cells"]), bid


@pytest.mark.parametrize("regiao", REGIOES)
def test_linha_de_base_bate_com_o_avaliador(regiao):
    """A base congelada é saída bruta do ``arena.py`` (mesmas chaves que o pós vai ter)."""
    payload = _load(BASE / f"arena-{regiao}.json")
    for rec in payload["criaturas"].values():
        assert set(rec) == {"nome", "categoria", "status", "cells", "ok", "motivos"}
        assert set(rec["cells"]) & {"L3|off", "L5|off"} and rec["ok"] == (not rec["motivos"])


def test_avaliador_protegido():
    rows = (ROOT / "evals" / "protected-paths.txt").read_text("utf-8").splitlines()
    for path in (
        "scripts/bestiario/arena.py",
        "tests/test_spec373_artefatos.py",
        "docs/spec373/base/eval",
    ):
        assert path in rows, path
