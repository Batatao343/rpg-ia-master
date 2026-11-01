"""SPEC-348 — canon da lore de Valoria: cronologia, pacto, Praga, mundo, grafo, expansões,
Posturas e dados de mundo (R6-R51)."""

from __future__ import annotations

import re

import pytest

from tests.spec348_helpers import (
    ROOT,
    codex_docs,
    doc,
    fold,
    hidden_docs,
    load_json,
    lore_text,
    public_docs,
)

LEXICO = ROOT / "data" / "cards" / "_lexico_valoria.txt"


def _forbidden_terms() -> list[str]:
    terms, on = [], False
    for ln in LEXICO.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln == "[proibidos]":
            on = True
            continue
        if ln.startswith("["):
            on = False
        if on and ln and not ln.startswith("#"):
            terms.append(ln.lower())
    return terms


def _has_forbidden(text: str) -> list[str]:
    plain = fold(text)
    return [t for t in _forbidden_terms() if re.search(rf"\b{re.escape(t)}\b", plain)]


def _public_text(prefix: str | None = None) -> str:
    return " ".join(
        d["text"] for d in public_docs() if prefix is None or d["id"].startswith(prefix)
    )


def _hidden_with(*terms: str) -> list[str]:
    return [d["id"] for d in hidden_docs() if all(fold(t) in d["text"] for t in terms)]


def _public_with(*terms: str) -> list[str]:
    return [d["id"] for d in public_docs() if all(fold(t) in d["text"] for t in terms)]


# ---------------------------------------------------------------- cronologia (R6-R15)


def test_era7_public_anchor_has_dates_and_no_hidden_dates():
    timeline = " ".join(d["text"] for d in public_docs() if d["id"].startswith("timeline_e7"))
    for phrase in (
        "ha quarenta e cinco anos",
        "ha quarenta e quatro",
        "elaryin morreu ha quarenta e um",
        "lorde protetor ha quarenta",
        "ha trinta anos",
        "primeira onda da praga de ferro",
    ):
        assert phrase in timeline, phrase
    for hidden in (
        "entre quarenta e quatro e vinte e nove",
        "acordo de trinta anos",
        "caixa de amostras",
        "cepa atual",
        "pacto com daruun",
        "armadura de malagor, interface",
    ):
        assert hidden not in _public_text(), hidden


def test_hidden_chronology_block():
    found = [
        d
        for d in hidden_docs()
        if "cronologia que ninguem escreve" in d["text"] and d["type"] == "secret"
    ]
    assert found
    body = found[0]["text"]
    for needle in (
        "pacto de valerius",
        "decimo ano do governo",
        "mesma noite do codigo de ferro",
        "guilda dos corvos e o doutor vane",
        "entre quarenta e quatro e vinte e nove anos atras",
        "caixa de amostras chegou a vane ha quinze anos",
    ):
        assert needle in body, needle


def test_no_stale_phrases_in_lore_nova():
    secrets = fold(lore_text("secrets.txt"))
    timeline = lore_text("timeline_completa.txt")
    flat = fold(timeline)
    assert "durante a guerra das cinzas" not in secrets
    assert "por decadas, nova arcadia" not in flat
    assert "como sempre faz a cada dois mil anos" not in flat
    assert "decadas de imersao" not in fold(lore_text("locations.txt"))
    assert "os seis dragoes que sobreviveram a guerra — vorrnak" not in flat
    for name in ("npcs.txt", "races.txt", "locations.txt", "factions.txt", "creatures.txt"):
        assert "governante de brekmar" not in fold(lore_text(name)), name
    npcs = fold(lore_text("npcs.txt"))
    assert "dois unicos sobreviventes de infeccao" not in npcs
    assert "nao simbiotico" in npcs
    assert "nao e doenca natural" not in secrets
    era5 = next(ln for ln in timeline.splitlines() if ln.startswith("ERA 5"))
    era6 = next(ln for ln in timeline.splitlines() if ln.startswith("ERA 6"))
    assert "sem sombra" not in fold(era5)
    assert "sem sombra" in fold(era6)
    assert "pacto" not in fold(era6)


def test_pact_story_is_hidden_and_single_version():
    layered = _hidden_with("daruun", "armadura de malagor", "decimo ano")
    assert layered
    from services.secret_signatures import SECRET_SIGNATURES

    for sig in SECRET_SIGNATURES["pacto_valerius"]:
        assert not [d for d in public_docs() if fold(sig) in d["text"]], sig
    # camadas: corretor/interface/preço/efeito colateral aparecem juntos no segredo central
    core = next(d for d in hidden_docs() if "valerius e um lich" in d["text"])
    for needle in ("corretor", "interface", "familia", "efeito colateral"):
        assert needle in core["text"], needle
    assert "guerra das cinzas" not in core["text"]


