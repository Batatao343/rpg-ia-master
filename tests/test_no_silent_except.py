"""SPEC-250 R4: nenhum ``except Exception`` novo pode degradar em silencio.

Todo handler amplo que nao relanca precisa logar (log_event/log_fallback/logger/metrica) ou trazer
``# silent-ok: <motivo>``. A allowlist (tests/data/silent_except_allowlist.txt) congela os casos
ANTIGOS e so pode diminuir: ao corrigir um, remova a linha dele.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import silent_except_scan  # noqa: E402

ALLOWLIST = Path(__file__).parent / "data" / "silent_except_allowlist.txt"


def _allowed() -> set[str]:
    lines = ALLOWLIST.read_text(encoding="utf-8").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def test_no_new_silent_except():
    found = set(silent_except_scan.scan())
    new = sorted(found - _allowed())
    assert not new, (
        "except silencioso novo (logue com log_fallback/log_event ou anote "
        "'# silent-ok: <motivo>'):\n" + "\n".join(new)
    )


def test_allowlist_only_shrinks():
    found = set(silent_except_scan.scan())
    stale = sorted(_allowed() - found)
    assert not stale, "remova da allowlist (ja corrigidos):\n" + "\n".join(stale)
