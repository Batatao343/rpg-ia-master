"""SPEC-369 R11 - testes de META, escritos pela Fase A ANTES do produto (autor de eval).

Leem os artefatos da Fase B (`docs/spec369/final-0-19.json`, `passos-0-19.json`) e da Fase C
(`docs/spec369/confirmacao.json`), todos no formato de `docs/spec369/metricas_369.py` (uma chave
por subcomando), e reprovam enquanto as metas do R13-R20/R22 nao forem cumpridas.

Artefato ausente -> ``pytest.xfail`` (vermelho esperado, sem quebrar a suite default).
Para ver a falha real: ``bash scripts/dev/pt.sh tests/test_spec369_metas.py --runxfail``.
Os limiares (``LIMIARES``) so mudam por decisao do dono, em commit separado de autor de eval.
A Fase B NAO edita este arquivo (R1).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

D = Path(__file__).resolve().parents[1] / "docs" / "spec369"

# D-369-3 (defaults; gate R9c do dono respondido em 04/11 com "ok defaults"). So muda por autor de eval.
LIMIARES = {
    "cartas_rodada_total_min": 2.00,  # R13
    "cartas_rodada_postura_min": 1.90,  # R13
    "uso_alto": 0.60,  # R14(a)
    "p95_total_max": 10.0,  # R15
    "p95_postura_max": 12.0,  # R15
    "timeout_postura_max_pct": 1.0,  # R15
    "pressagio_razao_faixa_cego_max": 0.95,  # R16 primaria (D-369-2)
    "faixa_vitoria_pct": (45.0, 85.0),  # R16, R19(c), R20
    "emboscada_corruptor_min": 0.45,  # R17
    "sangromante_max_pp": 2.0,  # R19(b), D-369-8
    "queda_postura_max_pp": 5.0,  # R19(d)
    "familia_delta_max_pp": 10.0,  # R20, D-369-7
    "max_cartas_heroi": 8,  # R18
    "max_passos_por_carta": 2,  # R18
    "max_cartas_inimigo_por_familia": 2,  # R18(d)
    "familia_min_lutas_por_modo": 200,  # R20, D-369-7 (Astra rodada 4, P2-3)
}
# Sementes da arena de familias por fase (R3/R22). `predador_apice` L3 so tem 2 criaturas: para 200
# lutas por modo usa 20 sementes (gate R9c item 4). 260-279 so estende a confirmacao 260-267 DENTRO da
# arena de familias (nenhuma faixa de ajuste dela passa de 19); as 260-339 das outras arenas sao a
# mesma confirmacao unica (R22), em outra arena/tag, e nunca serviram de ajuste.
SEMENTES_FAMILIA = {"final": [0, 7], "confirmacao": [260, 267]}
SEMENTES_FAMILIA_CELULA = {"predador_apice|L3": {"final": [0, 19], "confirmacao": [260, 279]}}
FORA_DA_META_R14 = {"sangromante"}  # R4(a): Sangromante e excecao aceita
# Gate R9c do dono (04/11, "ok defaults"; spec §8 "Resposta do dono ao gate R9c"):
ISENTAS_PISO_R13 = {"Sangromante"}  # item 2(0): fora do piso por Postura; o total >= 2,00 vale
# item 2(a): reacoes legadas "travadas pelo golden", fora do R14(b). Lista fechada: outra Carta que
# ficar `dominante` reprova. Item 2(b): o B4 sai do plano, mas `bomba_estopim` (onda) segue no R14(b).
LEGADAS_TRAVADAS_R14B = {"arc_cal_valvula", "dev_ombro_porta", "dev_reflexo_bastiao"}

# D-369-10 (dono, 04/11, "Aceitar e ajustar", spec §8): limites REGISTRADOS com os numeros da Fase B
# (`final-0-19.json` de 540deb81). Sao tetos que nao podem piorar; o resto das metas fica inalterado.
# - R14(a): assinatura basica com `custo_folego` 0 (lido do catalogo) fica isenta, como o golpe.
LIMITE_USO_R14A = {"arc1_cal_pulso_medido": 1.0, "bas_cor_mofo": 0.714}  # D-369-10 item 1
LIMITE_P95_POSTURA = {"Médico de Campo": 16.0}  # D-369-10 item 2 (p95 total <= 10 continua meta)
LIMITE_PRESSAGIO_RAZAO = 1.0257  # D-369-10 item 3 (vitoria de on-faixa segue em 45-85 %)
# D-369-10 item 3: celulas do R20 com limite registrado (vitoria `on` e Delta da Fase B, sem piorar).
LIMITE_FAMILIA = {
    "conjurador|L5": {"on_win": 0.385, "delta_pp": -8.0},
    "predador_apice|L3": {"on_win": 0.615, "delta_pp": -13.5},
}
# D-369-10 item 5 / R22: na confirmacao (sementes novas) os LIMITES REGISTRADOS ganham uma tolerancia
# de amostra (~1 erro-padrao das amostras da Fase C); metas cheias e pisos absolutos nao ganham nada.
TOLERANCIA_CONFIRMACAO = {"uso": 0.05, "p95": 1.0, "razao": 0.02, "familia_pp": 5.0}


def _tol(fase: str, chave: str) -> float:
    return TOLERANCIA_CONFIRMACAO[chave] if fase == "confirmacao" else 0.0


def assinatura_gratis(cid: str) -> bool:
    """D-369-10 item 1: Carta basica com `custo_folego` 0 no catalogo atual (jogada sempre que esta
    na mao; o uso nao mede dominancia)."""
    from services import card_effects as fx
    from services import cards

    card = cards.get_card(cid) or {}
    return bool(card.get("basica")) and fx.custo_folego(card) == 0


def _load(name: str) -> dict | list:
    path = D / name
    if not path.exists():
        pytest.xfail(f"{name} ausente: artefato da Fase B/C ainda nao existe (R11)")
    return json.loads(path.read_text(encoding="utf-8"))


def _base() -> dict:
    return json.loads((D / "base-0-19.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# checagens (devolvem a lista de violacoes; vazia = meta cumprida)
# --------------------------------------------------------------------------
def r13(data: dict) -> list[str]:
    r9 = data["base"]["r9"]
    bad = []
    if r9["total"]["cartas_por_rodada_media"] < LIMIARES["cartas_rodada_total_min"]:
        bad.append(f"total {r9['total']['cartas_por_rodada_media']}")
    for cls, v in r9["por_postura"].items():
        if cls in ISENTAS_PISO_R13:
            continue
        if v["cartas_por_rodada_media"] < LIMIARES["cartas_rodada_postura_min"]:
            bad.append(f"{cls} {v['cartas_por_rodada_media']}")
    return bad


def na_meta_r14a(cid: str, categoria: str) -> bool:
    """R14(a)+(d): Carta de onda OU assinatura basica (basica que nao e golpe nem guarda; golpe e,
    pelo gate R9c item 5, guarda basicos sao aceitos como fallback), sempre fora do Sangromante."""
    if categoria == "onda":
        return True
    return categoria == "basica" and not cid.endswith(("_golpe", "_guarda"))


def r14(data: dict, fase: str = "final") -> list[str]:
    bad = []
    for cid, r in data["uso"]["cartas"].items():
        if r["categoria"] in FORA_DA_META_R14:
            continue
        na_meta = na_meta_r14a(cid, r["categoria"]) and not assinatura_gratis(cid)
        teto = LIMIARES["uso_alto"]
        if cid in LIMITE_USO_R14A:
            teto = max(teto, LIMITE_USO_R14A[cid] + _tol(fase, "uso"))
        if na_meta and r["uso"] > teto:
            bad.append(f"(a) {cid} uso {r['uso']}")
        if "dominante" in r["bandeiras_v2"] and cid not in LEGADAS_TRAVADAS_R14B:
            bad.append(f"(b) {cid} delta {r['delta_pp_v2']}")
    return bad


def r15(data: dict, fase: str = "final") -> list[str]:
    r9 = data["base"]["r9"]
    bad = []
    if r9["total"]["p95_rodadas_conflito"] > LIMIARES["p95_total_max"]:
        bad.append(f"p95 total {r9['total']['p95_rodadas_conflito']}")
    for cls, v in r9["por_postura"].items():
        teto = LIMIARES["p95_postura_max"]
        if cls in LIMITE_P95_POSTURA:
            teto = max(teto, LIMITE_P95_POSTURA[cls] + _tol(fase, "p95"))
        if v["p95_rodadas_conflito"] > teto:
            bad.append(f"{cls} p95 {v['p95_rodadas_conflito']}")
        if v["timeout_pct"] > LIMIARES["timeout_postura_max_pct"]:
            bad.append(f"{cls} timeout {v['timeout_pct']}")
    return bad


def r16(data: dict, fase: str = "final") -> list[str]:
    bloco = data["pressagio"]["conhecida"]["decks_on"]
    lo, hi = LIMIARES["faixa_vitoria_pct"]
    bad = []
    teto = max(
        LIMIARES["pressagio_razao_faixa_cego_max"], LIMITE_PRESSAGIO_RAZAO + _tol(fase, "razao")
    )
    if bloco["razao_faixa_cego"] > teto:
        bad.append(f"on-faixa/on-cego {bloco['razao_faixa_cego']}")
    if not lo <= bloco["on-faixa"]["vitoria_pct"] <= hi:
        bad.append(f"vitoria on-faixa {bloco['on-faixa']['vitoria_pct']}")
    return bad


def r17(data: dict) -> list[str]:
    """Piso do Corruptor na emboscada realista com o credito D-369-6 (`realista_369`).
    "Nenhuma outra Postura muda" vale no commit do B2 (antes do B3 mexer em basicas) e e
    conferido no registro B2 de `passos-0-19.json` pela revisao, nao no artefato final."""
    total = data["emboscada"]["posturas"]["Corruptor"]["todas"]["realista_369"]["total"]
    return [] if total >= LIMIARES["emboscada_corruptor_min"] else [f"Corruptor {total}"]


def r19(data: dict, base: dict | None) -> list[str]:
    g = data["posturas"]["guarda_r19"]
    bad = [f"(a) {x}" for x in g["postura_fora_45_85"] + g["padrao_acima_75"]]
    if not g["arcanista_todas_ge_45"]:
        bad.append("(a) Arcanista todas < 45 %")
    lo, hi = LIMIARES["faixa_vitoria_pct"]
    vit = data["base"]["r9"]["total"]["vitoria_pct"]
    if not lo <= vit <= hi:
        bad.append(f"(c) vitoria base {vit}")
    if base is not None:
        ref = base["posturas"]["guarda_r19"]["totais"]
        for cls, total in g["totais"].items():
            if cls == "Sangromante" and (total - ref[cls]) * 100 > LIMIARES["sangromante_max_pp"]:
                bad.append(f"(b) Sangromante {ref[cls]} -> {total}")
            if (ref[cls] - total) * 100 > LIMIARES["queda_postura_max_pp"]:
                bad.append(f"(d) {cls} {ref[cls]} -> {total}")
    return bad


def r20(data: dict, alvo: list[str], fase: str = "final") -> list[str]:
    """Celula-alvo: >= 200 lutas por modo, sementes da convencao da fase, `on` em 45-85 % e
    |Delta| <= 10 pp. Celula com sementes proprias traz ``sementes`` (como em `base-0-19.json`)."""
    lo, hi = LIMIARES["faixa_vitoria_pct"]
    bad = []
    if data["familias"]["meta"]["seeds"] != SEMENTES_FAMILIA[fase]:
        bad.append(f"sementes {data['familias']['meta']['seeds']} != {SEMENTES_FAMILIA[fase]}")
    for key in alvo:
        cell = data["familias"]["cells"][key]
        esperado = SEMENTES_FAMILIA_CELULA.get(key, {}).get(fase)
        if esperado is not None and cell.get("sementes") != esperado:
            bad.append(f"{key} sementes {cell.get('sementes')} != {esperado}")
        for mode in ("off", "on"):
            if cell[mode]["fights"] < LIMIARES["familia_min_lutas_por_modo"]:
                bad.append(f"{key} {mode} so {cell[mode]['fights']} lutas")
        on = cell["on"]["win"] * 100
        c_lo, c_hi, d_max = _faixa_celula(key, fase)
        if not c_lo <= on <= c_hi or abs(cell["delta_pp"]) > d_max:
            bad.append(f"{key} on {on:.1f} delta {cell['delta_pp']}")
    return bad


def _faixa_celula(key: str, fase: str) -> tuple[float, float, float]:
    """(on_min, on_max, |Delta|_max) da celula: a meta cheia, ou o limite registrado D-369-10
    (a faixa so se alarga ate o valor da Fase B, nunca alem; + tolerancia na confirmacao)."""
    lo, hi = LIMIARES["faixa_vitoria_pct"]
    d_max = LIMIARES["familia_delta_max_pp"]
    lim = LIMITE_FAMILIA.get(key)
    if lim is None:
        return lo, hi, d_max
    tol = _tol(fase, "familia_pp")
    on = lim["on_win"] * 100
    return min(lo, on - tol), max(hi, on + tol), max(d_max, abs(lim["delta_pp"]) + tol)


# --------------------------------------------------------------------------
# Fase B (sementes 0-19 / familias 0-7)
# --------------------------------------------------------------------------
def test_r13_cartas_por_rodada():
    assert r13(_load("final-0-19.json")) == []


def test_r14_dominancia():
    assert r14(_load("final-0-19.json")) == []


def test_r15_duracao():
    assert r15(_load("final-0-19.json")) == []


def test_r16_pressagio_valor_da_informacao():
    assert r16(_load("final-0-19.json")) == []


def test_r17_emboscada_corruptor():
    assert r17(_load("final-0-19.json")) == []


def test_r19_guardas_globais():
    assert r19(_load("final-0-19.json"), _base()) == []


def test_r20_familias():
    assert r20(_load("final-0-19.json"), _base()["familias"]["celulas_alvo"]) == []


def test_r18_limites_de_passos():
    """``passos-0-19.json``: lista (ou ``{"passos": [...]}``) de ``{bloco, carta|constante, ...}``;
    passos de inimigo (B6) trazem ``familia``. Passo revertido tambem conta (R18)."""
    raw = _load("passos-0-19.json")
    passos = raw["passos"] if isinstance(raw, dict) else raw
    heroi: dict[str, int] = {}
    inimigo: dict[str, set[str]] = {}
    for p in passos:
        if not p.get("carta"):
            continue
        if p.get("bloco") == "B6":
            inimigo.setdefault(p["familia"], set()).add(p["carta"])
        else:
            heroi[p["carta"]] = heroi.get(p["carta"], 0) + 1
    assert len(heroi) <= LIMIARES["max_cartas_heroi"], sorted(heroi)
    assert all(n <= LIMIARES["max_passos_por_carta"] for n in heroi.values()), heroi
    assert all(len(v) <= LIMIARES["max_cartas_inimigo_por_familia"] for v in inimigo.values())


# --------------------------------------------------------------------------
# Fase C (R22: uma vez, sementes 260-339 / familias 260-267, sem reajuste). Excecao de amostra:
# `predador_apice` L3 na confirmacao usa 260-279 (`familias --seeds 260-279 --only predador_apice
# --levels 3`), gravada na celula com ``sementes: [260, 279]`` (SEMENTES_FAMILIA_CELULA).
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "check",
    ["r13", "r14", "r15", "r16", "r17", "r19", "r20"],
)
def test_r22_confirmacao(check):
    data = _load("confirmacao.json")
    assert data["base"]["meta"]["seeds"] == [260, 339]
    assert data["familias"]["meta"]["seeds"] == [260, 267]
    fns = {
        "r13": lambda: r13(data),
        "r14": lambda: r14(data, "confirmacao"),
        "r15": lambda: r15(data, "confirmacao"),
        "r16": lambda: r16(data, "confirmacao"),
        "r17": lambda: r17(data),
        "r19": lambda: r19(data, None),  # (a) e (c)
        "r20": lambda: r20(data, _base()["familias"]["celulas_alvo"], "confirmacao"),
    }
    assert fns[check]() == []
