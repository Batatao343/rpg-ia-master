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
  dial mudado por spec posterior só sai do portão R8 se estiver em
  ``docs/bestiario/recalibracoes_posteriores.json`` (protegido, validado aqui);
- R13 chefes: os 13 chefes da esteira com ``L5|off`` e ``L5|on`` em 45-85 %; slots com ``ok``;
  exceção nominal D-373 (dono, 04/11) por célula em ``EXCECOES_CHEFE_D373``, sem piorar > 3 pp;
- R18 Posturas: ``docs/spec373/posturas-ab-0-19.json`` (``arena_spec355.py base --seeds 0:20``, depois
  das Partes A/B e antes da Parte C) com ``posturas`` idêntico a ``docs/spec373/base/eval/posturas-0-19.json``;
- R3 confirmação: ``docs/spec373/confirmacao-40-119.json`` gerado pelo ``arena.py`` com
  ``--seed-inicio 40 --seeds 80`` para os 13 chefes (o resultado vai para a §9; não é reajustado).

Denominador congelado: as 281 criaturas da linha de base (mesmos ids). Unidade: taxa de vitória do
herói por célula (5 Posturas x 40 sementes = 200 lutas). Nada é excluído.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest
import yaml

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

# D-373 (dono, 04/11, "aceito assim"; spec §8/§9, R11.4): exceção nominal ao R13, por célula.
# Valor = taxa gravada nas 0-39 (``docs/spec373/arena-<r>.json`` em 378c2658). A célula listada
# pode ficar fora de 45-85 %, mas não pode se afastar da faixa mais que BORDA_PP além do gravado
# (mesma borda do R17, ~1 erro padrão de 200 lutas). Célula não listada segue a regra normal.
EXCECOES_CHEFE_D373: dict[str, dict[str, float]] = {
    "mon_hospede_do_estomago": {"L5|off": 0.435, "L5|on": 0.385},
    "mon_escavador_das_camaras": {"L5|on": 0.400},
}


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


# --- P2-2 (Sol): a lista de recalibradas é exatamente o conjunto com dial mudado (R8) --------
# Base congelada dos dials (sem a chave ``arena``) da main medida, ``9468d058``; ver
# ``handoffs/SPEC-373-eval-authoring.md`` §9. Não depende de git: o CI lê o JSON. O hash é do
# conteúdo canônico (indiferente a CRLF), para acusar edição da base.
AJUSTES = ROOT / "data" / "bestiario" / "mecanica" / "_ajustes.yaml"
DIALS_BASE = BASE / "ajustes-dials-base.json"
DIALS_BASE_SHA = "82155e342f5c54574cece7cf5ebe0e37b451f8ae9d29af4a7e5773dcc6894b70"


def _sha_canonico(obj: object) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _dials(entry: dict | None) -> dict[str, int]:
    """Dials de uma entrada; ausente vale 0 (o ``calibrar.py`` grava só os usados)."""
    return {k: int(v) for k, v in (entry or {}).items() if k != "arena" and v}


def ids_com_dial_mudado(base: dict[str, dict], pos: dict[str, dict]) -> set[str]:
    return {b for b in set(base) | set(pos) if _dials(base.get(b)) != _dials(pos.get(b))}


def avaliar_recalibradas(recal: set[str], mudados: set[str]) -> list[str]:
    erros = []
    if sem := sorted(recal - mudados):
        erros.append(f"na lista sem mudança de dial contra a base: {sem}")
    if fora := sorted(mudados - recal):
        erros.append(f"dial mudado fora da lista (sem confirmação 40-119): {fora}")
    return erros


