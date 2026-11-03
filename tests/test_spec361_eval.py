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


# --------------------------------------------------------------------------------------------
# SPEC-374 Etapa E — idioma_pt sem empate falso (R4), latência do job (R5), protocolo de 2
# rodadas (R6/D6) e set de ajuste separado (R7). Autor de eval != executor de produto (R1).
# --------------------------------------------------------------------------------------------
AJUSTE = Path(__file__).parent / "fixtures" / "spec374_pedidos_ajuste.yaml"
# Registrado na SPEC-374 §9 (Etapa E). Mudar o set de ajuste exige nova autoria de eval.
SHA256_AJUSTE = "13ec924e27825bd64699fd474ac5661fb959870b41373a53e0162d44c80aa3df"
# Família que cada pedido `nova` do set de ajuste mira (declarada pelo autor do set; None =
# o pedido não nomeia família, como o em inglês e o de injeção).
FAMILIA_AJUSTE = {
    "ophidia_lama": "besta_entropia",
    "floresta_ossos": "corpo_reescrito",
    "skallgard_maga": "humanoide_preco",
    "pantano_inveja": "demonio_encarnado",
    "arcadia_barris": "besta_entropia",
    "xylos_raiz": "corpo_reescrito",
    "costa_trono": "demonio_encarnado",
    "pradaria_ingles": None,
    "montanhas_injecao": None,
    "brekmar_mago": "humanoide_preco",
    "aethelgard_casco": "besta_entropia",
}


def test_idioma_pt_sem_empate_falso():
    # R4: "a"/"as" são artigos do português; no inglês eram ruído e empatavam textos curtos.
    assert "a" not in ev._EN and "as" not in ev._EN
    assert {"a", "as"} <= ev._PT
    assert ev.eh_portugues("Abrir a Maré")
    assert not ev.eh_portugues("the claws of a beast")
    assert ev.eh_portugues("a as a")
    # a regra de empate não mudou (D1): empate com stopwords dos dois lados segue não-pt
    assert not ev.eh_portugues("de the")


def test_limiar_latencia_job():
    # R5/D2: o limiar mede o job (prazo de 30 s), não o turno.
    assert ev.LIMIARES["latencia_job_p95_ms"] == ("<=", 30000)
    assert "latencia_nova_p95_ms" not in ev.LIMIARES
    regs = [
        {"id": str(i), "forcar": "nova", "caminho": "nova", "latencia_ms": ms, "textos": []}
        for i, ms in enumerate([1000, 2000, 29000])
    ]
    m = ev.avaliar(regs)
    assert m["latencia_job_p95_ms"] == round(ev.percentil([1000, 2000, 29000], 95))
    assert "latencia_nova_p95_ms" not in m and m["latencia_nova_p50_ms"] == 2000
    assert ev.checar_limiares(m)["latencia_job_p95_ms"] is True
    m["latencia_job_p95_ms"] = 30001
    assert ev.checar_limiares(m)["latencia_job_p95_ms"] is False


def test_denominadores_explicitos():
    # P2-8 b: fisico/campos_349/vizinho_max medem só as fichas escritas (nova/legacy); as
    # `nova` que caíram em fallback ficam fora do denominador, e o número sai nas métricas.
    regs = [
        {
            "id": "a",
            "forcar": "nova",
            "caminho": "nova",
            "anatomia": "garras, dentes e cauda",
            "ficha": dict.fromkeys(ev.CAMPOS_349, "x"),
            "textos": [],
            "vizinho_max": 0.3,
        },
        {"id": "b", "forcar": "nova", "caminho": "fallback", "textos": []},
    ]
    m = ev.avaliar(regs)
    assert m["n_gerados"] == 1 and m["fisico"] == 1.0 and m["campos_349"] == 1.0
    # sem a lista de vizinhos, vale o vizinho_max já calculado por pedido
    assert m["vizinho_max"] == 0.3
    assert m["lint_primeira_n"] == 0


def _rodada(ok_primeira: int, *, n: int = 11, **extra) -> dict:
    regs = [
        {
            "id": f"r{i}",
            "forcar": "nova",
            "caminho": "nova",
            "lint_primeira": i < ok_primeira,
            "lint_final": True,
            "textos": ["um bicho de garras que morde a cauda"],
            "anatomia": "garras, dentes e cauda",
            "ficha": dict.fromkeys(ev.CAMPOS_349, "x"),
            "latencia_ms": 9000,
            "prompt_chars": 9000,
            "vizinhos": ["olhos de vidro"],
        }
        for i in range(n)
    ]
    regs.append(
        {
            "id": "auto",
            "forcar": "auto",
            "caminho": "variante",
            "caminho_esperado": "variante",
            "textos": [],
            "latencia_ms": 5,
        }
    )
    doc = {
        "modo": "depois",
        "real": True,
        "mock": False,
        "commit": "abc1234",
        "pedidos_sha256": SHA256_CONGELADO,
        "metricas": ev.avaliar(regs),
    }
    doc.update(extra)
    return doc


