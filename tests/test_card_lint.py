"""SPEC-336 R3: lint determinístico das Cartas (fonte única com o content_validator)."""

import copy
import json
import os

import pytest

from services import card_effects as fx
from services import card_lint

BASE = {
    "id": "med_teste_trama",
    "name": "Trama de Cinza",
    "tipo": "ativa",
    "origem": "onda-1",
    "classe": "Médico de Campo",
    "subclasse": "boticario",
    "patamar": "inicial",
    "raridade": "comum",
    "custo_entropia": 1,
    "frequencia": "livre",
    "virtude_permitida": ["mente"],
    "efeitos": [{"kind": "cura", "valor": 3}],
    "descricao": "Cinza de fornalha fecha a ferida sob o céu sujo de Valoria.",
    "momento": "Melhor jogada quando um aliado sangra e o inimigo tem a iniciativa.",
    "tier": 1,
    "level_req": 1,
    "apex": False,
    "onda": 1,
    "versao": 1,
}


def card(**over):
    c = copy.deepcopy(BASE)
    c.update(over)
    return c


def codes(issues, level="error"):
    return {i.code for i in issues if i.level == level}


def test_clean_card_is_green():
    assert card_lint.errors(card_lint.lint_card(card(), [])) == []


def test_template_is_valid():
    with open(os.path.join("docs", "templates", "carta.json"), encoding="utf-8") as f:
        batch = [fx.materialize(c) for c in json.load(f)["cards"]]
    res = card_lint.lint_batch(batch, [])
    assert all(not card_lint.errors(v) for v in res.values()), res


def test_missing_momento_is_error_unless_legacy():
    c = card()
    del c["momento"]
    assert "momento" in codes(card_lint.lint_card(c, []))
    assert "momento" not in codes(card_lint.lint_card(c, [], exigir_momento=False))


def test_duplicate_detected_by_signature_and_momento():
    other = card(id="med_outra", name="Outra Trama")
    dup = card(
        id="med_copia",
        name="Cópia Fiel",
        momento="Melhor jogada quando aliado sangra e inimigo tem iniciativa.",
    )
    issues = card_lint.lint_card(dup, [other])
    assert "redundancia" in codes(issues)
    assert any("med_outra" in i.message for i in issues)


def test_same_signature_distinct_momento_only_warns():
    other = card(id="med_outra", name="Outra Trama")
    distinct = card(
        id="med_distinta",
        name="Fio de Sombra",
        momento="Melhor jogada logo após o Pacto, com o Fôlego quase vazio e a mão cheia de Fardos.",
    )
    issues = card_lint.lint_card(distinct, [other])
    assert "redundancia" not in codes(issues)
    assert "redundancia" in codes(issues, "warn")


def test_color_pie_violation_is_error():
    c = card(classe="Corruptor", efeitos=[{"kind": "cura", "valor": 3}])
    assert "color_pie" in codes(card_lint.lint_card(c, []))
    medico = card(efeitos=[{"kind": "rachadura", "valor": 2}])
    assert "color_pie" in codes(card_lint.lint_card(medico, []))
    arc = card(classe="Arcanista Cinzento", palavras_chave={"sacrificio": 1})
    assert "color_pie" in codes(card_lint.lint_card(arc, []))


def test_color_pie_target_and_limit_rules():
    c = card(classe="Sangromante", efeitos=[{"kind": "cura", "valor": 2, "alvo": "aliados"}])
    assert "color_pie" in codes(card_lint.lint_card(c, []))
    big = card(classe="Sangromante", efeitos=[{"kind": "vigilia", "valor": 6}])
    assert "color_pie" in codes(card_lint.lint_card(big, []))


def test_number_in_description_is_error():
    c = card(descricao="Cura 3 de vida com cinza.")
    assert "voz" in codes(card_lint.lint_card(c, []))


def test_voice_rules_name_length_size_and_lexicon():
    assert "voz" in codes(card_lint.lint_card(card(name="Trama De Cinza Do Velho Médico"), []))
    assert "voz" in codes(card_lint.lint_card(card(descricao="x" * 141), []))
    assert "voz" in codes(card_lint.lint_card(card(descricao="Um buff de cinza no braço."), []))
    assert "voz" in codes(card_lint.lint_card(card(momento="Quando o boss aparece."), []))


