"""SPEC-230 R2: todo `with_structured_output(` precisa de guard `isinstance(`
na mesma função (FallbackLLM devolve AIMessage, que e Pydantic valido e nao
estoura no model_dump)."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = (
    list((ROOT / "agents").glob("*.py"))
    + list((ROOT / "services").glob("*.py"))
    + [ROOT / "character_creator.py", ROOT / "api.py"]
)
# allowlist justificada: (arquivo, funcao) -> motivo
ALLOW: dict[tuple[str, str], str] = {
    (
        "campaign_manager.py",
        "_invoke",
    ): "helper fino; o chamador valida isinstance(plan, CampaignPlanModel)",
}


def _sites():
    for path in FILES:
        src = path.read_text(encoding="utf-8")
        if "with_structured_output(" not in src:
            continue
        tree = ast.parse(src)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            seg = ast.get_source_segment(src, fn) or ""
            own = [
                n
                for n in ast.walk(fn)
                if isinstance(n, ast.Attribute) and n.attr == "with_structured_output"
            ]
            if own:
                yield path.name, fn.name, seg


def test_all_structured_output_sites_guarded():
    bad = []
    seen = set()
    for fname, fn, seg in _sites():
        key = (fname, fn)
        if key in seen:
            continue
        seen.add(key)
        if key in ALLOW:
            continue
        if "isinstance(" not in seg:
            bad.append(f"{fname}::{fn}")
    assert not bad, f"with_structured_output sem guard isinstance: {bad}"