def test_plague_chain_present():
    pub = _public_text()
    assert "morrakh" in pub and "primeira onda da praga" in pub
    assert _hidden_with("caixa", "vane", "cepa atual")
    assert not _public_with("caixa de amostras")
    laboratory = next(d for d in hidden_docs() if "criada em laboratorio" in d["text"])
    assert "cepa atual" in laboratory["text"]
    chain = _hidden_with("assinatura e do abismo", "morrakh carrega")
    assert chain


def test_calendar_year_base_and_protocol_explained():
    cal = load_json("data/world/calendar.json")
    assert cal["constants"]["YEAR_BASE"] == 112
    assert cal["year_review"] == "aprovado"
    era7 = " ".join(d["text"] for d in public_docs() if d["id"].startswith("timeline_e7"))
    assert "livro do protocolo dos anoes" in era7 and "ano 112" in era7
    assert "termina no 67" in era7 and "fundacao e no 68" in era7
    assert (
        "a guerra comeca no ano 1" not in _public_text()
        and "sessenta e seis anos" not in _public_text()
    )
    assert "monte da perdicao voltou a fumegar" in era7


# ---------------------------------------------------------------- mundo (R22-R28)


def test_world_fixes_present():
    pub = _public_text()
    # R22 Aethelgard: lago de cratera, salobro, garganta para o mar
    aeth = doc("aethelgard")["text"]
    assert "lago de cratera" in aeth and "salobra" in aeth and "eras de imersao" in aeth
    # R23 onze Landships
    assert "onze navegam" in pub and "em manutencao prolongada" in pub
    assert "ls-pfc-9" not in pub
    # R24 estrelas
    assert "da borda nao se veem estrelas" in pub
    # R25 Verme: hidden
    assert _hidden_with("verme-primordial", "o rei perdeu essa guerra")
    # R26 dor / Lista de Fornalha
    assert "o custo e dor" in pub and "lista de fornalha" in pub
    assert "mais acessivel para um cinzeu" not in fold(lore_text("npcs.txt"))
    # R27 Deuses Antigos: público só "havia, e não há mais"; liturgia oculta
    assert "havia, e nao ha mais" in pub
    assert _hidden_with("sobrou da liturgia")
    assert not _public_with("sobrou da liturgia")
    # R28 lua lançada com magia
    assert "milhares de elfos foram queimados" in pub
    # R12/R13/R14
    assert "falha critica de contencao" in pub and "dia sem sombra" in pub
    assert "brekmar comecou como lugar de fuga" in pub
    assert "thessrak foi selado" in pub


def test_kahen_title_arbitro():
    npc = doc("npc_kahen")
    assert "arbitro de brekmar" in npc["text"]
    assert "governante de brekmar" not in _public_text()


def test_elaryin_official_version_public_real_cause_hidden():
    assert "bebeu ate morrer" in _public_text()
    assert not _public_with("elaryin", "overdose")
    assert _hidden_with("elaryin", "overdose de po de fada")


# ---------------------------------------------------------------- grafo (R31-R33, R48)


def _edges() -> list[dict]:
    return load_json("data/graph/edges.json")


def _entity_ids() -> set[str]:
    ids = set(load_json("data/graph/entities.json"))
    ids |= set(load_json("data/graph/entities_extra.json"))
    return ids


def test_graph_new_leads_and_located_in():
    rel = load_json("data/graph/relation_types.json")
    by_id = {e["id"]: e for e in _edges()}
    expected = {
        "e_morvan_lidera_cidades": (
            "npc_keeper_morvan",
            "leads",
            "cidades_estado_sobreviventes_vaelorn_solvhen",
        ),
        "e_morvan_em_solvhen": ("npc_keeper_morvan", "located_in", "pr_solvhen"),
        "e_mae_corva_lidera_corvos": ("npc_mae_corva", "leads", "guilda_corvos"),
        "e_sennar_lidera_chama_azul": (
            "npc_sennar_o_pregador_da_cicatriz",
            "leads",
            "filhos_chama_azul",
        ),
    }
    ents = _entity_ids()
    for eid, (src, typ, tgt) in expected.items():
        e = by_id[eid]
        assert (e["source"], e["type"], e["target"]) == (src, typ, tgt)
        assert typ in rel and src in ents and tgt in ents
    assert by_id["e_sennar_membro_legiao"]["visibility"] == "hidden"


