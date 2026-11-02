"""SPEC-349 Etapa 1: gate de unicidade de criatura (services/bestiary_lint.py) + R33."""

from __future__ import annotations

import copy
import json

from services import bestiary_lint as bl
from services import content_validator as cv

BASE = {
    "id": "mon_a",
    "nome": "Roedor de Fundição",
    "status": "nova",
    "familia": "besta_entropia",
    "origem_lore": {"fonte": "abismo", "detalhe": None, "refs": []},
    "anatomia": {
        "plano_corporal": "quadrupede",
        "material": "ferro_ferrugem",
        "escala": "pequena",
        "locomocao": "anda",
        "percepcao": "calor",
        "texto": "Dorso de placas enferrujadas, dentes de rebite, pata torta e cauda de arame farpado.",
    },
    "silhueta": "Um arco de chapas pontudas rente ao chão.",
    "comportamento": "Rói forjas.",
    "papel_tatico": "batedor_rapido",
    "arquetipo": "predador",
    "categoria": "lacaio",
    "gancho": "Nasce onde o ferro escorre das fundições para o beco.",
    "habitat": ["na_anel_ferro"],
    "autor": "fable",
    "revisor_unicidade": "opus-reviewer",
    "revisao": "aprovada",
}


def ficha(**over) -> dict:
    f = copy.deepcopy(BASE)
    for k, v in over.items():
        if k in ("anatomia", "origem_lore"):
            f[k].update(v)
        else:
            f[k] = v
    return f


def distinta() -> dict:
    return ficha(
        id="mon_b",
        nome="Tecelã de Cera",
        familia="corpo_reescrito",
        anatomia={
            "plano_corporal": "bipede_ereto",
            "material": "cera_sebo",
            "escala": "humana",
            "locomocao": "escala_paredes",
            "percepcao": "som",
            "texto": "Tronco derretido, braços longos de sebo, mãos de muitos dedos e rosto liso sem olhos.",
        },
        silhueta="Uma torre mole de mãos penduradas no teto.",
        papel_tatico="controlador",
        arquetipo="controlador",
        gancho="Tece redes de cera nos corredores dos Jardins para prender o que passa.",
    )


def codes(issues, level=None):
    return {i.code for i in issues if level is None or i.level == level}


def regiao(fichas, **kw):
    return bl.lint_regiao("x", fichas, bestiary={}, codex_docs=[], cotas={}, **kw)


def test_reskin_sintetico_pego():
    a = ficha()
    b = ficha(
        id="mon_c",
        nome="Fuçador Negro",
        anatomia={
            "material": "escoria_fuligem",
            "locomocao": "salta",
            "texto": a["anatomia"]["texto"]
            .replace("enferrujadas", "queimadas")
            .replace("rebite", "brasa"),
        },
        silhueta="Tigela invertida de fuligem sobre quatro patas finas.",
        gancho="Escapa de buracos na terra molhada depois de cada chuva.",
        papel_tatico="emboscador",
    )
    assert "U6" in codes(regiao([a, b]), "error")


def test_variante_pega():
    assert "U5" in codes(bl.lint_ficha(ficha(nome="Rato Alfa")))
    assert "U5" in codes(bl.lint_ficha(ficha(silhueta="Um filhote de chapas.")))


def test_nucleo_repetido_pego():
    a = ficha(nome="Cão de Rebite")
    b = distinta()
    b["nome"] = "Cão de Fuligem"
    assert bl.nucleo_nome("Cão de Rebite") == bl.nucleo_nome("Cão de Fuligem")
    assert "U4" in codes(regiao([a, b]), "error")


def test_tripla_repetida_pega():
    a = ficha()
    b = distinta()
    b["anatomia"].update(plano_corporal="quadrupede", material="ferro_ferrugem")
    b["papel_tatico"] = "batedor_rapido"
    assert "U2" in codes(regiao([a, b]), "error")


def test_eixos_demais_iguais():
    a = ficha()
    b = distinta()
    b["anatomia"].update(plano_corporal="quadrupede", material="ferro_ferrugem", escala="pequena")
    # 3 iguais (plano, material, escala) + papel diferente -> ok
    assert bl.eixos_iguais(a, b) == 3
    assert "U3" not in codes(regiao([a, b]))
    b["anatomia"]["locomocao"] = "anda"
    assert bl.eixos_iguais(a, b) == 4
    assert "U3" in codes(regiao([a, b]), "error")


