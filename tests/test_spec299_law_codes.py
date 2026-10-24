"""SPEC-299 etapa 1 — dados e lint de ``data/law_codes.json``."""

import copy
import json

from services import law_codes


def _raw() -> dict:
    return json.loads(law_codes.LAW_CODES_PATH.read_text(encoding="utf-8"))


def test_lint_clean_on_real_data():
    assert law_codes.lint_law_codes() == []


def test_every_jurisdiction_location_exists():
    data = _raw()
    data["jurisdictions"]["local_que_nao_existe"] = "codigo_de_ferro"
    problems = law_codes.lint_law_codes(data)
    assert any("local_que_nao_existe" in p for p in problems)


def test_authority_is_faction():
    data = _raw()
    data["codes"]["codigo_de_ferro"]["authority_faction_id"] = "nova_arcadia"
    assert any("authority_faction_id" in p for p in law_codes.lint_law_codes(data))
    for cid in ("codigo_de_ferro", "colmeia"):
        assert law_codes.get_code(cid)["authority_faction_id"]


def test_pools_exist_in_bestiary():
    data = _raw()
    data["codes"]["codigo_de_ferro"]["guard_pool"] = ["enemy_inexistente"]
    assert any("guard_pool" in p for p in law_codes.lint_law_codes(data))


def test_prison_inside_jurisdiction():
    data = _raw()
    data["codes"]["codigo_de_ferro"]["prison_location_id"] = "skallgard"
    assert any("prison_location_id" in p for p in law_codes.lint_law_codes(data))


def test_unknown_location_is_lawless():
    for loc in ("brekmar", "na_anel_lama", "na_taverna_javali", "pantano_melancolia", ""):
        assert law_codes.code_for_location(loc) is None
    assert law_codes.code_for_location("nova_arcadia")["id"] == "codigo_de_ferro"
    assert law_codes.code_for_location("sx_cidades_hospedeiros")["id"] == "colmeia"


def test_lint_flags_bad_crime_type():
    data = copy.deepcopy(_raw())
    data["codes"]["codigo_de_ferro"]["crimes"]["bruxaria"] = {"severity": 1}
    assert any("fora do catálogo" in p for p in law_codes.lint_law_codes(data))


def test_missing_file_makes_law_inert(monkeypatch, tmp_path):
    monkeypatch.setattr(law_codes, "LAW_CODES_PATH", tmp_path / "nao_existe.json")
    law_codes.reload()
    try:
        assert not law_codes.is_active()
        assert law_codes.code_for_location("nova_arcadia") is None
        assert law_codes.lint_law_codes()  # lint acusa o arquivo ausente
    finally:
        monkeypatch.undo()
        law_codes.reload()
    assert law_codes.is_active()


def test_magia_ilegal_on_in_codigo_de_ferro_only():
    code = law_codes.get_code("codigo_de_ferro")
    assert law_codes.crime_row(code, "magia_ilegal") is not None
    assert law_codes.crime_row(law_codes.get_code("lei_dos_clas"), "magia_ilegal") is None


def test_validate_content_integrates_law_lint():
    from services.content_validator import validate_law_codes

    assert validate_law_codes() == []