def test_protocolo_duas_rodadas():
    # R6/D6: agregado >= 16/22 e nenhuma rodada < 7/11; demais limiares em cada rodada.
    assert ev.PROTOCOLO["rodadas"] == 2
    assert ev.PROTOCOLO["pedidos_sha256"] == SHA256_CONGELADO
    assert ev.checar_protocolo([_rodada(8), _rodada(8)])["passou"] is True  # 16/22
    assert ev.checar_protocolo([_rodada(9), _rodada(7)])["passou"] is True  # 16/22, piso 7
    r = ev.checar_protocolo([_rodada(8), _rodada(7)])  # 15/22
    assert r["passou"] is False and r["lint_primeira_agregado"] == (15, 22)
    r = ev.checar_protocolo([_rodada(11), _rodada(6)])  # 17/22, mas uma rodada < 7/11
    assert r["passou"] is False and r["piso_rodada"] == [True, False]
    # 1 rodada só, ou 3, não é o protocolo
    assert ev.checar_protocolo([_rodada(11)])["passou"] is False
    assert ev.checar_protocolo([_rodada(9)] * 3)["passou"] is False
    # mock, outro set de pedidos, commits diferentes ou sem commit invalidam
    assert ev.checar_protocolo([_rodada(9), _rodada(9, mock=True)])["passou"] is False
    outro_set = _rodada(9, pedidos_sha256=SHA256_AJUSTE)
    assert ev.checar_protocolo([_rodada(9), outro_set])["passou"] is False
    assert ev.checar_protocolo([_rodada(9), _rodada(9, commit="def5678")])["passou"] is False
    assert ev.checar_protocolo([_rodada(9), _rodada(9, commit=None)])["passou"] is False
    sujo = {"commit": "abc1234+sujo"}
    assert ev.checar_protocolo([_rodada(9, **sujo), _rodada(9, **sujo)])["passou"] is False
    # outro limiar falhando numa rodada derruba o protocolo
    ruim = _rodada(9)
    ruim["metricas"]["digitos"] = 1
    r = ev.checar_protocolo([_rodada(9), ruim])
    assert r["passou"] is False and r["limiares_por_rodada"][1]["digitos"] is False
    # o lint_primeira de cada rodada não usa o 0,70 de uma rodada só (vale o piso)
    assert "lint_primeira" not in r["limiares_por_rodada"][0]


def _ajuste() -> list[dict]:
    return yaml.safe_load(AJUSTE.read_text(encoding="utf-8"))["pedidos"]


def test_pedidos_ajuste_congelados():
    raw = AJUSTE.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == SHA256_AJUSTE
    pedidos = _ajuste()
    assert len(pedidos) == 14 and len({p["id"] for p in pedidos}) == 14
    chaves = {"id", "pedido", "regiao", "location_id", "motivo_trama", "forcar", "caminho_esperado"}
    assert all(chaves <= set(p) for p in pedidos)
    novas = [p for p in pedidos if p["forcar"] == "nova"]
    autos = [p for p in pedidos if p["forcar"] == "auto"]
    assert len(novas) == 11 and len(autos) == 3
    assert all(p["caminho_esperado"] == "nova" for p in novas)
    assert len({p["regiao"] for p in novas}) >= 6
    assert {p["id"] for p in novas} == set(FAMILIA_AJUSTE)
    assert {f for f in FAMILIA_AJUSTE.values() if f} == {
        "corpo_reescrito",
        "besta_entropia",
        "humanoide_preco",
        "demonio_encarnado",
    }
    assert sum(1 for p in novas if not p["motivo_trama"]) == 3
    assert sum(1 for p in novas if not ev.eh_portugues(p["pedido"])) == 1
    assert sum(1 for p in novas if ev.digitos(p["pedido"])) == 1  # a tentativa de injeção
    assert sorted(p["caminho_esperado"] for p in autos) == ["existente", "existente", "variante"]
    var = next(p for p in autos if p["caminho_esperado"] == "variante")
    assert (var["base_esperada"], var["modificador_esperado"]) == (
        "enemy_aranha_lobo",
        "fugido_da_jaula",
    )
    # os locais existem no mapa
    import json

    mapa = json.loads(
        (Path(__file__).parents[1] / "data" / "world_map.json").read_text(encoding="utf-8")
    )
    ids = {n["id"] for n in mapa["locations"]}
    assert {p["location_id"] for p in pedidos} <= ids


def test_avaliador_protegido():
    # R8: avaliador, testes, sets e script de eval só mudam por autoria de eval.
    linhas = (
        (Path(__file__).parents[1] / "evals" / "protected-paths.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert {
        "services/creature_gen_eval.py",
        "tests/test_spec361_eval.py",
        "tests/fixtures/spec361_pedidos.yaml",
        "tests/fixtures/spec374_pedidos_ajuste.yaml",
        "scripts/bestiario/eval_geracao.py",
    } <= set(linhas)


def test_pedidos_ajuste_disjuntos():
    # R7: nenhum pedido igual ou paráfrase dos 14 medidos (Jaccard lexical < 0,6).
    from services import card_lint

    medidos = [p["pedido"] for p in _pedidos()]
    for p in _ajuste():
        assert p["pedido"] not in medidos
        pior = max(card_lint.similarity(p["pedido"], m) for m in medidos)
        assert pior < 0.6, (p["id"], pior)