def test_conceitual_pego():
    assert "U9" in codes(
        bl.lint_ficha(ficha(anatomia={"texto": "Uma presença sem corpo que paira sobre o beco."}))
    )
    assert "U9" in codes(
        bl.lint_ficha(ficha(anatomia={"texto": "Algo frio e escuro."}))
    )  # < 3 partes


def test_generico_pego():
    assert "U8" in codes(bl.lint_ficha(ficha(nome="Golem de Lixo")))
    assert "U8" in codes(bl.lint_ficha(ficha(silhueta="Um tank de chapas.")))  # léxico de Cartas


def test_demonio_sem_npc_valido():
    f = ficha(
        familia="demonio_encarnado", origem_lore={"fonte": "demonio", "detalhe": "npc_inexistente"}
    )
    assert "U10" in codes(bl.lint_ficha(f))
    f["origem_lore"]["detalhe"] = "npc_fehk"
    assert "U10" not in codes(bl.lint_ficha(f))
    assert "U10" in codes(
        bl.lint_ficha(ficha(familia="corpo_reescrito", origem_lore={"fonte": "outro"}))
    )
    assert "U10" in codes(bl.lint_ficha(ficha(familia="humanoide_preco")))
    assert "U10" in codes(
        bl.lint_ficha(
            ficha(
                origem_lore={
                    "fonte": "abismo",
                    "refs": ["lore_nova/timeline_completa.txt:99999999"],
                }
            )
        )
    )
    assert "U10" not in codes(
        bl.lint_ficha(
            ficha(origem_lore={"fonte": "abismo", "refs": ["lore_nova/timeline_completa.txt:20"]})
        )
    )


def test_revisor_igual_autor():
    assert "U11" in codes(bl.lint_ficha(ficha(revisor_unicidade="fable")))
    assert "U11" in codes(bl.lint_ficha(ficha(revisao="pendente")))
    assert "U11" in codes(bl.lint_ficha(ficha(revisor_unicidade="pendente")))
    assert "U11" not in codes(bl.lint_ficha(ficha(revisao="pendente"), exigir_revisao=False))
    assert not bl.lint_ficha(ficha(status="retro", revisao="pendente", nome="Rato Alfa"))


def test_par_distinto_passa():
    assert not codes(bl.lint_ficha(ficha()), "error")
    assert not codes(regiao([ficha(), distinta()]), "error")


def test_retro_x_retro_e_aviso():
    a = ficha(status="retro", id="mon_r1", nome="Rato da Peste")
    b = ficha(status="retro", id="mon_r2", nome="Rato de Caldeira")
    iss = regiao([a, b])
    assert {"U2", "U3", "U4", "U6"} & codes(iss, "warn")
    assert not codes(iss, "error")
    # com uma nova no par vira erro
    c = ficha(id="mon_r3", nome="Rato Cinzento")
    assert "U4" in codes(regiao([a, c]), "error")


def test_cotas_regiao():
    fs = [ficha(), distinta()]
    iss = bl.lint_regiao("x", fs, bestiary={}, codex_docs=[], cotas=bl.COTAS_PADRAO)
    assert "U12" in codes(iss, "error")
    # retro não conta
    assert bl.contar_cotas([ficha(status="retro")])["total"] == 0
    assert bl.contar_cotas(fs)["total"] == 2
    # D3: reinventada/adotada não entra no total (ocupa slot), mas conta na família
    c = bl.contar_cotas([ficha(), dict(distinta(), status="reinventada")])
    assert c["total"] == 1 and c["familias"]["corpo_reescrito"] == 1
    assert "U12" in codes(
        bl.lint_vagas(
            [{"vaga": 1, "familia": "corpo_reescrito", "categoria": "padrao"}], bl.COTAS_PADRAO
        )
    )


def test_vagas_u2_u3():
    v = {
        "familia": "corpo_reescrito",
        "categoria": "padrao",
        "papel_tatico": "quebra_defesa",
        "arquetipo": "bruto",
        "plano_corporal": "bipede_curvado",
        "material": "osso",
    }
    v2 = dict(v, vaga=2)
    v1 = dict(v, vaga=1)
    iss = bl.lint_vagas([v1, v2], {})
    assert "U2" in codes(iss, "error")


