"""Suíte da spec conflito-12: loot e resumo canônico pós-conflito.

100% determinístico. Exercita `services/conflict_summary.py` (build_summary,
loot_context, contrato de não-reversão, fatos p/ archivist) e garante que
`economy.roll_loot` NÃO teve a assinatura mexida (risco §7)."""

import inspect

from services import conflict_summary as sm
from services import economy


def _p(name, **over):
    p = {"name": name, "dead": False, "conscious": True,
         "ferimentos": {"leve": [], "grave": [], "critico": []}}
    p.update(over)
    return p


# ==========================================================================
# Etapa 1 — build_summary (R2/R4)
# ==========================================================================
def test_build_summary_cobre_todos_os_campos():
    resumo = sm.build_summary([_p("herói")])
    for campo in sm.ConflictSummary.model_fields:
        assert campo in resumo                       # todos os 18 campos de R2 presentes


def test_summary_reflete_mortos_rendidos_fugitivos_corretamente():
    participantes = [
        _p("herói"),
        _p("orc_a", dead=True),
        _p("orc_b", surrendered=True),
        _p("orc_c", fled=True),
        _p("lacaio", conscious=False, incapacitated=True),
        _p("ferido", ferimentos={"leve": [], "grave": [{"regiao": "perna"}], "critico": []},
           scar_pending=True),
    ]
    r = sm.build_summary(participantes)
    assert r["mortos"] == ["orc_a"]
    assert r["rendidos"] == ["orc_b"]
    assert r["fugitivos"] == ["orc_c"]
    assert r["inconscientes"] == ["lacaio"]
    assert r["cicatrizes_a_gerar"] == ["ferido"]
    assert "ferido" in r["ferimentos"] and r["ferimentos"]["ferido"][0]["regiao"] == "perna"
    assert set(r["sobreviventes"]) == {"herói", "orc_b", "orc_c", "lacaio", "ferido"}


def test_summary_agrega_cartas_reveladas_e_fatos_de_fuga():
    scene = {"enemies": [{"name": "Afogado", "revealed_cards": ["maremoto"],
                          "revealed_resistances": ["gelido"]}],
             "objects": [{"id": "ponte", "name": "Ponte instável", "destroyed": True}]}
    chase = {"escapou": True, "fugitive_id": "herói"}
    deaths = [{"fatos_relacionais": ["Bran foi deixado para trás."]}]
    r = sm.build_summary([_p("herói")], scene=scene, chase_state=chase, death_outcomes=deaths)
    assert r["cartas_descobertas"] == ["maremoto"]
    assert r["resistencias_descobertas"] == ["gelido"]
    assert "Ponte instável" in r["objetos_utilizados"]
    assert "herói" in r["fugitivos"]
    assert "Bran foi deixado para trás." in r["fatos_de_relacao"]


# ==========================================================================
# Etapa 2 — integração de loot (R1) sem tocar economy.py
# ==========================================================================
def test_loot_recebe_conflict_scene_resolvido():
    resumo = sm.build_summary([_p("orc", dead=True)])
    ctx = sm.loot_context(resumo, region_id="planicie", encounter_level=6, danger_level=2)
    assert ctx["danger"] == 6                        # Nível do Encontro vence o danger bruto
    assert ctx["loot_source"] == "TREASURE"
    # sem encounter_level cai no danger_level
    assert sm.loot_context(resumo, danger_level=3)["danger"] == 3


def test_roll_loot_nao_muda_assinatura():
    # risco §7: a spec proíbe reescrever economy — a assinatura tem de continuar igual
    params = list(inspect.signature(economy.roll_loot).parameters)
    assert params == ["region_id", "danger", "rng", "projection",
                      "bestiary_knowledge", "turn", "boost"]


# ==========================================================================
# Etapa 3 — entrega à narrativa (R3) + fatos p/ archivist
# ==========================================================================
def test_narrativa_nao_pode_reverter_fato_do_resumo():
    resumo = sm.build_summary([_p("chefe", dead=True), _p("refem", captured=True)])
    # tentar reviver o morto → viola
    v = sm.validate_narrative_consistency(resumo, {"vivos": ["chefe"]})
    assert v["ok"] is False and v["violations"]
    # libertar capturado SEM novo acontecimento → viola; COM novo → ok
    assert sm.validate_narrative_consistency(resumo, {"libertados": ["refem"]})["ok"] is False
    assert sm.validate_narrative_consistency(
        resumo, {"libertados": ["refem"], "novo_acontecimento": True})["ok"] is True


def test_archivist_persiste_fatos_do_resumo():
    resumo = sm.build_summary(
        [_p("orc", dead=True)],
        extras={"fatos_de_relacao": ["A aldeia teme o herói agora."],
                "mudancas_permanentes_cenario": ["A ponte foi destruída."]})
    fatos = sm.summary_facts(resumo)
    assert "orc morreu no conflito." in fatos
    assert "A aldeia teme o herói agora." in fatos
    assert "A ponte foi destruída." in fatos
