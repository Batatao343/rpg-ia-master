"""SPEC-416 Bloco C: catraca de `assert` que depende do relógio real em `tests/`."""

from __future__ import annotations

import textwrap
from pathlib import Path

from scripts.dev import clock_asserts as ca


def _count(tmp_path: Path, source: str) -> dict[str, int]:
    (tmp_path / "t.py").write_text(textwrap.dedent(source), encoding="utf-8")
    return ca.measure(tmp_path, ["t.py"])


def test_detecta_relogio_com_alias(tmp_path):
    # Cópia literal de tests/test_spec361_gate.py::test_prazo_real_por_thread
    found = _count(
        tmp_path,
        """
        def test_prazo_real_por_thread(monkeypatch):
            import time as _t

            monkeypatch.setenv("RPG_CREATURE_GEN_DEADLINE_S", "0.2")

            def lento():
                _t.sleep(0.6)

            t0 = _t.perf_counter()
            res = cg.gerar(_p(), lore="")
            assert res.caminho == "fallback"
            assert _t.perf_counter() - t0 < 0.55
        """,
    )
    assert found == {"t.py::test_prazo_real_por_thread": 1}


def test_from_import_e_datetime(tmp_path):
    found = _count(
        tmp_path,
        """
        import datetime as dt
        from datetime import datetime, date
        from time import perf_counter as pc

        def test_a():
            assert pc() > 0

        def test_b():
            assert datetime.now().year > 2000

        def test_c():
            assert dt.datetime.utcnow() and date.today()
        """,
    )
    assert found == {"t.py::test_a": 1, "t.py::test_b": 1, "t.py::test_c": 1}


def test_contaminacao_transitiva(tmp_path):
    found = _count(
        tmp_path,
        """
        import time

        def test_x():
            t0 = time.monotonic()
            dt_ = t0 + 1
            assert dt_ > 0
        """,
    )
    assert found == {"t.py::test_x": 1}


def test_relogio_fora_do_assert_nao_conta(tmp_path):
    found = _count(
        tmp_path,
        """
        import time

        def test_y():
            time.sleep(0)
            log = time.time()
            print(log)
            assert 1 + 1 == 2
        """,
    )
    assert found == {}


def test_metodo_qualificado(tmp_path):
    found = _count(
        tmp_path,
        """
        import time

        class TestK:
            def test_m(self):
                assert time.time() > 0
        """,
    )
    assert found == {"t.py::TestK.test_m": 1}


def test_novo_cresceu_folgado_orfao():
    msgs = ca.problems({"a::n": 1, "b::g": 3, "c::f": 1}, {"b::g": 2, "c::f": 2, "d::o": 1})
    text = "\n".join(msgs)
    assert "novo: a::n" in text
    assert "cresceu: b::g 2 -> 3" in text
    assert "folgada: c::f 2 -> 1" in text
    assert "órfã na baseline: d::o" in text
    assert ca.problems({"a": 1}, {"a": 1}) == []


def test_tighten_recusa_crescimento(tmp_path):
    path = tmp_path / "b.json"
    ca.write_baseline({"a": 1}, path)
    assert ca.run_tighten({"a": 2}, path) == 1
    assert ca.load_baseline(path) == {"a": 1}
    ca.write_baseline({"a": 3, "gone": 1}, path)
    assert ca.run_tighten({"a": 2}, path) == 0
    assert ca.load_baseline(path) == {"a": 2}


def test_repo_respeita_baseline():
    current = ca.measure(ca.ROOT, ca.tracked_tests(ca.ROOT))
    found = ca.problems(current, ca.load_baseline())
    assert not found, "\n".join(
        [
            *found,
            "Use relógio fixo (monkeypatch do time/datetime do módulo sob teste); encolheu ="
            " clock_asserts.py --tighten; exceção = --update do coordenador.",
        ]
    )
    assert "tests/test_spec361_gate.py::test_prazo_real_por_thread" in ca.load_baseline()
