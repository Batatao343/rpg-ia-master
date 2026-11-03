"""SPEC-370 R16-R21: eval da fauna viva por regiao, oraculo proprio do M1, M7 e M8.

Protegido (R21, `evals/protected-paths.txt`): quem otimiza o produto nao edita este arquivo
nem `scripts/fauna/eval.py`. Limiares literais abaixo (D4 da 360; D5 e D7 da 370).
Parametrizado pelas 12 regioes; a regiao sem `data/bestiario/fauna/<r>.yaml` e pulada.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGIONS = (
    "nova_arcadia",
    "pantano_melancolia",
    "brekmar",
    "skallgard",
    "pradaria_ruinas",
    "montanhas_afiadas",
    "aethelgard",
    "floresta_sussurros",
    "selva_xylos",
    "deserto_zhur",
    "costa_negra",
    "ophidia",
)


def _load_eval():
    spec = importlib.util.spec_from_file_location(
        "spec370_eval", ROOT / "scripts" / "fauna" / "eval.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EV = _load_eval()
_CACHE: dict[str, dict] = {}


def _has_fauna(region: str) -> bool:
    return (ROOT / "data" / "bestiario" / "fauna" / f"{region}.yaml").exists()


def _result(region: str) -> dict:
    """Tamanho do relatorio (20 x 60). M7 cheio so em Nova Arcadia (D6)."""
    if not _has_fauna(region):
        pytest.skip(f"{region}: sem data/bestiario/fauna/{region}.yaml (lote futuro)")
    if region not in _CACHE:
        _CACHE[region] = EV.run(20, 60, region, m7=(region == "nova_arcadia"))
    return _CACHE[region]


@pytest.fixture(params=REGIONS)
def region(request):
    return request.param


# --------------------------------------------------------------------------- congelamento


def test_limiares_congelados_370():
    assert EV.M1_MIN_PRECEDIDO == 0.70
    assert EV.M1_MIN_APROXIMACAO == 1.00
    assert EV.M2_MAX_RATIO_FORA == 0.35
    assert (EV.M3_MIN_PRESA_SOBE, EV.M3_MAX_PREDADOR_CAI) == (1.5, 0.6)
    assert EV.M4_MIN_TERRITORIO == 0.80
    assert EV.M4_MIN_NOS == 2
    assert (EV.M5_MIN_DELTA, EV.M5_MAX_DELTA) == (-0.20, 0.05)
    assert (EV.M5_REGIAO_ALERTA_MIN, EV.M5_REGIAO_ALERTA_MAX) == (-0.30, 0.10)
    assert EV.M6_MAX_VAZAMENTOS == 0
    assert EV.M8_MAX_DENSIDADE == 0.40
    assert (EV.DEFAULT_SEEDS, EV.DEFAULT_DAYS) == (20, 60)
    assert tuple(EV.REGIONS) == REGIONS
    assert EV.M7_OFF_KEYS == (
        "arrivals",
        "rests",
        "triggers",
        "fauna_combats",
        "conversions",
        "signs_shown",
    )


# --------------------------------------------------------------------------- oraculo (R18)


def test_atribuicao_pelo_arquivo_de_dados():
    data = EV._fauna_data()
    idx = EV._sign_index(data)
    cid = sorted(idx)[0]
    text = idx[cid][0]
    assert EV.attribute_sign(f"<B>\n- {text}\n</B>", idx) == {cid}
    assert EV.attribute_sign("", idx) == frozenset()
    assert EV.attribute_sign("um texto que nao e sinal de ninguem", idx) == frozenset()


def test_precedido_oraculo_bom_e_ruim():
    terr = frozenset({"b"})
    emitted = [(3, "a", frozenset({"x"})), (5, "b", frozenset({"y"}))]
    # bom: sinal de x no mesmo local, antes do combate e dentro da janela
    assert EV.precedido_oraculo(emitted, "x", "a", 7, 0, terr)
    # bom: sinal de y num no do territorio (b), combate em outro local
    assert EV.precedido_oraculo(emitted, "y", "c", 7, 0, terr)
    # ruim: sinal de outra criatura
    assert not EV.precedido_oraculo(emitted, "z", "a", 7, 0, terr)
    # ruim: sinal fora da janela (antes do ultimo combate / do nascimento)
    assert not EV.precedido_oraculo(emitted, "x", "a", 7, 3, terr)
    # ruim: sinal no mesmo turno ou depois do combate
    assert not EV.precedido_oraculo(emitted, "x", "a", 3, 0, terr)
    # ruim: local fora do territorio
    assert not EV.precedido_oraculo(emitted, "x", "c", 7, 0, frozenset({"d"}))


def test_oraculo_nao_confia_em_sinais_mostrados(monkeypatch):
    """Known-bad (P2-8): o produto grava o sinal na presenca sem emitir texto. O oraculo antigo
    conta 'precedido'; o proprio, nao."""
    if not _has_fauna("nova_arcadia"):
        pytest.skip("sem fauna de Nova Arcadia")
    from services import fauna

    def mute(fn):
        def wrapped(*a, **k):
            _text, upd = fn(*a, **k)
            return "", upd

        return wrapped

    for name in ("scene_block", "convert_to_signal", "track_signal"):
        monkeypatch.setattr(fauna, name, mute(getattr(fauna, name)))
    res = EV.run(3, 20, "nova_arcadia")
    on = res["on"]
    assert on["combats_with_entry"] > 0
    assert on["precedido"] > 0  # o antigo e enganado
    assert on["precedido_oraculo"] == 0
    assert on["sinais_emitidos"] == 0
    assert res["spec370"]["passed"]["M1"] is False


# --------------------------------------------------------------------------- por regiao


def test_m1_oraculo_proprio(region):
    res = _result(region)
    on, mm = res["on"], res["spec370"]["metrics"]
    assert on["combats_with_entry"] > 0
    assert mm["M1_precedido_oraculo"] >= 0.70, mm
    assert mm["M1_aproximacao"] >= 1.00, mm
    assert on["sinais_sem_dono"] == 0, on


def test_m2_horario(region):
    res = _result(region)
    assert res["dist"]["m2"], "nenhuma criatura com horario restrito"
    assert res["metrics"]["M2_pior_razao"] <= 0.35, res["dist"]["m2"]


def test_m3_cadeia_alimentar(region):
    res = _result(region)
    s = res["spec370"]
    if not res["dist"]["m3_up"] and not res["dist"]["m3_down"]:
        assert s["passed"]["M3"] is None and s["na"].get("M3"), "N/A sem motivo"
        return
    assert "M3" not in s["na"]
    if res["dist"]["m3_up"]:
        assert res["metrics"]["M3_presa_sobe_min"] >= 1.5, res["dist"]["m3_up"]
    if res["dist"]["m3_down"]:
        assert res["metrics"]["M3_predador_cai_max"] <= 0.6, res["dist"]["m3_down"]


def test_m4_territorio(region):
    res = _result(region)
    s = res["spec370"]
    if s["nodes"] < 2:
        assert s["passed"]["M4"] is None and s["na"].get("M4")
        return
    assert "M4" not in s["na"]
    assert res["metrics"]["M4_territorio"] >= 0.80, res["metrics"]


def test_m5_regiao_informativo_e_gatilhos(region):
    res = _result(region)
    assert res["off"]["fauna_combats"] > 0
    assert res["off"]["triggers"] == res["on"]["triggers"]  # R9 da 360: so QUEM, nunca QUANTOS
    d = res["spec370"]["metrics"]["M5_regiao_delta"]
    assert res["spec370"]["m5_alerta"] == (not (-0.30 <= d <= 0.10))


def test_m6_vazamento(region):
    res = _result(region)
    assert res["metrics"]["M6_vazamentos"] == 0, res["leak_samples"]
    assert res["on"]["texts"] > 0


def test_m8_densidade(region):
    res = _result(region)
    assert res["spec370"]["metrics"]["M8_densidade"] <= 0.40, res["spec370"]["metrics"]


def test_m7_reduzido(region):
    if not _has_fauna(region):
        pytest.skip(f"{region}: sem data/bestiario/fauna/{region}.yaml (lote futuro)")
    a = EV.run(3, 12, region)
    b = EV.run(3, 12, region)
    assert EV._digest(a) == EV._digest(b)
    assert EV.render_full(a) == EV.render_full(b)


def test_veredito_regiao(region):
    assert EV.gate_ok(_result(region)), _result(region)["spec370"]["passed"]


# --------------------------------------------------------------------------- NA e global


def test_m7_cheio_nova_arcadia():
    """D6: M7 no tamanho do relatorio (20 x 60) so em Nova Arcadia."""
    m7 = _result("nova_arcadia")["spec370"]["m7"]
    assert m7 and m7["igual"], m7


def test_nova_arcadia_caminho_360_e_relatorio_fresco():
    """R16/R22: o corpo da 360 sai igual e o relatorio publicado comeca com ele."""
    res = _result("nova_arcadia")
    body = EV.render(res)
    assert EV.render_full(res).startswith(body)
    report = (ROOT / "docs" / "spec360" / "eval-nova_arcadia.md").read_text(encoding="utf-8")
    assert report.startswith(body), "relatorio de NA desatualizado: rode eval.py --regiao"
    assert all(res["passed"].values()), res["passed"]  # oraculo antigo dentro dos limiares


def test_m5_global():
    results = {r: _result(r) for r in REGIONS if _has_fauna(r)}
    assert "nova_arcadia" in results
    g = EV.global_m5(results)
    assert g["regions"] == sorted(results)
    assert -0.20 <= g["M5_global_delta"] <= 0.05, g
    assert g["passed"] is True


def test_regiao_de_um_no_nao_quebra():
    """Ophidia tem 1 no raiz: a simulacao roda (a chegada volta ao mesmo no) e o M4 e N/A."""
    assert len(EV._region_nodes("ophidia")) == 1
    res = EV.run(1, 3, "ophidia")
    assert res["on"]["arrivals"] == 9
    assert res["spec370"]["passed"]["M4"] is None
