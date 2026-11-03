"""SPEC-374 R16: doc ``npc_secret`` de entidade curada precisa de ``curated: true``.

Módulo próprio para ``content_validator.py`` não crescer (``tests/test_size_budget.py``)."""

from __future__ import annotations

from services.content_validator import (
    CODEX_DIR,
    GRAPH_DIR,
    Finding,
    _parse_codex,
    _read_graph_json,
)


def validate_curated_secrets(
    codex_dir: str = CODEX_DIR, graph_dir: str = GRAPH_DIR
) -> list[Finding]:
    """SPEC-374 R16 - doc ``npc_secret`` de entidade CURADA (só em ``entities_extra.json``)
    precisa de ``curated: true``: o migrate apaga todo ``.md`` sem a marca, e o doc de segredo
    escrito à mão não sai de ``lore_nova/``. ERRO."""
    base = _read_graph_json(graph_dir, "entities.json", {})
    extra = _read_graph_json(graph_dir, "entities_extra.json", {})
    findings: list[Finding] = []
    for path, frontmatter, _body in _parse_codex(codex_dir):
        if frontmatter.get("type") != "npc_secret" or frontmatter.get("curated"):
            continue
        alvos = [
            str(r)
            for r in frontmatter.get("related_entities") or []
            if str(r) in extra and str(r) not in base
        ]
        if alvos:
            findings.append(
                Finding(
                    "curated_secrets",
                    "error",
                    path,
                    str(frontmatter.get("id", "")),
                    f"doc de segredo de entidade curada ({alvos[0]}, em entities_extra.json) "
                    "sem `curated: true`: o próximo migrate o apaga",
                )
            )
    return findings
