"""
validate_content.py — CLI do lint de conteúdo (Fase 7.1).

Roda todos os validadores de `services/content_validator.py` sobre os dados
reais do repo e imprime os achados agrupados por validador.

Uso:  uv run python scripts/validate_content.py
Exit: 1 se houver qualquer ERRO; 0 caso contrário (AVISOs não falham).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.content_validator import CODEX_DIR, GRAPH_DIR, validate_all

_ORDEM = ("frontmatter", "ids", "references", "aliases", "visibility", "overrides", "encoding")


def main(codex_dir: str = CODEX_DIR, graph_dir: str = GRAPH_DIR) -> int:
    # Overrides ficam AO LADO do codex (`<pai>/codex_overrides.yaml`) — assim
    # validar um codex arbitrário (ex.: fixture de teste) não pega o overrides
    # real do repo (id de override viraria "órfão" falso).
    overrides_path = os.path.join(os.path.dirname(os.path.abspath(codex_dir)),
                                  "codex_overrides.yaml")
    findings = validate_all(codex_dir, graph_dir, overrides_path=overrides_path)
    por_validador: dict[str, list] = {}
    for f in findings:
        por_validador.setdefault(f.validator, []).append(f)

    validadores = list(_ORDEM) + sorted(set(por_validador) - set(_ORDEM))

    print("--- LINT DE CONTEÚDO ---")
    n_erros = n_avisos = 0
    for validador in validadores:
        grupo = por_validador.get(validador, [])
        if not grupo:
            print(f"[{validador}] OK (0 erros)")
            continue
        for f in grupo:
            rotulo = "ERRO" if f.severity == "error" else "AVISO"
            alvo = f" ({f.entity_id})" if f.entity_id else ""
            print(f"[{validador}] {rotulo} {f.path}{alvo}: {f.message}")
            if f.severity == "error":
                n_erros += 1
            else:
                n_avisos += 1
    print(f"--- {n_erros} ERRO(S) · {n_avisos} AVISO(S) ---")
    return 1 if n_erros else 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sys.exit(main())
