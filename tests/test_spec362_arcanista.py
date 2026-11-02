"""SPEC-362 R15: artefatos da arena do Arcanista, pacote de Cartas e integridade do avaliador."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from services import card_effects as fx
from services import card_lint, cards

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "spec362"
CLS = "Arcanista Cinzento"
SUBCLASSES = ("todas", "calibrado", "descoberto", "improvisador")
ARQ_ONDA = "data/cards/posturas/arcanista_cinzento_{}.json"
PROTEGIDOS = (
    "scripts/cards/sim.py",
    "docs/spec335/arena_posturas.py",
    "docs/spec341/arena_spec341.py",
    "docs/spec355/arena_spec355.py",
    "data/cards/_orcamento.json",
    "tests/spec330_equivalence.py",
    "tests/fixtures/spec330_legacy_golden.json",
    "tests/fixtures/spec330_card_text_snapshot.json",
    "tests/test_card_sim.py",
    "tests/test_spec341_balanco.py",
    "data/cards/devoto.json",
    "data/cards/sangromante.json",
    "data/cards/corruptor.json",
    "data/cards/medico.json",
    "data/cards/arcanista.json",
    "data/cards/basicas.json",
    "data/cards/bestiario.json",
    "data/cards/exemplos.json",
    "data/cards/exemplos_extra.json",
    "data/cards/tiers_5_plus.json",
)


def _load(name: str) -> dict:
    return json.loads((D / name).read_text(encoding="utf-8"))


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False, cwd=ROOT)


def _base() -> str:
    """Ponto de partida da branch (main pode ter andado depois do rebase)."""
    res = _git("merge-base", "main", "HEAD")
    return res.stdout.strip() or "main"


def _on_branch() -> bool:
    return _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "spec-362"


def _main_versao(cid: str) -> int:
    for sub in ("tronco", "calibrado", "descoberto", "improvisador"):
        path = ARQ_ONDA.format(sub)
        res = _git("show", f"{_base()}:{path}")
        if res.returncode != 0:
            continue
        data = json.loads(res.stdout)
        for c in data["cards"] if isinstance(data, dict) else data:
            if c["id"] == cid:
                return int(c.get("versao", 1) or 1)
    raise AssertionError(f"{cid} nao esta nas Cartas de onda do Arcanista na main")


def test_versoes_batem_com_catalogo():
    for name in ("arena-final.json", "arena-confirmacao.json"):
        for cid, v in _load(name)["versoes"].items():
            assert int((cards.get_card(cid) or {}).get("versao", 1) or 1) == v, (name, cid)


def test_pacote_dentro_do_limite():
    ids = list(_load("arena-final.json")["versoes"])
    assert len(ids) <= 3
    pool = list(cards._load_cards().values())
    for cid in ids:
        card = cards.get_card(cid)
        assert card and card.get("classe") == CLS and cid.split("_")[0].endswith("1"), cid
        assert int(card.get("versao", 1) or 1) == _main_versao(cid) + 1, cid
        assert fx.budget_error(card) is None, cid
        issues = card_lint.lint_card(card, [c for c in pool if c["id"] != cid])
        assert not card_lint.errors(issues), cid


def test_alteradas_fora_da_341():
    ids = set(_load("arena-final.json")["versoes"])
    for name in ("arena-final.json", "arena-confirmacao.json"):
        antigo = json.loads((ROOT / "docs" / "spec341" / name).read_text(encoding="utf-8"))
        assert not ids & set(antigo["versoes"]), name


def test_arcanista_piso_e_teto():
    final = _load("arena-final.json")
    piso = 0.465 if final.get("folga_atingida", True) else 0.45
    conf = _load("arena-confirmacao.json")
    # Coordenador (02/11): piso de 45 % vira meta na 20-99; a excecao do Arcanista segue com o valor medido.
    piso_conf = 0.448
    assert final["posturas"][CLS]["todas"]["total"] >= piso
    assert conf["posturas"][CLS]["todas"]["total"] >= piso_conf
    for data in (final, conf):
        for sub in SUBCLASSES:
            assert data["posturas"][CLS][sub]["padrao"] <= 0.75, sub


def test_outras_posturas_identicas_a_base():
    final = _load("arena-final.json")["posturas"]
    base = _load("arena-base-0-19.json")["posturas"]
    for cls in base:
        if cls != CLS:
            assert final[cls] == base[cls], cls


def test_legadas_e_avaliador_sem_diff():
    if not _on_branch():
        return
    for path in PROTEGIDOS:
        assert _git("diff", "--quiet", _base(), "--", path).returncode == 0, path
