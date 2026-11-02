"""SPEC-361 Etapa 0 — eval congelado: pedidos (sha256) e métricas puras (§3.9)."""

import hashlib
from pathlib import Path

import yaml

from services import creature_gen_eval as ev

FIXTURE = Path(__file__).parent / "fixtures" / "spec361_pedidos.yaml"
# Registrado na SPEC-361 §9 (Etapa 0). Mudar o arquivo de pedidos exige nova spec/eval.
SHA256_CONGELADO = "baf3831005468ebae5d1e8e0237077fad6199aeee90907b8dfcc988d52db6dbc"


def _pedidos() -> list[dict]:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))["pedidos"]


def test_pedidos_congelados():
    raw = FIXTURE.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == SHA256_CONGELADO
    pedidos = _pedidos()
    assert len(pedidos) == 14
    ids = {p["id"] for p in pedidos}
    assert {"zhur_colmeia_auto", "zhur_colmeia_nova"} <= ids
    auto = next(p for p in pedidos if p["id"] == "zhur_colmeia_auto")
    assert (auto["caminho_esperado"], auto["base_esperada"], auto["modificador_esperado"]) == (
        "variante",
        "mon_saltador_de_palafita",
        "mente_unica",
    )
    novas = [p for p in pedidos if p["forcar"] == "nova" and p["id"] != "zhur_colmeia_nova"]
    assert len(novas) == 10
    assert len({p["regiao"] for p in novas}) >= 6
    assert sum(1 for p in novas if not p["motivo_trama"]) == 3
    existentes = [p for p in pedidos if p["caminho_esperado"] == "existente"]
    assert len(existentes) == 2 and all(p["forcar"] == "auto" for p in existentes)


def test_metricas_puras():
    assert ev.digitos("dê 999 de HP") == 3
    assert ev.digitos("duas pernas finas") == 0
    assert "troll" in ev.termos_proibidos("um troll de pedra")
    assert "hp" in ev.termos_proibidos("perde hp quando sangra")
    assert ev.termos_proibidos("um roedor de pernas de vidro") == []
    assert ev.eh_portugues("um roedor que pula sobre as pernas de vidro")
    assert not ev.eh_portugues("a drowned thing that crawls out of the tide")
    assert ev.eh_fisico("Tem garras, dentes curvos e uma cauda de placas.")
    assert not ev.eh_fisico("Uma presença fria com olhos.")
    assert ev.campos_349_ok(
        {"telegrafo": "x", "contra_jogo": "x", "gancho": "x", "aparencia": "x", "arte_visual": "x"}
    )
    assert not ev.campos_349_ok({"telegrafo": "x"})
    assert ev.percentil([1, 2, 3, 4], 50) == 2.5
    assert ev.percentil([], 95) == 0.0


def test_avaliar_e_limiares():
    regs = [
        {
            "id": "a",
            "forcar": "nova",
            "caminho": "nova",
            "lint_primeira": True,
            "lint_final": True,
            "textos": ["um bicho de garras e dentes que morde a cauda"],
            "anatomia": "garras, dentes e cauda",
            "ficha": dict.fromkeys(ev.CAMPOS_349, "x"),
            "latencia_ms": 3000,
            "prompt_chars": 9000,
            "vizinhos": ["olhos de vidro"],
        },
        {
            "id": "b",
            "forcar": "nova",
            "caminho": "fallback",
            "lint_primeira": False,
            "lint_final": False,
            "textos": [],
            "anatomia": "",
            "latencia_ms": 9000,
        },
        {
            "id": "c",
            "forcar": "auto",
            "caminho": "variante",
            "caminho_esperado": "variante",
            "textos": ["ficam parados com 3 olhos"],
            "anatomia": "pernas, olhos e boca",
            "ficha": None,
            "latencia_ms": 4,
        },
    ]
    m = ev.avaliar(regs)
    assert m["lint_primeira"] == 0.5 and m["fallback"] == 0.5 and m["caminho_ok"] == 1.0
    assert m["digitos"] == 1
    assert m["variante_vs_nova"] == {"variante": 1, "nova": 0}
    ok = ev.checar_limiares(m)
    assert ok["caminho_ok"] is True and ok["fallback"] is False and ok["digitos"] is False
    antes = ev.avaliar(regs, modo="antes")
    assert "lint_primeira" not in antes and ev.checar_limiares(antes)["lint_primeira"] is None
