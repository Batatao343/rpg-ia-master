"""SPEC-314 revisão sol — vazamentos de NOME restantes (P1-1/2, P2-1..4)."""

from __future__ import annotations

import json

from services import chronicle
from services import context_builder as cb
from services import faction_gate as fg
from services import lore_quests as lq
from services import npc_knowledge as nk
from services.secret_signatures import sanitize_beat
from tests.spec310_helpers import make_state

SECRETAS = ("mao_sombria", "filhos_chama_azul", "druidas_renegados", "cultistas_destilacao")
REL_EV = {
    "event_id": "ev-rel",
    "type": "faction_relation_changed",
    "turn": 3,
    "target_id": "filhos_chama_azul",
    "payload": {"other_faction_id": "legiao_ferro", "relation": "guerra"},
}


def test_p1_1_subject_text_mascara_nome():
    st = make_state(event_log=[REL_EV])
    txt = nk._subject_text(st, "event", "ev-rel")
    assert "Chama Azul" not in txt and "uma facção desconhecida" in txt
    st["faction_intel"] = {"filhos_chama_azul": {"known": True}}
    assert "Chama Azul" in nk._subject_text(st, "event", "ev-rel")


def test_p1_2_linha_de_controle_mascarada():
    st = make_state()
    edge = {"source": "filhos_chama_azul", "target": "na_anel_ferro", "type": "controls"}
    proj = {"dynamic_edges": [edge]}
    st["world_projection"] = proj
    facts = cb.collect_dynamic_facts(
        st, purpose="story", query="", current_loc="Anel de Ferro", scene_entities=[]
    )
    text = "\n".join(f.text for f in facts)
    assert "Chama Azul" not in text


def _labels_bestiario() -> list[tuple[str, str]]:
    data = json.load(open("data/bestiary.json", encoding="utf-8"))
    rows = data.items() if isinstance(data, dict) else [(x.get("id"), x) for x in data]
    out = []
    for k, v in rows:
        name = v.get("name", "") if isinstance(v, dict) else ""
        out.append((str(k), str(name)))
    return out


def test_p2_1_mascara_cobre_rotulos_reais_do_bestiario():
    st = make_state()
    termos = ("mao_sombria", "chama_azul", "destilacao", "druida_renegado")
    hits = [(k, n) for k, n in _labels_bestiario() if any(t in k for t in termos)]
    assert len(hits) >= 4
    for k, n in hits:
        masked = fg.mask_secret_names(st, f"{k} {n} anda rondando")
        assert masked != f"{k} {n} anda rondando", (k, n)
        for alias in ("Mão Sombria", "Chama Azul", "Destilação", "Druida-Renegado"):
            assert alias.lower() not in masked.lower()
        for slug in ("mao_sombria", "chama_azul", "destilacao", "druida_renegado"):
            assert slug not in masked
    # nomes parecidos de facção PÚBLICA / criatura comum não são tocados
    assert fg.mask_secret_names(st, "Renegado do Ermo e Necromante Renegado") == (
        "Renegado do Ermo e Necromante Renegado"
    )
    # fação conhecida não é mascarada
    st["faction_intel"] = {"mao_sombria": {"known": True}}
    assert "Mão Sombria" in fg.mask_secret_names(st, "Degolador da Mão Sombria")


def test_p2_1_menu_usa_chave_opaca_e_traduz_de_volta():
    st = make_state()
    items = [
        {
            "kind": "cacar_criatura",
            "anchor_id": "enemy_degolador_mao_sombria",
            "label": "Degolador da Mão Sombria anda rondando",
        },
        {
            "kind": "cacar_criatura",
            "anchor_id": "enemy_gargula_ferro",
            "label": "Gárgula anda rondando",
        },
    ]
    keyed = lq._opaque_keys(st, items)
    block = lq._render_menu(keyed, st)
    assert "enemy_degolador_mao_sombria" not in block and "Mão Sombria" not in block
    assert "anchor_id=m1" in block and "anchor_id=enemy_gargula_ferro" in block
    assert lq.resolve_menu_key(keyed, "m1") == "enemy_degolador_mao_sombria"
    assert lq.resolve_menu_key(keyed, "enemy_gargula_ferro") == "enemy_gargula_ferro"


def test_p2_2_lore_publico_com_nome_mascarado(monkeypatch):
    def fake(query, index_name="lore", max_visibility="public", **_k):
        return "A Mão Sombria (para quem trabalha) cobra pedágio."

    monkeypatch.setattr(cb, "query_rag", fake)
    monkeypatch.setattr(cb, "RAG_AVAILABLE", True)
    st = make_state()
    for purpose in ("npc", "story", "planning"):
        pack = cb.build_context_pack(st, "pedágio", purpose, own_faction="mao_sombria")
        assert "Mão Sombria" not in pack.lore_block and "[facção desconhecida]" in pack.lore_block
    st["faction_membership"] = {"mao_sombria": {"status": "ativo", "rank": 0}}
    pack = cb.build_context_pack(st, "pedágio", "npc", own_faction="mao_sombria")
    assert "Mão Sombria" in pack.lore_block  # D3: o membro conhece a própria fação


def test_p2_3_cronica_e_memoria_mascaram_ocupante_secreto():
    ev = {
        "event_id": "ev-ctl",
        "type": "location_control_changed",
        "turn": 4,
        "target_id": "na_anel_ferro",
        "payload": {"new_controller_id": "filhos_chama_azul"},
        "source": "engine",
    }
    st = make_state()
    txt = chronicle.render_milestone(ev, {}, st)
    assert "Chama Azul" not in txt and "homens sem insígnia" in txt
    assert "Chama Azul" in chronicle.render_milestone(ev, {})  # sem state: comportamento antigo
    st["faction_intel"] = {"filhos_chama_azul": {"known": True}}
    assert "Chama Azul" in chronicle.render_milestone(ev, {}, st)
    assert "uma facção desconhecida" in cb.render_event(ev, {}, make_state())


def test_p2_4_sanitize_beat_neutraliza_nome_e_plano():
    st = make_state()
    neutro = "Investigue os rumores locais."
    assert sanitize_beat("Siga a Mão Sombria até Brekmar", st) == neutro
    assert (
        sanitize_beat("Impeça de libertar Malagor da armadura no Palácio de Obsidiana", st)
        == neutro
    )
    assert (
        sanitize_beat("Fale com o ferreiro e compre uma espada", st)
        == "Fale com o ferreiro e compre uma espada"
    )
    st["faction_intel"] = {"filhos_chama_azul": {"known": True, "knows_goal": True}}
    txt = "Impeça de libertar Malagor da armadura no Palácio de Obsidiana"
    assert sanitize_beat(txt, st) == txt
