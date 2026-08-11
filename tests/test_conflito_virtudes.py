"""Suíte da spec conflito-01: Virtudes, Vitalidade e Ferimentos (fundação de dados).

100% determinístico, offline. Cobre as tabelas derivadas de Corpo (gamedata),
o schema de Virtudes (state/PlayerStats), a distribuição 4/3/2/1/1 na criação,
a progressão por nível par e a migração v3→v4 (hard cutover)."""

import pytest

import gamedata


# --------------------------------------------------------------------------
# Etapa 1 — Tabelas derivadas de Corpo (doc 01 §8.1)
# --------------------------------------------------------------------------
def test_vitalidade_por_corpo():
    esperado = {0: 6, 1: 8, 2: 10, 3: 12, 4: 14, 5: 16}
    assert gamedata.VITALIDADE_POR_CORPO == esperado


def test_espacos_ferimento_por_corpo():
    esperado = {
        0: {"leve": 2, "grave": 1, "critico": 1},
        1: {"leve": 3, "grave": 1, "critico": 1},
        2: {"leve": 3, "grave": 2, "critico": 1},
        3: {"leve": 4, "grave": 2, "critico": 2},
        4: {"leve": 4, "grave": 3, "critico": 2},
        5: {"leve": 5, "grave": 3, "critico": 3},
    }
    assert gamedata.ESPACOS_FERIMENTO_POR_CORPO == esperado


def test_limites_gravidade_por_corpo():
    esperado = {
        0: {"leve": (1, 3), "grave": (4, 6), "critico": (7, None)},
        1: {"leve": (1, 4), "grave": (5, 8), "critico": (9, None)},
        2: {"leve": (1, 5), "grave": (6, 10), "critico": (11, None)},
        3: {"leve": (1, 6), "grave": (7, 12), "critico": (13, None)},
        4: {"leve": (1, 7), "grave": (8, 14), "critico": (15, None)},
        5: {"leve": (1, 8), "grave": (9, 16), "critico": (17, None)},
    }
    assert gamedata.LIMITES_GRAVIDADE_POR_CORPO == esperado


def test_vitalidade_para_corpo_helper():
    assert gamedata.vitalidade_para_corpo(0) == 6
    assert gamedata.vitalidade_para_corpo(3) == 12
    assert gamedata.vitalidade_para_corpo(5) == 16
    # fora da faixa: clampa em 0..5
    assert gamedata.vitalidade_para_corpo(-1) == 6
    assert gamedata.vitalidade_para_corpo(9) == 16


def test_espacos_ferimento_helper():
    assert gamedata.espacos_ferimento_para_corpo(3) == {"leve": 4, "grave": 2, "critico": 2}
    assert gamedata.espacos_ferimento_para_corpo(0) == {"leve": 2, "grave": 1, "critico": 1}


def test_categoria_ferimento_por_excedente():
    # Corpo 2: leve 1-5, grave 6-10, crítico 11+
    assert gamedata.categoria_ferimento(2, 1) == "leve"
    assert gamedata.categoria_ferimento(2, 5) == "leve"
    assert gamedata.categoria_ferimento(2, 6) == "grave"
    assert gamedata.categoria_ferimento(2, 10) == "grave"
    assert gamedata.categoria_ferimento(2, 11) == "critico"
    assert gamedata.categoria_ferimento(2, 99) == "critico"
    # excedente <=0 não gera ferimento
    assert gamedata.categoria_ferimento(2, 0) is None
    assert gamedata.categoria_ferimento(2, -3) is None


# --------------------------------------------------------------------------
# Etapa 2 — Schema PlayerStats/EnemyStats + sync de Vitalidade
# --------------------------------------------------------------------------
def test_sync_player_vitals_deriva_da_tabela():
    player = {"virtudes": {"mente": 1, "agilidade": 2, "forca": 3, "carisma": 1, "corpo": 3}}
    gamedata.sync_player_vitals(player, heal_to_full=True)
    assert player["max_vitalidade"] == 12
    assert player["vitalidade"] == 12
    assert player["ferimento_espacos"] == {"leve": 4, "grave": 2, "critico": 2}
    assert player["ferimentos"] == {"leve": [], "grave": [], "critico": []}


def test_sync_player_vitals_bump_de_corpo_cura_delta():
    player = {"virtudes": {"corpo": 2}}
    gamedata.sync_player_vitals(player, heal_to_full=True)
    assert player["max_vitalidade"] == 10 and player["vitalidade"] == 10
    # leva dano
    player["vitalidade"] = 4
    # sobe Corpo 2->3: teto 10->12, atual 4 ganha o delta (+2) -> 6
    player["virtudes"]["corpo"] = 3
    gamedata.sync_player_vitals(player)
    assert player["max_vitalidade"] == 12
    assert player["vitalidade"] == 6