def test_padrao_assinatura_duplicados():
    a = ficha(padrao=["ataque", "defesa"], a_cada_n=3, telegrafo="{nome} range os dentes de ferro.")
    b = distinta()
    b.update(padrao=["ataque", "defesa"], a_cada_n=3, telegrafo="{nome} range os dentes de ferro.")
    assert "U13" in codes(regiao([a, b]), "error")
    b["padrao"] = ["mover", "enfraquecer"]
    b["telegrafo"] = "Fios de cera descem do teto sobre você."
    assert "U13" not in codes(regiao([a, b]))


def test_carta_propria_compartilhada_pega():
    a = ficha(mecanica_assinatura={"carta": "cri_x", "frase": "x"})
    b = distinta()
    b["mecanica_assinatura"] = {"carta": "cri_x", "frase": "y"}
    assert "U7" in codes(regiao([a, b]), "error")


def test_u1_id_nome_unicos():
    a = ficha()
    docs = [{"id": "mon_outro", "name": "Roedor de Fundição", "tags": [], "body": ""}]
    iss = bl.lint_regiao("x", [a], bestiary={}, codex_docs=docs, cotas={})
    assert "U1" in codes(iss, "error")
    assert "U1" in codes(regiao([ficha(nome="Rato")]))  # 1 palavra
    best = {"mon_z": {"name": "Roedor Fundição"}}
    assert "U1" in codes(bl.lint_regiao("x", [a], bestiary=best, codex_docs=[], cotas={}), "error")


def test_u6_contra_codex_da_regiao():
    a = ficha()
    doc = {"id": "mon_velho", "name": "Velho", "tags": ["x"], "body": a["anatomia"]["texto"]}
    assert "U6" in codes(bl.lint_regiao("x", [a], bestiary={}, codex_docs=[doc], cotas={}), "error")
    doc["tags"] = ["outra"]
    assert "U6" not in codes(bl.lint_regiao("x", [a], bestiary={}, codex_docs=[doc], cotas={}))


def test_lint_global_r29():
    a = ficha(familia="demonio_encarnado", origem_lore={"fonte": "demonio", "detalhe": "npc_fehk"})
    b = ficha(
        id="mon_z",
        nome="Outro Nome Aqui",
        familia="demonio_encarnado",
        origem_lore={"fonte": "demonio", "detalhe": "npc_fehk"},
    )
    b["silhueta"] = "Totalmente diferente e longa descrição de contraluz com sinos."
    iss = bl.lint_global({"r1": [a], "r2": [b]})
    assert "R29" in codes(iss, "error")  # mesma anatomia de cria do mesmo demônio
    c = ficha(id="mon_c", nome=a["nome"])
    assert "R29" in codes(bl.lint_global({"r1": [a], "r2": [c]}), "error")  # nome repetido


def _cards(path, ids):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"cards": [{"id": i, "oculta": True} for i in ids]}), encoding="utf-8"
    )


def _real(cid):
    with open("data/bestiary.json", encoding="utf-8") as f:
        return json.load(f)[cid]


def test_validate_bestiary_acha_carta_em_subpasta(tmp_path):
    cre = _real("mon_cao_rebite")
    _cards(tmp_path / "cards" / "criaturas" / "x.json", cre["cartas"])
    bp = tmp_path / "b.json"
    bp.write_text(json.dumps({"mon_cao_rebite": cre}), encoding="utf-8")
    out = cv.validate_bestiary(str(bp), str(tmp_path / "cards"))
    assert not [f for f in out if "inexistente" in f.message]


def test_anticlone_vale_para_bestiario_349(tmp_path):
    a = _real("mon_cao_rebite")
    b = copy.deepcopy(a)
    a["origem"] = b["origem"] = "bestiario-349"
    b["id"] = "mon_clone"
    _cards(tmp_path / "cards" / "x.json", a["cartas"])
    bp = tmp_path / "b.json"
    bp.write_text(json.dumps({"mon_cao_rebite": a, "mon_clone": b}), encoding="utf-8")
    out = cv.validate_bestiary(str(bp), str(tmp_path / "cards"))
    assert [f for f in out if "clone tático" in f.message]
