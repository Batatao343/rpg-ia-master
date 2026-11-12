"""SPEC-416 Bloco E (B2): baseline do ruff por contagem arquivo x regra; só encolhe."""

from __future__ import annotations

from scripts.dev import ruff_baseline as rb


def _toml(counts):
    return {(f, c) for f, codes in counts.items() for c in codes}


def test_contagem_nova_no_arquivo_baselinado_falha():
    # O per-file-ignores aceitaria: o arquivo já está baselinado para BLE001.
    recorded = {"a.py": {"BLE001": 2}}
    found = rb.problems({"a.py": {"BLE001": 3}}, recorded, _toml(recorded))
    assert found == ["cresceu a.py×BLE001 2 → 3"]


def test_par_novo_falha():
    recorded = {"a.py": {"BLE001": 1}}
    found = rb.problems(
        {"a.py": {"BLE001": 1, "SIM102": 1}, "b.py": {"C901": 2}}, recorded, _toml(recorded)
    )
    assert "par novo a.py×SIM102 (1)" in found and "par novo b.py×C901 (2)" in found


def test_folgado_e_orfao_pedem_tighten():
    recorded = {"a.py": {"BLE001": 3, "C901": 1}}
    found = rb.problems({"a.py": {"BLE001": 2}}, recorded, _toml(recorded))
    assert "folgada a.py×BLE001 3 → 2; rode --tighten" in found
    assert "órfão a.py×C901; rode --tighten" in found


def test_toml_divergente_falha():
    recorded = {"a.py": {"BLE001": 1}}
    assert rb.problems(recorded, recorded, _toml(recorded)) == []
    assert "toml ≠ contagens; rode --tighten" in rb.problems(recorded, recorded, set())


def test_tighten_so_desce_e_zera_pares():
    recorded = {"a.py": {"BLE001": 3, "C901": 1}, "b.py": {"SIM102": 2}}
    measured = {"a.py": {"BLE001": 2}, "b.py": {"SIM102": 2}}
    assert rb.tightened(measured, recorded) == {"a.py": {"BLE001": 2}, "b.py": {"SIM102": 2}}


def test_tighten_recusa_crescimento(tmp_path, monkeypatch):
    monkeypatch.setattr(rb, "COUNTS", tmp_path / "c.json")
    monkeypatch.setattr(rb, "BASELINE", tmp_path / "b.toml")
    assert rb.run_tighten({"a.py": {"BLE001": 3}}, {"a.py": {"BLE001": 2}}) == 1
    assert not (tmp_path / "c.json").exists()
    assert rb.run_tighten({"a.py": {"BLE001": 1}}, {"a.py": {"BLE001": 2}}) == 0
    assert rb.load_counts(tmp_path / "c.json") == {"a.py": {"BLE001": 1}}
    assert rb.toml_pairs(tmp_path / "b.toml") == {("a.py", "BLE001")}


def test_repo_respeita_contagens():
    found = rb.problems(rb.violation_counts(), rb.load_counts(), rb.toml_pairs())
    assert not found, "\n".join(
        [*found, "Conserte o código; encolheu = ruff_baseline.py --tighten (coordenador sobe)."]
    )