def test_sync_player_vitals_clampa_ao_maximo():
    player = {"virtudes": {"corpo": 1}, "vitalidade": 999}
    gamedata.sync_player_vitals(player)
    assert player["vitalidade"] == 8


def test_enemy_virtudes_aceita_none():
    from state import EnemyStats  # noqa: F401 — só garante import do schema
    inimigo = {"id": "e1", "name": "Verme", "hp": 5, "max_hp": 5, "virtudes": None}
    assert inimigo["virtudes"] is None


# --------------------------------------------------------------------------
# Etapa 3 — Distribuição de Virtudes na criação (4/3/2/1/1)
# --------------------------------------------------------------------------
def test_valida_distribuicao_correta():
    from character_creator import validate_virtude_distribution
    # nenhuma exceção
    validate_virtude_distribution({"mente": 4, "agilidade": 3, "forca": 2, "carisma": 1, "corpo": 1})


def test_valida_distribuicao_soma_errada():
    from character_creator import validate_virtude_distribution
    with pytest.raises(ValueError):
        validate_virtude_distribution({"mente": 4, "agilidade": 4, "forca": 2, "carisma": 1, "corpo": 1})


def test_valida_distribuicao_faltando_chave():
    from character_creator import validate_virtude_distribution
    with pytest.raises(ValueError):
        validate_virtude_distribution({"mente": 4, "agilidade": 3, "forca": 2, "carisma": 1})


def test_valida_distribuicao_chave_extra_dnd():
    from character_creator import validate_virtude_distribution
    with pytest.raises(ValueError):
        validate_virtude_distribution({"str": 4, "dex": 3, "con": 2, "int": 1, "wis": 1})


def test_criacao_usa_virtudes_do_jogador():
    from character_creator import create_player_character
    escolha = {"mente": 1, "agilidade": 1, "forca": 4, "carisma": 2, "corpo": 3}
    sheet = create_player_character({
        "name": "Bruta", "class_name": "Devoto do Abismo", "race": "Humano",
        "level": "1", "virtudes": escolha,
    })
    assert sheet["virtudes"]["forca"] == 4
    assert sheet["virtudes"]["corpo"] == 3
    # Corpo 3 -> 12 + bônus de Postura 6; espaços continuam derivados só de Corpo.
    assert sheet["max_vitalidade"] == 18
    assert sheet["vitalidade"] == 18
    assert sheet["ferimento_espacos"] == {"leve": 4, "grave": 2, "critico": 2}
    # attributes NÃO existe mais no jogador
    assert "attributes" not in sheet


def test_criacao_sem_virtudes_usa_recomendacao_da_classe():
    from character_creator import create_player_character
    sheet = create_player_character({
        "name": "Arcano", "class_name": "Arcanista Cinzento", "race": "Humano", "level": "1",
    })
    # recomendação do Arcanista: mente 4 (primária)
    assert sheet["virtudes"]["mente"] == 4
    assert sorted(sheet["virtudes"].values()) == [1, 1, 2, 3, 4]


def test_criacao_distribuicao_invalida_rejeitada():
    from character_creator import create_player_character
    with pytest.raises(ValueError):
        create_player_character({
            "name": "X", "class_name": "Devoto do Abismo", "race": "Humano", "level": "1",
            "virtudes": {"mente": 5, "agilidade": 3, "forca": 2, "carisma": 1, "corpo": 1},
        })


# --------------------------------------------------------------------------
# Etapa 4 — Progressão por nível par (+1 Virtude, teto 5, recalc)
# --------------------------------------------------------------------------
def _player_lvl(level=3, corpo=2, vit=None):
    p = {"class_name": "Devoto do Abismo", "level": level, "xp": 0,
         "virtudes": {"mente": 1, "agilidade": 1, "forca": 4, "carisma": 1, "corpo": corpo},
         "pending_choices": []}
    gamedata.sync_player_vitals(p, heal_to_full=True)
    if vit is not None:
        p["vitalidade"] = vit
    return p


def test_nivel_par_oferece_escolha_de_virtude():
    from progression import grant_xp, XP_TABLE
    p = _player_lvl(level=3)
    p, events = grant_xp(p, XP_TABLE[4])  # sobe para nível 4
    assert p["level"] == 4
    kinds = [c["kind"] for c in p["pending_choices"]]
    assert "virtude" in kinds and "carta" in kinds


def test_nivel_impar_nao_oferece_virtude():
    from progression import grant_xp, XP_TABLE
    p = _player_lvl(level=2)
    p, _ = grant_xp(p, XP_TABLE[3])  # sobe para nível 3 (ímpar)
    assert p["level"] == 3
    kinds = [c["kind"] for c in p["pending_choices"]]
    assert "virtude" not in kinds


