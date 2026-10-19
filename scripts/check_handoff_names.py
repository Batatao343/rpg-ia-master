"""Lint de nome de handoff (workspace P5): `handoffs/SPEC-NNN[-<papel>]-<tipo>.md`.

papel ∈ {sol, astra, terra, luna} (minúsculo; omitido quando o revisor é o coordenador)
tipo  ∈ {review, independent-review, eval-authoring, port-review}
Template: docs/templates/handoff-review.md. Nomes anteriores a 2026-10-19 ficam em
LEGACY (congelado: só encolhe — renomear um histórico = tirar daqui).

    python scripts/check_handoff_names.py   # exit 1 se houver nome novo fora do padrão
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(
    r"^SPEC-\d{3}(?:-(?:sol|astra|terra|luna))?-(?:review|independent-review|eval-authoring|port-review)\.md$"
)
LEGACY = frozenset(
    {
        "LOGS-P1-SOL-review.md",
        "LOGS-P2P3-review.md",
        "PONYTAIL-specs-review-2026-10-18.md",
        "SPEC-175-SOL-review-v4.md",
        "SPEC-175-SOL-review-v6.md",
        "SPEC-175-SOL-review.md",
        "SPEC-176-SOL-independent-review.md",
        "SPEC-176-SOL-review.md",
        "SPEC-177-SOL-independent-review.md",
        "SPEC-177-SOL-typesafe-correction-review.md",
        "SPEC-178-SOL-independent-review.md",
        "SPEC-178-SOL-live-blocker-review.md",
        "SPEC-178-SOL-result-review.md",
        "SPEC-179-SOL-offline-review.md",
        "SPEC-179-SOL-recovery-review.md",
        "SPEC-179-SOL-result-review.md",
        "SPEC-180-SOL-independent-review.md",
        "SPEC-181-SOL-independent-review.md",
        "SPEC-182-SOL-independent-review.md",
        "SPEC-183-SOL-independent-review.md",
        "SPEC-183-Terra-review.md",
        "SPEC-184-ASTRA-independent-review.md",
        "SPEC-185-SOL-independent-review.md",
        "SPEC-185-Terra-review.md",
        "SPEC-186-SOL-independent-review.md",
        "SPEC-187-Terra-review.md",
        "SPEC-188-SOL-independent-review.md",
        "SPEC-188-SOL-review.md",
        "SPEC-189-SOL-independent-review.md",
        "SPEC-189-SOL-review.md",
        "SPEC-190-SOL-independent-review.md",
        "SPEC-191-SOL-preflight-review.md",
        "SPEC-191-Terra-review.md",
        "SPEC-203-ASTRA-independent-review.md",
        "SPEC-204-SOL-independent-review.md",
        "SPEC-205-SOL-independent-review.md",
        "SPEC-207-ASTRA-independent-review.md",
        "SPEC-207-legal-consent-handoff.md",
        "SPEC-208-SOL-independent-review.md",
        "SPEC-209-SOL-independent-review.md",
        "SPEC-210-SOL-independent-review.md",
        "SPEC-211-SOL-independent-review.md",
        "SPEC-212-SOL-independent-review.md",
        "SPEC-212-etapa0-followup.md",
        "SPEC-212-etapa0.md",
        "SPEC-212-review-eval-followup.md",
        "SPEC-213-ASTRA-independent-review.md",
        "SPEC-215-ASTRA-independent-review.md",
        "SPEC-216-eval-authoring-result.md",
        "SPEC-216-eval-followup.md",
        "SPEC-217-ASTRA-J1-review.md",
        "SPEC-217-ASTRA-J2-review.md",
        "SPEC-217-ASTRA-port-review.md",
        "SPEC-217-J1-for-Astra.md",
        "SPEC-218-ASTRA-independent-review.md",
        "SPEC-219-SOL-independent-review.md",
        "SPEC-220-SOL-independent-review.md",
        "SPEC-222-SOL-independent-review.md",
        "SPEC-222-legal-text.md",
        "SPEC-224-ASTRA-independent-review.md",
        "SPEC-236-SOL-independent-review.md",
        "SPEC-237-SOL-independent-review.md",
        "SPEC-238-ASTRA-review.md",
        "SPEC-238-for-Astra.md",
        "SPEC-239-245-SOL-review.md",
        "SPEC-265-SOL-review.md",
        "SPEC-275-ASTRA-review.md",
    }
)


def violations(handoffs_dir: Path = ROOT / "handoffs") -> list[str]:
    names = sorted(path.name for path in handoffs_dir.iterdir() if path.is_file())
    return [name for name in names if not PATTERN.match(name) and name not in LEGACY]


def stale_legacy(handoffs_dir: Path = ROOT / "handoffs") -> list[str]:
    present = {path.name for path in handoffs_dir.iterdir()}
    return sorted(LEGACY - present)


def main() -> int:
    bad = violations()
    for name in bad:
        print(f"handoff fora do padrão SPEC-NNN[-papel]-tipo.md: handoffs/{name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