def test_cidades_keep_living_leader_when_aerwen_dies():
    from services import npc_world

    fac = "cidades_estado_sobreviventes_vaelorn_solvhen"
    leaders = {n: f for n, f in npc_world.leaders().items() if f == fac}
    assert {"npc_lady_aerwen", "npc_keeper_morvan"} <= set(leaders)
    sim = {"npcs": {}}
    state = {"world_projection": {"entities": {"npc_lady_aerwen": {"alive": False}}}}
    living = [n for n in leaders if not npc_world._is_dead(state, n, {}, sim)]
    assert living == ["npc_keeper_morvan"]
    # a morte tambem vale pelo estado da simulacao
    sim = {"npcs": {"npc_lady_aerwen": {"dead": True}}}
    living = [n for n in leaders if not npc_world._is_dead({}, n, {}, sim)]
    assert living == ["npc_keeper_morvan"]


def test_quebrados_faction_public_without_diary():
    fac = doc("quebrados")
    assert fac["visibility"] == "public" and fac["type"] == "faction"
    assert "elaryin" in fac["text"] and "diario" not in fac["text"]
    assert _hidden_with("quebrados", "diario em codigo", "aprendiz foi heroi")


def test_autoria_declares_mundo_vivo_canon():
    text = fold((ROOT / "docs/guias/AUTORIA.md").read_text(encoding="utf-8"))
    assert "mundo_vivo" in text and "segunda camada" in text


def test_delivery_route_uses_vorr_ingot():
    routes = load_json("data/world/lore_quests.json")["delivery_routes"]
    route = next(r for r in routes if r["id"] == "minerio_skallgard_brekmar")
    assert route["item_id"] == "lingote_aco_vorr"
    assert "review" not in route and route["lore_keyword"] == "Vorr"
    art = load_json("data/artifacts.json")
    assert art["lingote_aco_vorr"]["type"] == "material"


def test_vorr_route_is_fulfillable_and_profitable():
    cfg = load_json("data/world/lore_quests.json")
    route = next(r for r in cfg["delivery_routes"] if r["id"] == "minerio_skallgard_brekmar")
    world = {loc["id"]: loc for loc in load_json("data/world_map.json")["locations"]}
    sellers = [
        m
        for m in load_json("data/merchants.json").values()
        if route["item_id"] in m["base_stock"]
        and world[m["location_id"]].get("region_id") == route["origin_region"]
    ]
    assert sellers, "nenhum mercador da regiao de origem vende o item da rota"
    value = load_json("data/artifacts.json")[route["item_id"]]["value_gold"]
    cost = route["qty"] * value * min(m["price_mult"] for m in sellers)
    assert cost <= max(cfg["rewards"]["entregar_material"]), cost


# ---------------------------------------------------------------- expansões (R50-R51)

# (id, destino, visibilidade, frases-chave dobradas — todas devem estar no mesmo doc)
EXPANSIONS = [
    ("E-01", "hidden", ["ilsa", "colina cinza", "herdeira"]),
    ("E-02", "hidden", ["bertil", "decimo ano", "armadura"]),
    ("E-03", "hidden", ["pagina arrancada", "mercado de carne"]),
    ("E-04", "hidden", ["sennar", "alistado nos rolos da legiao"]),
    ("E-05", "hidden", ["aco de sangue lembra", "encapuzados"]),
    ("E-06", "hidden", ["marcados", "assinatura de morrakh", "quase-parentes"]),
    ("E-08", "hidden", ["coroa de pressao", "sob o gelo", "so quem guarda o ultimo martelo"]),
    ("E-10", "public", ["salao do juramento", "assento central esta vazio"]),
    ("E-11", "hidden", ["kahen", "vergonha", "numero"]),
    ("E-12", "hidden", ["povo-recife", "uma alma por casco"]),
    ("E-13", "hidden", ["groth", "recibo", "kahen"]),
    ("E-14", "hidden", ["veneno de ophidia", "contra a praga"]),
    ("E-15", "hidden", ["ampulheta de vaelorn", "aerwen troca os proprios anos"]),
    ("E-16", "hidden", ["solvhen", "sonho coletivo", "solvhara"]),
    ("E-19", "hidden", ["morvath", "thessrak vivo"]),
    ("E-20", "hidden", ["diario em codigo", "aprendiz"]),
    ("E-24", "hidden", ["bigornas", "ultimos anoes", "protecao"]),
]