def test_repeated_name_is_error():
    other = card(
        id="med_outra", momento="Quando o Pacto cobra a Carga e a mão está vazia de golpes."
    )
    c = card(
        id="med_nova",
        name="trama de cinza",
        momento="Quando o torpor acaba e o inimigo recua da zona.",
    )
    assert "nome" in codes(card_lint.lint_card(c, [other]))


def test_out_of_budget_is_error():
    c = card(efeitos=[{"kind": "cura", "valor": 30}])
    assert "orcamento" in codes(card_lint.lint_card(c, []))


def test_vocabulary_outside_glossary_is_error():
    c = card(efeitos=[{"kind": "cura_milagrosa", "valor": 3}])
    assert "vocabulario" in codes(card_lint.lint_card(c, []))
    kw = card(palavras_chave={"furia": True})
    assert "vocabulario" in codes(card_lint.lint_card(kw, []))


def test_version_bump_replaces_instead_of_colliding():
    v1 = card()
    assert "nome" in codes(card_lint.lint_card(card(), [v1]))
    assert "nome" not in codes(card_lint.lint_card(card(versao=2), [v1]))


def test_batch_catches_duplicates_inside_the_batch():
    a = card(id="med_a", name="Fio Um")
    b = card(id="med_b", name="Fio Dois")
    res = card_lint.lint_batch([a, b], [])
    assert not card_lint.errors(res["med_a"])
    assert "redundancia" in codes(res["med_b"])


def test_wave_rule_max_two_new_keywords(monkeypatch):
    fake = {"k1": {"onda": 7}, "k2": {"onda": 7}, "k3": {"onda": 7}}
    monkeypatch.setattr(fx, "glossary", lambda: fake)
    monkeypatch.setattr(fx, "card_keyword_ids", lambda c: ["k1"])
    issues = card_lint.lint_wave([card(id=f"c{i}", onda=7) for i in range(6)])
    assert any("3 palavras-chave novas" in i.message for i in issues)


def test_wave_rule_needs_six_cards(monkeypatch):
    monkeypatch.setattr(fx, "glossary", lambda: {"k1": {"onda": 7}})
    monkeypatch.setattr(fx, "card_keyword_ids", lambda c: ["k1"])
    assert card_lint.lint_wave([card(id=f"c{i}", onda=7) for i in range(5)])
    assert not card_lint.lint_wave([card(id=f"c{i}", onda=7) for i in range(6)])


def test_similarity_with_embedding_backend():
    v = {"a": [1.0, 0.0], "b": [1.0, 0.1], "c": [0.0, 1.0]}
    assert card_lint.similarity("a", "b", embed=v.get) > 0.99
    assert card_lint.similarity("a", "c", embed=v.get) == 0.0


def test_content_validator_runs_card_lint_for_wave_cards(tmp_path):
    from services.content_validator import validate_cards

    cdir = tmp_path / "cards"
    (cdir / "posturas").mkdir(parents=True)
    (cdir / "_rascunhos").mkdir()
    good = card(id="med_ok")
    bad = card(id="med_ruim", name="Outra Trama", descricao="Cura 3 pontos de vida.")
    (cdir / "posturas" / "medico.json").write_text(
        json.dumps({"cards": [good, bad]}), encoding="utf-8"
    )
    # rascunho nunca é validado nem entra no pool
    (cdir / "_rascunhos" / "x.json").write_text(
        json.dumps({"cards": [card(id="med_rasc", descricao="9")]}), encoding="utf-8"
    )
    msgs = [(f.entity_id, f.message) for f in validate_cards(str(cdir)) if f.severity == "error"]
    assert any(eid == "med_ruim" and "voz" in m for eid, m in msgs)
    assert not any(eid in ("med_ok", "med_rasc") for eid, _ in msgs)


