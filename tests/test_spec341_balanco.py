"""SPEC-341 — balanço das Cartas pós-SPEC-339.

R14 inventário fechado de taunt/marca de onda; R15/R16 as Cartas de duração 1 valem no
`run_round` real; R2 legadas intactas (golden); R5 versões/lint/orçamento das alteradas;
R9/R10/R18 artefatos da arena (tetos e pisos) + `versoes` batendo com o catálogo.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from services import card_effects as fx
from services import card_lint, cards
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct
from tests import spec330_equivalence as eq

ROOT = Path(__file__).resolve().parent.parent
SPEC_DOCS = ROOT / "docs" / "spec341"

# R14: id -> (controle, `duracao` efetiva esperada; ausente = 1)
ONDA_CONTROLE: dict[str, tuple[str, int]] = {
    "dev1_zel_ciume_aberto": ("taunt", 1),
    "dev1_zel_corpo_entre": ("taunt", 1),
    "dev1_zel_ninguem_mais": ("taunt", 1),
    "san1_exp_veia_a_mostra": ("taunt", 1),
    "san1_exp_plateia_cega": ("taunt", 1),
    "san1_exp_teatro_de_facas": ("taunt", 1),
    "san1_sil_marca_de_unha": ("marca", 1),
    "san1_sil_cirurgia_sem_testemunha": ("marca", 1),
    "san1_ava_livro_de_dividas": ("marca", 1),
    "med1_bot_giz_vermelho": ("marca", 1),
    "neu1_ka_divida_gravada": ("marca", 1),
    "arc1_imp_parafuso": ("marca", 2),
    "arc1_imp_arame": ("marca", 2),
}

# Cartas de onda alteradas por esta spec: id -> `versao` mínima exigida (preenchido nas Etapas 2-3)
ALTERADAS: dict[str, int] = {
    "med1_bot_giz_vermelho": 2,
    "neu1_ka_divida_gravada": 2,
    "san1_ava_cobranca_adiada": 2,
    "san1_ava_juros_do_primeiro": 2,
    "san1_sil_corte_sem_aviso": 2,
    "san1_sil_ponto_cego": 2,
}

D1_REAIS = [i for i, (_, d) in ONDA_CONTROLE.items() if d == 1]


def _legacy_ids() -> set[str]:
    with open(eq.GOLDEN, encoding="utf-8") as f:
        return set(json.load(f))


def _duracao_efetiva(card: dict, kind: str) -> int:
    efs = [e for e in fx.normalize(card) if e.get("kind") == kind]
    return max(int(e.get("duracao", e.get("duration", 1)) or 1) for e in efs)


# --------------------------------------------------------------------------
# R14 — inventário fechado
# --------------------------------------------------------------------------
def test_inventario_controle_de_onda_fechado():
    legacy = _legacy_ids()
    achados: dict[str, tuple[str, int]] = {}
    for cid, card in cards.all_cards().items():
        if cid in legacy or not str(card.get("origem", "")).startswith("onda"):
            continue  # só Cartas de onda (335/336); baralhos de inimigo (332) ficam de fora
        for kind in ("taunt", "marca"):
            if any(e.get("kind") == kind for e in fx.normalize(card)):
                achados[cid] = (kind, _duracao_efetiva(card, kind))
    esperado = {k: v for k, v in ONDA_CONTROLE.items()}
    nao_classificadas = {k: v for k, v in achados.items() if k not in esperado}
    assert not nao_classificadas, f"taunt/marca de onda fora da tabela do R14: {nao_classificadas}"
    divergentes = {k: (achados.get(k), v) for k, v in esperado.items() if achados.get(k) != v}
    assert not divergentes, f"duracao diverge da tabela (achado, esperado): {divergentes}"


# --------------------------------------------------------------------------
# R15/R16 — as de duracao 1 valem no motor real
# --------------------------------------------------------------------------
_V = {"forca": 3, "agilidade": 2, "corpo": 5, "mente": 3, "carisma": 2}
ORDENS = {"hero_first": "heroes", "enemy_first": "enemy"}


class _Rng0(random.Random):
    """random() sempre 0.0: chances (Provocação, acerto) sempre passam."""

    def random(self):
        return 0.0


def _actor(aid: str, **kw) -> dict:
    base = {"id": aid, "name": aid, "virtudes": dict(_V)}
    base.update(kw)
    return orch.ensure_combat_sheet(base, is_player=(aid == "player"))


def _cena(card: dict):
    cid = card["id"]
    player = _actor(
        "player",
        class_name=card.get("classe") or "Devoto do Abismo",
        known_cards=[cid],
        prepared_cards=[cid],
        entropy=10,
        max_entropy=10,
        level=15,
        virtudes=dict(_V, agilidade=1),
    )
    ally = _actor("ally", categoria="companheiro", transient=True, virtudes=dict(_V, agilidade=9))
    e1 = _actor("e1", virtudes=dict(_V, agilidade=1))
    e2 = _actor("e2", virtudes=dict(_V, agilidade=1))
    actors = {"player": player, "ally": ally, "e1": e1, "e2": e2}
    scene = cs.new_scene()
    for i in actors:
        cs.place(scene, i)
    cs.freeze(scene)
    sides = {"hero": ["player"], "ally": ["ally"], "enemy": ["e1", "e2"]}
    return actors, scene, sides


@pytest.mark.parametrize("ordem", ORDENS)
@pytest.mark.parametrize("cid", D1_REAIS)
def test_controle_d1_de_onda_vale_no_turno_seguinte(cid, ordem, monkeypatch):
    card = cards.get_card(cid)
    kind = ONDA_CONTROLE[cid][0]
    actors, scene, sides = _cena(card)
    # Cartas de suporte (1º efeito protege "eu") miram o próprio jogador; as demais, o inimigo e1.
    alvo_decl = "player" if card["efeitos"][0].get("alvo") == "eu" else "e1"
    visto: list[tuple[int, str, bool]] = []
    original = orch._resolve_actor_turn

    def spy(scene_, actor, actor_id, actors_by_id, sides_, decl, st, out, rng):
        alvo = actors_by_id["e1"]
        if actor_id in ("player", "e1"):
            pres = any(c.get("control") == kind for c in alvo.get("active_conditions") or [])
            visto.append((st.get("rnd", 0), actor_id, pres))
        return original(scene_, actor, actor_id, actors_by_id, sides_, decl, st, out, rng)

    monkeypatch.setattr(orch, "_resolve_actor_turn", spy)
    logs_por_rodada: list[list[str]] = []
    for rnd in range(1, 5):
        decl = (
            ct.TurnDeclaration(
                actor_id="player",
                acao=ct.TurnStep(kind="card", card_id=cid, target_id=alvo_decl),
            )
            if rnd == 1
            else ct.TurnDeclaration(actor_id="player")
        )
        out = orch.run_round(
            scene,
            actors,
            sides,
            {"player": actors["player"]},
            declarations={"player": decl},
            initiator=ORDENS[ordem],
            rng=_Rng0(rnd),
        )
        logs_por_rodada.append(list(out["logs"]))
    if kind == "taunt":
        # a Provocação é lida no PORTADOR (e1): exatamente 1 turno dele a vê ativa
        assert sum(p for _, a, p in visto if a == "e1") == 1, visto
        # e o aliado (mais ágil) seria o alvo comum: só 1 declaração do e1 mira o jogador
        ataques = [ln for rd in logs_por_rodada[:2] for ln in rd if ln.startswith("e1 → player")]
        assert len(ataques) == 1, logs_por_rodada[:2]
    else:
        # a Marca é lida no ALVO no turno do APLICADOR: cobre exatamente o próximo ataque
        assert sum(p for _, a, p in visto if a == "player") == 1, visto


# --------------------------------------------------------------------------
# R2 — legadas intactas
# --------------------------------------------------------------------------
def test_legadas_intactas():
    with open(eq.GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)
    legacy = eq.legacy_cards()
    assert len(legacy) == len(golden) == 308
    diffs = [cid for cid, c in sorted(legacy.items()) if eq.run_card_full(c) != golden[cid]]
    assert not diffs, f"legadas mudaram: {diffs[:5]}"


# --------------------------------------------------------------------------
# R5 — alteradas: versão, lint, orçamento
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cid", sorted(ALTERADAS))
def test_cartas_alteradas_sobem_versao_e_passam_no_lint(cid):
    card = cards.get_card(cid)
    assert int(card.get("versao", 1) or 1) >= ALTERADAS[cid]
    # `voz` = sabor da descrição (não mudou nesta spec; aviso pré-existente da onda 1)
    issues = [i for i in card_lint.lint_card(card) if i.code != "voz"]
    assert not issues, [str(i) for i in issues]
    assert fx.budget_error(card) is None


# --------------------------------------------------------------------------
# R9/R10/R18 — artefatos da arena
# --------------------------------------------------------------------------
def _load(nome: str) -> dict:
    path = SPEC_DOCS / nome
    assert path.exists(), f"{nome} ausente: rode a arena da Etapa 5 (R18)"
    return json.loads(path.read_text(encoding="utf-8"))


# D4-bis (dono, 27/10): silencioso (76,2 %) e o agregado Sangromante/todas (75,4 %) aceitos como
# exceção registrada nas sementes 0–19. O teto global de 75 % NÃO muda para as demais subclasses.
EXCECAO_ACEITA = {"silencioso": 0.762, "todas": 0.754}


# D4-ter (dono, 27/10): na held-out 20–99, avaro 75,2 %, silencioso 76,6 % e todas 75,6 % aceitos.
EXCECAO_HELD_OUT = {"avaro": 0.752, "silencioso": 0.766, "todas": 0.756}


def _checar_faixa(arte: dict, *, held_out: bool):
    sang = arte["posturas"]["Sangromante"]
    for sub in ("avaro", "silencioso", "todas"):
        aceita = EXCECAO_HELD_OUT if held_out else EXCECAO_ACEITA
        teto = max(0.75, aceita.get(sub, 0.75))
        assert sang[sub]["padrao"] <= teto, (sub, sang[sub]["padrao"])
    assert sang["exposto"]["padrao"] >= 0.65, sang["exposto"]["padrao"]
    if not held_out:
        assert sang["exposto"]["padrao"] >= 0.704 - 0.05
    for sub, v in sang.items():
        assert v["total"] >= 0.45, (sub, v["total"])


def test_arena_final_dentro_da_faixa():
    _checar_faixa(_load("arena-final.json"), held_out=False)


def test_arena_confirmacao_dentro_da_faixa():
    arte = _load("arena-confirmacao.json")
    _checar_faixa(arte, held_out=True)
    for cls, sub in (("Corruptor", "alma"), ("Médico de Campo", "boticario")):
        padrao = arte["posturas"][cls][sub]["padrao"]
        assert 0.45 <= padrao <= 0.75, (cls, sub, padrao)


@pytest.mark.parametrize("nome", ["arena-final.json", "arena-confirmacao.json"])
def test_arena_versoes_batem_com_catalogo(nome):
    arte = _load(nome)
    assert arte["versoes"], "versoes das Cartas alteradas ausentes"
    for cid, v in arte["versoes"].items():
        atual = int((cards.get_card(cid) or {}).get("versao", 1) or 1)
        assert atual == v, f"{cid}: catálogo v{atual} != arena v{v} (refaça a arena)"
    assert set(ALTERADAS) <= set(arte["versoes"])