def test_subir_corpo_aumenta_vitalidade_na_hora():
    from progression import apply_choice
    p = _player_lvl(level=4, corpo=2)  # Vitalidade 10 + bônus de Postura 6
    p["pending_choices"] = [{"id": "lvl4-virtude", "level": 4, "kind": "virtude"}]
    assert p["max_vitalidade"] == 16
    p2, err = apply_choice(p, "lvl4-virtude", virtude="corpo")
    assert err is None
    assert p2["virtudes"]["corpo"] == 3
    assert p2["max_vitalidade"] == 18  # recalculou na hora


def test_virtude_acima_do_teto_rejeitada():
    from progression import apply_choice
    p = _player_lvl(level=4, corpo=2)
    p["virtudes"]["forca"] = 5  # já no teto
    p["pending_choices"] = [{"id": "lvl4-virtude", "level": 4, "kind": "virtude"}]
    p2, err = apply_choice(p, "lvl4-virtude", virtude="forca")
    assert err is not None
    assert p2 is p or p2 == p  # player intocado no erro


def test_nivel_maximo_e_dez():
    import progression
    assert progression.MAX_LEVEL == 10


# --------------------------------------------------------------------------
# Etapa 5 — Migração v3→v4 (hard cutover)
# --------------------------------------------------------------------------
def test_migracao_v3_marca_arquivado_sem_converter():
    import persistence
    raw = {
        "schema_version": 3,
        "player": {"name": "Velho", "class_name": "Sangromante", "level": 3,
                   "attributes": {"str": 14, "dex": 16, "con": 12, "int": 8, "wis": 10, "cha": 12},
                   "hp": 20, "max_hp": 20},
    }
    out = persistence.migrate_state(raw)
    assert out["schema_version"] == 5
    assert out["archived"] is True
    assert out.get("archived_reason")
    # NÃO inventou Virtudes a partir dos atributos
    assert "virtudes" not in out["player"]


def test_acao_em_save_arquivado_recusa_sem_crash(tmp_path, monkeypatch):
    import json
    import uuid
    from fastapi.testclient import TestClient
    import api
    import persistence

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    api._rate_hits.clear()
    client = TestClient(api.app)

    gid = str(uuid.uuid4())
    raw_v3 = {
        "schema_version": 3,
        "game_id": gid,
        "player": {"name": "Antigo", "class_name": "Devoto do Abismo", "level": 2,
                   "attributes": {"str": 16, "dex": 10, "con": 16, "int": 8, "wis": 12, "cha": 14},
                   "hp": 30, "max_hp": 30},
        "world": {"current_location": "Ruínas", "turn_count": 5},
        "message_history": [{"type": "human", "content": "olá"}],
    }
    with open(persistence.save_path(gid), "w", encoding="utf-8") as f:
        json.dump(raw_v3, f)

    # load migra e marca; a ação é recusada com 409 (nunca 500)
    r = client.post("/game/action", json={"input_text": "Ataco", "game_id": gid})
    assert r.status_code == 409
    assert "arquivad" in r.json()["detail"].lower() or "jornada" in r.json()["detail"].lower()


# --------------------------------------------------------------------------
# Etapa 6 — Auditoria: nenhum consumidor de produção lê attributes do JOGADOR
# --------------------------------------------------------------------------
def test_nenhum_read_de_attributes_do_jogador_em_producao():
    """Estilo HANDLED_KINDS: varre o código de produção e proíbe leitura de
    `attributes` a partir de dicts de jogador (player/char/sheet/final_char).
    O inimigo mantém `attributes` (attr_mods) até a conflito-04/05 — permitido."""
    import glob
    import os
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proibidos = [
        re.compile(r'\bplayer(?:\[[^\]]*\])?\.get\(\s*["\']attributes["\']'),
        re.compile(r'\bplayer\[\s*["\']attributes["\']\s*\]'),
        re.compile(r'\b(?:final_char|char|sheet)\[\s*["\']attributes["\']\s*\]'),
        re.compile(r'\b(?:final_char|char|sheet)\.get\(\s*["\']attributes["\']'),
    ]
    alvos = []
    for base in ("", "agents", "services", "playtest"):
        alvos += glob.glob(os.path.join(root, base, "*.py"))

    ofensores = []
    for path in alvos:
        if os.sep + "tests" + os.sep in path:
            continue
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if any(rx.search(line) for rx in proibidos):
                    ofensores.append(f"{os.path.relpath(path, root)}:{n}: {line.strip()}")
    assert not ofensores, "leitura de attributes do jogador em produção:\n" + "\n".join(ofensores)