def test_recalibradas_known_good_e_bad():
    base = {"a": {"arena": "x", "dano": -1, "sig": 0}, "b": {"dano": 2}}
    # só o texto ``arena`` e zeros explícitos/ausentes não contam como mudança
    pos = {"a": {"arena": "y", "dano": -1}, "b": {"dano": 2, "corpo": 0}}
    assert ids_com_dial_mudado(base, pos) == set()
    pos2 = pos | {"b": {"dano": 3}, "c": {"sig": 1}}  # mudou b; c é nova com dial
    mudados = ids_com_dial_mudado(base, pos2)
    assert mudados == {"b", "c"}
    assert avaliar_recalibradas({"b", "c"}, mudados) == []
    sem = avaliar_recalibradas({"a", "b", "c"}, mudados)
    assert sem == ["na lista sem mudança de dial contra a base: ['a']"]
    fora = avaliar_recalibradas({"b"}, mudados)
    assert fora == ["dial mudado fora da lista (sem confirmação 40-119): ['c']"]


def test_base_de_dials_congelada():
    payload = _load(DIALS_BASE)
    assert payload["fonte"].startswith("git show 9468d058:")
    assert len(payload["dials"]) == TOTAL_CRIATURAS
    assert _sha_canonico(payload["dials"]) == DIALS_BASE_SHA


def test_portao_recalibradas_igual_aos_dials_mudados():
    """``recalibradas.json`` == ids com dial mudado contra a base, nas duas direções.

    Só desconta as recalibrações de specs posteriores (registro protegido, disjunto da lista da 373)."""
    base = _load(DIALS_BASE)["dials"]
    pos = yaml.safe_load(AJUSTES.read_text("utf-8"))["ajustes"]
    recal = set(_load(DOCS / "recalibradas.json"))
    mudados = ids_com_dial_mudado(base, pos) - set(posteriores())
    assert avaliar_recalibradas(recal, mudados) == []


# --- Recalibrações posteriores à 373 (adendo, ``handoffs/SPEC-373-eval-authoring.md``) --------
# Registro versionado e protegido: id -> {spec, motivo}. Os portões da 373 descontam só estas ids.
POSTERIORES = ROOT / "docs" / "bestiario" / "recalibracoes_posteriores.json"


def posteriores() -> dict[str, dict]:
    return _load(POSTERIORES)["recalibracoes"]


def _textos_da_spec(spec: str) -> str:
    """Relatório ``docs/specNNN/RELATORIO.md`` + arquivo da spec; vazio se nada existir."""
    num = spec.removeprefix("SPEC-")
    fontes = [ROOT / "docs" / f"spec{num}" / "RELATORIO.md", *ROOT.glob(f"specs/{spec}-*.md")]
    return "\n".join(p.read_text("utf-8") for p in fontes if p.is_file())


def avaliar_posteriores(
    reg: dict[str, dict], recal373: set[str], base_ids: set[str], textos: dict[str, str]
) -> list[str]:
    """Registro não é lista livre: spec citada, motivo, id conhecida, fora da lista da 373, citada."""
    erros = []
    for bid, rec in sorted(reg.items()):
        spec, motivo = str(rec.get("spec", "")), str(rec.get("motivo", "")).strip()
        if not spec.startswith("SPEC-") or not motivo:
            erros.append(f"{bid}: precisa de spec SPEC-NNN e motivo")
        elif spec == "SPEC-373" or bid in recal373:
            erros.append(f"{bid}: é da 373 (vai em recalibradas.json, não no registro)")
        elif bid not in base_ids:
            erros.append(f"{bid}: fora do denominador da 373")
        elif bid not in textos.get(spec, ""):
            erros.append(f"{bid}: não consta no relatório nem na spec {spec}")
    return erros


def test_posteriores_known_good_e_bad():
    base_ids, recal = {"a", "b", "c"}, {"c"}
    textos = {"SPEC-900": "| a | 50 / 60 |"}
    ok = {"a": {"spec": "SPEC-900", "motivo": "m"}}
    assert avaliar_posteriores(ok, recal, base_ids, textos) == []
    assert avaliar_posteriores({"b": {"spec": "SPEC-900", "motivo": "m"}}, recal, base_ids, textos)
    assert avaliar_posteriores({"a": {"spec": "SPEC-901", "motivo": "m"}}, recal, base_ids, textos)
    assert avaliar_posteriores({"a": {"spec": "SPEC-900", "motivo": " "}}, recal, base_ids, textos)
    assert avaliar_posteriores({"a": {"motivo": "m"}}, recal, base_ids, textos)
    assert avaliar_posteriores({"c": {"spec": "SPEC-900", "motivo": "m"}}, recal, base_ids, textos)
    assert avaliar_posteriores({"z": {"spec": "SPEC-900", "motivo": "z"}}, recal, base_ids, textos)
    # o desconto é só das ids registradas: outra id com dial mudado segue reprovando
    mudados = {"a", "c", "x"} - set(ok)
    assert avaliar_recalibradas(recal, mudados) == [
        "dial mudado fora da lista (sem confirmação 40-119): ['x']"
    ]