def test_loader_ignores_drafts_and_reads_highest_version(tmp_path, monkeypatch):
    from services import cards

    monkeypatch.setattr(cards.gamedata, "DATA_DIR", str(tmp_path))
    cdir = tmp_path / "cards"
    (cdir / "_rascunhos").mkdir(parents=True)
    (cdir / "posturas").mkdir()
    v1 = card(id="med_v", descricao="Antiga.")
    v2 = card(id="med_v", descricao="Nova.", versao=2)
    (cdir / "posturas" / "a.json").write_text(json.dumps({"cards": [v2, v1]}), encoding="utf-8")
    (cdir / "_rascunhos" / "r.json").write_text(
        json.dumps({"cards": [card(id="med_r")]}), encoding="utf-8"
    )
    cards.reload_cards()
    try:
        assert cards.get_card("med_v")["descricao"] == "Nova."
        assert cards.get_card("med_r") is None
    finally:
        cards.reload_cards()


@pytest.mark.parametrize(
    "fn", ["lint.py", "sim.py", "draft.py", "promote.py", "metrics.py", "painel.py"]
)
def test_cli_scripts_exist(fn):
    assert os.path.isfile(os.path.join("scripts", "cards", fn))


# --- Revisão Sol (P1-1, P1-2, P2-1..3) ---------------------------------------
def test_batch_refuses_existing_id_unless_versao_strictly_higher():
    pool = [card(id="med_x", name="Nome X")]
    same = card(id="med_x", name="Nome X")
    assert "nome" in codes(card_lint.lint_batch([same], pool)["med_x"])
    assert not card_lint.errors(
        card_lint.lint_batch([card(id="med_x", name="Nome X", versao=2)], pool)["med_x"]
    )


def test_batch_refuses_legacy_id_without_versao():
    legacy = {k: v for k, v in card(id="med_leg", name="Legada").items() if k != "versao"}
    new = card(id="med_leg", name="Legada")
    assert "nome" in codes(card_lint.lint_batch([new], [legacy])["med_leg"])


def test_promote_refuses_existing_id(tmp_path):
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "cards_promote_sol", os.path.join("scripts", "cards", "promote.py")
    )
    promote = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = promote
    spec.loader.exec_module(promote)
    cdir = tmp_path / "cards"
    (cdir / "posturas").mkdir(parents=True)
    (cdir / "posturas" / "a.json").write_text(
        json.dumps({"cards": [card(id="med_x", name="Nome X")]}), encoding="utf-8"
    )
    lote = tmp_path / "l.json"
    lote.write_text(
        json.dumps(
            {
                "cards": [
                    card(
                        id="med_x",
                        name="Nome X",
                        momento="Outro momento bem distinto de pacto e fardo.",
                    )
                ]
            }
        ),
        encoding="utf-8",
    )
    res = promote.promote(
        str(lote),
        {"med_x": {"bandeiras": []}},
        onda=2,
        autor="t",
        revisor_voz="dono",
        cards_dir=str(cdir),
    )
    assert "med_x" in res["recusadas"] and not res["promovidas"]


def _write(cdir, name, cards_):
    (cdir / "posturas").mkdir(parents=True, exist_ok=True)
    (cdir / "posturas" / name).write_text(json.dumps({"cards": cards_}), encoding="utf-8")


def _errors(cdir):
    from services.content_validator import validate_cards

    return [f.message for f in validate_cards(str(cdir)) if f.severity == "error"]


def test_validator_requires_unique_and_increasing_id_versao_across_files(tmp_path):
    cdir = tmp_path / "cards"
    legacy = {
        "id": "dup_id",
        "name": "Velha",
        "tipo": "ativa",
        "classe": "Médico de Campo",
        "patamar": "inicial",
        "frequencia": "livre",
        "efeito": {"kind": "cura", "valor": 3},
        "descricao": "x",
        "tier": 1,
        "level_req": 1,
    }
    _write(cdir, "a.json", [legacy])
    _write(cdir, "b.json", [card(id="dup_id", name="Nova", versao=1)])
    assert any("(dup_id, 1) duplicado" in m for m in _errors(cdir))
    _write(cdir, "b.json", [card(id="dup_id", name="Nova", versao=2)])
    assert not any("dup_id" in m and "versao" in m for m in _errors(cdir))
    _write(cdir, "a.json", [{**legacy, "versao": 3}])
    assert any("não é maior" in m for m in _errors(cdir))