@pytest.mark.parametrize("eid,vis,phrases", EXPANSIONS, ids=[e[0] for e in EXPANSIONS])
def test_each_expansion_has_canonical_text(eid, vis, phrases):
    pool = hidden_docs() if vis == "hidden" else public_docs()
    assert [d["id"] for d in pool if all(p in d["text"] for p in phrases)], (eid, phrases)


def test_public_sides_of_expansions():
    pub = _public_text()
    assert 'o casco "toma a sua"' in pub
    assert "as bigornas estao quentes" in doc("ma_forja_profunda")["text"]
    assert "ninguem diz quem as alimenta" in doc("ma_forja_profunda")["text"]
    assert "quieto demais" in doc("pr_solvhen")["text"]
    assert "nao sao os de aethelgard" in doc("pm_cripta_afogada")["text"]


def test_forja_text_does_not_explain_orcs():
    for text in (fold(lore_text("secrets.txt")),):
        block = text.split("as bigornas da forja profunda estao quentes por um contrato", 1)[1]
        block = block.split("[categoria:", 1)[0]
        assert "orc" not in block and "goblin" not in block
    pub = doc("ma_forja_profunda")["text"]
    assert "orc" not in pub


# ---------------------------------------------------------------- Posturas (R47-R49)

POSTURAS = {
    "Devoto do Abismo": ("ama", "npc_hrefna_da_vigilia", "clas tecnologicos"),
    "Sangromante": ("negocia", "npc_oriel_talho_fundo", "legiao de ferro"),
    "Corruptor": ("trabalha junto", "npc_mairen_das_margens", "druidas do ciclo cinzento"),
    "Arcanista Cinzento": ("manipula", "npc_hask_o_musgo", "druidas-renegados"),
    "Médico de Campo": ("nega", "npc_benedita_a_parteira", "guilda dos corvos"),
}


def test_posturas_doc_curated_public_and_complete():
    d = doc("story_posturas")
    assert d["visibility"] == "public" and d["fm"].get("curated") is True
    classes = load_json("data/classes.json")
    assert set(classes) == set(POSTURAS)
    text = d["text"]
    for name, (verb, master, enemy) in POSTURAS.items():
        assert fold(name) in text, name
        assert verb in text and enemy in text, name
        mname = doc(master)["fm"]["name"]
        assert fold(mname.split(",")[0].split(" — ")[0]) in text, mname
        assert classes[name]["posture"] == verb
    assert text.count("rumor de origem") == 5
    assert "entropia" in text and "carga do abismo" in text


def test_posturas_masters_are_graph_npcs():
    ents = load_json("data/graph/entities.json")
    edges = _edges()
    for _name, (_verb, master, _enemy) in POSTURAS.items():
        assert ents[master]["type"] == "npc"
        mine = [e for e in edges if e["source"] == master]
        assert any(e["type"] == "located_in" for e in mine), master
        for e in mine:
            assert e["target"] in _entity_ids(), (master, e["target"])
            assert e["type"] != "enemy_of"
    assert not [
        e
        for e in edges
        if e["id"].startswith(("e_hrefna", "e_oriel", "e_mairen", "e_hask", "e_benedita"))
        and e["type"] == "enemy_of"
    ]
    # só Benedita e Hrefna não têm facção própria de origem obrigatória? ambas conferidas acima
    members = [
        e
        for e in edges
        if e["type"] == "member_of" and e["source"] in {m[1] for m in POSTURAS.values()}
    ]
    assert len(members) == 3  # Hrefna, Oriel, Hask; Mairen saiu do culto e Benedita nao tem faccao


def test_posturas_no_mechanics_no_forbidden_terms():
    text = doc("story_posturas")["body"]
    assert not re.search(r"\d", text)
    assert "carta" not in fold(text)
    assert not _has_forbidden(text)


NEW_DOC_IDS = [
    "story_posturas",
    "pm_cripta_afogada",
    "pr_solvhen",
    "ma_forja_profunda",
    "quebrados",
    "npc_hrefna_da_vigilia",
    "npc_oriel_talho_fundo",
    "npc_mairen_das_margens",
    "npc_hask_o_musgo",
    "npc_benedita_a_parteira",
    "npc_ilsa",
    "npc_bertil",
    "npc_sennar_o_pregador_da_cicatriz",
]
NEW_SECRET_TITLES = [
    "cronologia que ninguem escreve",
    "ilsa, a remendeira, e a herdeira",
    "a pagina que falta",
    "o aco de sangue lembra",
    "os marcados resistem",
    "a decima segunda landship",
    "o estaleiro das almas cobra",
    "o veneno de ophidia e o que as ilhas",
    "solvhen dorme",
    "morvath mantem thessrak",
    "o diario em codigo dos quebrados",
    "as bigornas da forja profunda",
]


