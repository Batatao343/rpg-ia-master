"""SPEC-376: `data/` é a fonte de Cartas/classes; geradores com deriva destrutiva saíram.

Offline, determinístico. A parte do bestiário (A5) vive no fim do arquivo.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GERADORES_APAGADOS = ("scripts/gen_cards_v4.py", "scripts/gen_classes_v2.py")
DOCS_VIGENTES = ("docs/design/CARTAS.md", "docs/design/CLASSES.md", "docs/guias/AUTORIA.md")


def test_geradores_apagados_nao_existem():
    for rel in GERADORES_APAGADOS:
        assert not (ROOT / rel).exists(), f"{rel} foi removido pela SPEC-376"


def test_docs_nao_mandam_rodar_geradores_apagados():
    for rel in DOCS_VIGENTES:
        texto = (ROOT / rel).read_text(encoding="utf-8")
        for gerador in ("gen_cards_v4", "gen_classes_v2"):
            for linha in texto.splitlines():
                if gerador in linha:
                    assert "removido" in linha.lower() or "SPEC-376" in linha, (rel, linha)