def test_non_numeric_versao_does_not_break_catalog(tmp_path, monkeypatch):
    from services import cards
    from services.content_validator import validate_cards

    monkeypatch.setattr(cards.gamedata, "DATA_DIR", str(tmp_path))
    cdir = tmp_path / "cards"
    _write(
        cdir, "a.json", [card(id="med_v", versao="dois"), card(id="med_w", name="W", versao=None)]
    )
    cards.reload_cards()
    try:
        assert cards.get_card("med_v") is not None
    finally:
        cards.reload_cards()
    assert any(
        f.severity == "warning" and "versao inválida" in f.message
        for f in validate_cards(str(cdir))
    )


def test_loader_traversal_matches_lint_and_keeps_legacy_cards():
    from services import cards

    ids = {c["id"] for c in card_lint.load_pool()}
    assert set(cards.all_cards()) == ids
    pool = card_lint.load_pool()
    # ondas (SPEC-335+) e baralhos de família (`inf_`, SPEC-332) crescem; o legado fica fixo
    legado = {c["id"] for c in pool if c.get("onda") is None and not c["id"].startswith("inf_")}
    assert len(legado) == 332  # 323 + 9 da SPEC-333
    assert {c["id"] for c in pool if c.get("onda") is not None} <= ids


def test_auto_resolved_choices_marked_source_auto(monkeypatch):
    import progression
    from services import card_telemetry

    seen = []
    monkeypatch.setattr(card_telemetry, "log_event", lambda a, e, **kw: seen.append((e, kw)))
    p = {
        "class_name": "Médico de Campo",
        "level": 2,
        "known_cards": [],
        "pending_choices": [{"id": "lvl2-carta", "level": 2, "kind": "carta"}],
    }
    progression.auto_resolve_choices(p)
    picks = [kw for e, kw in seen if e in ("card_picked", "card_offered")]
    assert picks and all(kw["source"] == "auto" for kw in picks)
    seen.clear()
    card_telemetry.picked("x")
    assert seen[0][1]["source"] == "player"


def test_check_raridade_regras_da_r3():
    base = dict(card(onda=1), raridade="comum", patamar="inicial")
    assert not card_lint.check_raridade(base)
    dois = dict(base, efeitos=[{"kind": "cura", "valor": 3}, {"kind": "comprar", "valor": 1}])
    assert "raridade" in codes(card_lint.check_raridade(dois))
    kws = dict(base, palavras_chave={"guardar": True, "eco": True})
    assert "raridade" in codes(card_lint.check_raridade(kws))
    assert not card_lint.check_raridade(dict(dois, raridade="incomum", patamar="avancado"))
    tres = dict(dois, efeitos=dois["efeitos"] + [{"kind": "protecao", "valor": 1}])
    assert card_lint.errors(
        card_lint.check_raridade(dict(tres, raridade="incomum", patamar="avancado"))
    )
    assert card_lint.errors(card_lint.check_raridade(dict(base, patamar="avancado")))
    abissal = dict(base, raridade="abissal", patamar="lendario", custo_entropia=0)
    assert card_lint.errors(card_lint.check_raridade(abissal))
    ok = dict(abissal, custo_entropia=4, palavras_chave={"exaurir": True})
    assert not card_lint.check_raridade(ok)
    assert not card_lint.check_raridade(dict(dois, onda=None))  # legado: sem a regra


def test_escala_no_efeito_principal_de_dano_e_recusada():
    """SPEC-335 P1-1: o golpe com rolagem não aplica `escala`; só os efeitos extras escalam."""
    escala = {"por": "entropia", "fator": 0.5, "max": 3}
    inerte = card(efeitos=[{"kind": "dano", "categoria_arma": "leve", "dano_base": 2, "escala": escala}])
    assert any(i.code == "escala_inerte" for i in card_lint.check_escala_principal(inerte))
    extra = card(
        efeitos=[
            {"kind": "dano", "categoria_arma": "leve", "dano_base": 2},
            {"kind": "dano", "valor": 1, "escala": escala},
        ]
    )
    assert not card_lint.check_escala_principal(extra)


def test_pool_inteiro_sem_escala_inerte():
    from services import card_effects as fx

    for c in card_lint.load_pool():
        assert not card_lint.check_escala_principal(fx.materialize(c)), c["id"]