def _new_docs_text() -> str:
    parts = []
    for d in codex_docs():
        base = d["id"].removesuffix("_segredo")
        if base in NEW_DOC_IDS:
            parts.append(d["body"])
        elif d["type"] == "secret" and any(t in fold(d["body"][:200]) for t in NEW_SECRET_TITLES):
            parts.append(d["body"])
    return " ".join(parts)


def test_new_texts_no_forbidden_lexicon():
    new = _new_docs_text()
    assert len(new) > 8000  # pegou os docs novos
    assert not _has_forbidden(new), _has_forbidden(new)


# ---------------------------------------------------------------- dados de mundo (R43-R46)

NEW_RUMOR_SEEDS = {
    "rumor_um_morto_ainda_varre_o_crematorio": ("baixa", True),
    "rumor_o_pregador_tem_a_cicatriz_da_legiao": ("media", True),
    "rumor_o_arbitro_de_brekmar_tem_um_numero_gravado": ("media", True),
    "rumor_os_que_velam_no_gelo_pedem_para_ser_escolhidos": ("alta", True),
    "rumor_em_brekmar_se_paga_o_eter_em_sangue_e_a_legiao_queima_quem_aprende": ("alta", True),
    "rumor_ha_quem_cure_apodrecendo_mais_depressa": ("baixa", False),
    "rumor_os_druidas_cinzentos_guardam_o_que_sobrou_de_aethelgard": ("media", True),
    "rumor_a_parteira_do_anel_de_lama_ensina_a_costurar_quem_a_praga_quer": ("alta", True),
}


def _lore_seeds() -> dict:
    seeds = load_json("data/world/rumor_seeds.json")["seeds"]
    return {k: v for k, v in seeds.items() if v["family"] == "lore"}


def test_guardian_rumor_true():
    seed = _lore_seeds()["rumor_o_guardiao_do_farol_era_um_de_nos"]
    assert seed["truth"] is True and seed["secret_id"] == "farol_chama_negra"


def test_false_ratio_in_range():
    lore = {k: v for k, v in _lore_seeds().items() if not v.get("disabled")}
    assert len(lore) == 48
    ratio = sum(1 for s in lore.values() if not s["truth"]) / len(lore)
    assert 0.20 <= ratio <= 0.35, ratio


def test_ophidia_seed_west_and_no_yuan_ti():
    seed = _lore_seeds()["rumor_ophidia_esta_criando_um_veneno_que_mata_apenas_humanos"]
    assert "oeste" in fold(seed["gist"]) and "sul" not in fold(seed["gist"])
    assert "yuan-ti" not in fold(lore_text("rumors.txt"))
    assert "yuan-ti" not in _public_text()


def test_festivals_named_and_approved():
    fest = {f["id"]: f for f in load_json("data/world/festivals.json")["festivals"]}
    assert len(fest) == 14 and all(f["review"] == "aprovado" for f in fest.values())
    ceu = fest["fim_do_ceu_vermelho"]
    assert ceu["name"] == "Véspera do Céu Vermelho" and ceu["label"] == "em vigília"
    daily = lore_text("daily_life.txt").splitlines()
    start = next(i for i, ln in enumerate(daily) if ln.startswith("Como Valoria Conta o Tempo"))
    for f in fest.values():
        assert len(f["lore_refs"]) == 1
        name, _, line = f["lore_refs"][0].partition(":")
        assert name == "daily_life.txt" and int(line) - 1 > start, f["id"]
        assert fold(f["name"].split(" ", 1)[1]) in fold(daily[int(line) - 1]), f["id"]
    section = fold(" ".join(daily[start:]))
    for needle in ("sete meses", "dragao", "cinco dias", "so ali", "noite do silencio", "vigilia"):
        assert needle in section, needle


def test_new_rumor_seeds_enabled_with_regions():
    seeds = _lore_seeds()
    for sid, (conf, truth) in NEW_RUMOR_SEEDS.items():
        s = seeds[sid]
        assert s["regions"] and not s.get("disabled"), sid
        assert s["confiabilidade"] == conf and s["truth"] is truth, sid
        assert s["source"].startswith("lore_nova/rumors.txt:")
    assert seeds["rumor_um_morto_ainda_varre_o_crematorio"]["secret_id"] == "pacto_valerius"


def test_rumor_seeds_generator_check_is_green():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_rumor_seeds.py"), "--check"],
        capture_output=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout
