"""SPEC-349 Etapas 3-4: onda 1 (Nova Arcádia) — fichas, tabuleiro, Codex, arte e appearance."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from services import bestiary_lint as bl
from services.content_validator import parse_codex_file

ROOT = Path(__file__).resolve().parent.parent
REGIAO = "nova_arcadia"
FICHA = ROOT / "data" / "bestiario" / "fichas" / f"{REGIAO}.yaml"
DOC = yaml.safe_load(FICHA.read_text(encoding="utf-8"))
FICHAS = {f["id"]: f for f in DOC["criaturas"]}
NOVAS = {k: f for k, f in FICHAS.items() if bl.is_nova(f)}
BEST = json.loads((ROOT / "data" / "bestiary.json").read_text(encoding="utf-8"))
ENTS = json.loads((ROOT / "data" / "graph" / "entities_extra.json").read_text(encoding="utf-8"))
CUR = yaml.safe_load(
    (ROOT / "data" / "bestiario" / "curadoria_legado.yaml").read_text(encoding="utf-8")
)
ARTE = (ROOT / "docs" / "arte" / "bestiario-349" / f"{REGIAO}.md").read_text(encoding="utf-8")
RETRO_ENUMS = ("plano_corporal", "material", "escala", "locomocao", "percepcao")


def _one_line(text: str) -> str:
    return " ".join(str(text or "").split())


# ----------------------------------------------------------------- Etapa 3
def test_fichas_retro_completas():
    """R6: toda criatura legada (`classe: valoria`) da região tem ficha retro só com eixos."""
    legado = {
        cid
        for cid, v in BEST.items()
        if REGIAO in (v.get("regions") or []) and cid in CUR and CUR[cid]["classe"] == "valoria"
    }
    retro = {k for k, f in FICHAS.items() if f.get("status") == "retro"}
    assert legado == retro, legado ^ retro
    for k in retro:
        f = FICHAS[k]
        assert f["familia"] == "legado"
        for eixo in RETRO_ENUMS:
            assert f["anatomia"][eixo] in bl.ENUMS[eixo], (k, eixo)
        assert f["papel_tatico"] in bl.ENUMS["papel_tatico"], k
        assert f["anatomia"]["texto"] and f["categoria"] and f["arquetipo"]


def test_vagas_passam_u2_u3_u12():
    """R8: o tabuleiro passa antes da prosa, e cada ficha nova ocupa uma vaga com os mesmos eixos."""
    vagas = bl.load_vagas(REGIAO)
    assert not bl.lint_vagas(vagas, bl.COTAS_ONDA[REGIAO])
    por_vaga = {v["vaga"]: v for v in vagas}
    for k, f in NOVAS.items():
        v = por_vaga[f["vaga"]]
        for eixo in RETRO_ENUMS:
            assert f["anatomia"][eixo] == v[eixo], (k, eixo)
        for campo in ("familia", "categoria", "papel_tatico", "arquetipo"):
            assert f[campo] == v[campo], (k, campo)
        assert set(f["habitat"]) == set(v["habitat"]), k


def test_slots_genericos_da_regiao_cobertos():
    """R24: os 6 genéricos de Nova Arcádia têm ficha reinventada/adotada no MESMO id."""
    slots = {
        cid for cid, e in CUR.items() if e["regiao_onda"] == REGIAO and e["classe"] == "generico"
    }
    assert len(slots) == 6
    for cid in slots:
        f = FICHAS[cid]
        esperado = "adotada" if CUR[cid]["destino"].startswith("adotar:") else "reinventada"
        assert f["status"] == esperado, cid
        assert f["substitui"] == cid and f.get("substitui_generico")
        if esperado == "adotada":
            assert f["codex_id"] == CUR[cid]["destino"].split(":", 1)[1]
            assert (ROOT / "data" / "codex" / "monsters" / f"{f['codex_id']}.md").is_file()


def test_lint_regiao_sem_erro_fora_u11():
    """Gate U1-U13 verde (U11 é coberto por test_revisao_independente)."""
    issues = []
    for f in FICHAS.values():
        issues += bl.lint_ficha(f, exigir_revisao=False)
    docs = []
    for p in (ROOT / "data" / "codex" / "monsters").glob("*.md"):
        fm, body = parse_codex_file(str(p))
        docs.append(
            {"id": fm.get("id"), "name": fm.get("name"), "tags": fm.get("tags") or [], "body": body}
        )
    issues += bl.lint_regiao(REGIAO, list(FICHAS.values()), bestiary=BEST, codex_docs=docs)
    assert not [i for i in issues if i.level == "error"], [
        str(i) for i in issues if i.level == "error"
    ]


def test_revisao_independente():
    """R10/U11: ficha nova aprovada por revisor válido e diferente do autor."""
    for k, f in NOVAS.items():
        assert not [i for i in bl.lint_ficha(f) if i.code == "U11"], k
    assert (ROOT / "handoffs" / "SPEC-349-independent-review.md").is_file()


def test_etapa5_campos_para_o_motor():
    """A ficha deixa padrão/cadência/telegrafo e carta-assinatura para a Etapa 5 consumir (R15)."""
    slots_ok = set(bl.ENUMS["papel_tatico"]) | {
        "ataque",
        "ataque_multiplo",
        "defesa",
        "reforco_proprio",
        "enfraquecer",
        "mover",
    }
    for k, f in NOVAS.items():
        assert 2 <= len(f["padrao"]) <= 4 and set(f["padrao"]) <= slots_ok, k
        assert 2 <= f["a_cada_n"] <= 4, k
        assert "{nome}" in f["telegrafo"] and len(f["telegrafo"]) <= 120, k
        assert f["mecanica_assinatura"]["carta"].startswith("cri_"), k


# ----------------------------------------------------------------- Etapa 4
@pytest.mark.parametrize("cid", sorted(NOVAS))
def test_ficha_codex_arte_consistentes(cid):
    f = NOVAS[cid]
    bloco = re.search(rf"^### {re.escape(f['nome'])}\n(.*?)(?=^### |^## |\Z)", ARTE, re.M | re.S)
    assert bloco, f"{cid} sem entrada no doc de arte"
    for campo in ("**Visual:**", "**Composição:**", "**Evitar:**"):
        assert campo in bloco.group(1), (cid, campo)
    if f["status"] == "adotada":
        return  # R4: o doc do Codex da criatura adotada não é tocado
    path = ROOT / "data" / "codex" / "monsters" / f"{cid}.md"
    assert path.is_file(), cid
    fm, body = parse_codex_file(str(path))
    assert fm.get("curated") is True and fm.get("type") == "monster" and fm.get("id") == cid
    assert fm.get("name") == f["nome"] and fm.get("visibility") == "public"
    assert REGIAO in fm["tags"] and f["familia"] in fm["tags"]
    assert re.search(r"^Tipo: .+ \| Perigo: (Baixo|Médio|Alto|Extremo)$", body, re.M)
    assert re.search(r"^Aparência: .+$", body, re.M) and re.search(
        r"^Como se luta: .+$", body, re.M
    )
    assert not re.search(r"\d", _one_line(re.search(r"^Como se luta: (.+)$", body, re.M).group(1)))


@pytest.mark.parametrize("cid", sorted(NOVAS))
def test_aparencia_unica(cid):
    """R18: uma fonte para a aparência — ficha == Codex == bestiary[id].appearance (<= 300)."""
    f = NOVAS[cid]
    aparencia = _one_line(f["aparencia"])
    assert len(aparencia) <= 300, (cid, len(aparencia))
    if f["status"] != "adotada":
        body = (ROOT / "data" / "codex" / "monsters" / f"{cid}.md").read_text(encoding="utf-8")
        assert re.search(r"^Aparência: (.+)$", body, re.M).group(1) == aparencia, cid
    if cid in BEST:  # as novas entram no bestiário na Etapa 5
        assert BEST[cid]["appearance"] == aparencia, cid
        assert BEST[cid]["name"] == f["nome"]


@pytest.mark.parametrize("cid", sorted(NOVAS))
def test_codex_frontmatter_e_entidade(cid):
    """R17: entidade em entities_extra e related_entities resolvem no grafo."""
    f = NOVAS[cid]
    assert cid in ENTS and ENTS[cid]["type"] == "monster" and ENTS[cid]["name"] == f["nome"]
    base = json.loads((ROOT / "data" / "graph" / "entities.json").read_text(encoding="utf-8"))
    for ref in f.get("related_entities") or []:
        assert ref in base or ref in ENTS, (cid, ref)
    for h in f["habitat"]:
        assert h in base or h in ENTS, (cid, h)