def test_registro_de_posteriores_valido():
    reg = posteriores()
    specs = {str(r.get("spec", "")) for r in reg.values()}
    textos = {s: _textos_da_spec(s) for s in specs}
    recal = set(_load(DOCS / "recalibradas.json"))
    base_ids = set(_load(DIALS_BASE)["dials"])
    assert avaliar_posteriores(reg, recal, base_ids, textos) == []


def test_portao_confirmacao_cobre_as_recalibradas():
    """Etapa 6: a confirmação 40-119 roda nos 13 chefes **e** nas recalibradas."""
    conf = _load(DOCS / "confirmacao-40-119.json")["criaturas"]
    recal = set(_load(DOCS / "recalibradas.json"))
    assert recal <= set(conf), sorted(recal - set(conf))


def _fora_pp(w: float) -> float:
    return round(max((FAIXA[0] - w) * 100, (w - FAIXA[1]) * 100, 0.0), 1)


def chefes_reprovados(cells_por_chefe: dict[str, dict], excecoes: dict) -> dict[str, dict]:
    """Chefe -> células L5 reprovadas. Célula da D-373 só reprova se piorar > BORDA_PP."""
    out: dict[str, dict] = {}
    for bid, cells in cells_por_chefe.items():
        for k in ("L5|off", "L5|on"):
            w, gravado = cells[k], excecoes.get(bid, {}).get(k)
            limite = 0.0 if gravado is None else _fora_pp(gravado) + BORDA_PP
            if _fora_pp(w) > limite:
                out.setdefault(bid, {})[k] = w
    return out


def test_chefes_reprovados_known_good_e_bad():
    exc = {"x": {"L5|on": 0.40}}
    assert chefes_reprovados({"x": {"L5|off": 0.60, "L5|on": 0.40}}, exc) == {}
    assert chefes_reprovados({"x": {"L5|off": 0.60, "L5|on": 0.37}}, exc) == {}  # borda 3 pp
    assert chefes_reprovados({"x": {"L5|off": 0.60, "L5|on": 0.36}}, exc) == {"x": {"L5|on": 0.36}}
    # célula não listada da mesma criatura segue a regra normal
    assert chefes_reprovados({"x": {"L5|off": 0.44, "L5|on": 0.50}}, exc) == {"x": {"L5|off": 0.44}}
    # outro chefe fora da faixa reprova, mesmo por 0,5 pp
    assert chefes_reprovados({"y": {"L5|off": 0.445, "L5|on": 0.60}}, exc) == {
        "y": {"L5|off": 0.445}
    }


def test_excecoes_d373_sao_so_as_aceitas_pelo_dono():
    assert set(EXCECOES_CHEFE_D373) == {"mon_hospede_do_estomago", "mon_escavador_das_camaras"}
    assert set(EXCECOES_CHEFE_D373) <= set(CHEFES) and not set(EXCECOES_CHEFE_D373) & set(SLOTS)
    for cells in EXCECOES_CHEFE_D373.values():
        assert set(cells) <= {"L5|off", "L5|on"} and all(_fora_pp(w) > 0 for w in cells.values())


def test_portao_chefes_na_faixa_off_e_on():
    """R13 com a exceção nominal D-373 (``EXCECOES_CHEFE_D373``); o resto dos chefes sem exceção."""
    pos = _arena_dir(DOCS)
    fora = chefes_reprovados({b: pos[b]["cells"] for b in CHEFES}, EXCECOES_CHEFE_D373)
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
