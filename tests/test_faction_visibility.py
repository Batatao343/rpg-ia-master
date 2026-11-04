"""SPEC-377 item 4 (D4=a) — as duas politicas de esconder faccao ficam como estao.

SPEC-293 (`faction_display.display_label`): o NOME de combatente de faccao nao conhecida,
publica ou secreta, vira papel. SPEC-314 (`faction_gate.display_faction`): o NPC/contexto
citam a faccao publica pelo nome e escondem so a secreta. A matriz abaixo fixa as duas.
"""

from __future__ import annotations

import pytest

from services import faction_display as fd
from services import faction_gate as fg

UNKNOWN = {"faction_intel": {}}

# fid, nome canonico do 1o combatente, secreta?, rotulo do HUD sem intel, nome para o NPC sem intel
MATRIX = [
    ("legiao_ferro", "Soldado da Legião de Ferro", False, "Soldado", "A Legião de Ferro"),
    (
        "clas_combate",
        "Guerreiro Bjorn",
        False,
        "Guerreiro Bjorn",
        "Os Clãs de Combate de Skallgard",
    ),
    ("mao_sombria", "Degolador da Mão Sombria", True, "Degolador", fg.UNKNOWN_FACTION),
    ("filhos_chama_azul", "Iniciado da Chama Azul", True, "Iniciado", fg.UNKNOWN_FACTION),
    ("druidas_renegados", "Druida-Renegado", True, fd.GENERIC_LABEL, fg.UNKNOWN_FACTION),
    ("cultistas_destilacao", "Cultista da Destilação", True, "Cultista", fg.UNKNOWN_FACTION),
]


@pytest.mark.parametrize(("fid", "name", "secret", "hud", "npc"), MATRIX)
def test_matriz_atual_sem_intel(fid, name, secret, hud, npc):
    assert fg.is_secret(fid) is secret
    assert fd.display_label(name, fid, [], {}) == hud
    assert fg.display_faction(UNKNOWN, fid) == npc


@pytest.mark.parametrize(("fid", "name", "secret", "hud", "npc"), MATRIX)
def test_conhecida_mostra_nome_completo_nas_duas(fid, name, secret, hud, npc):
    intel = {fid: {"known": True}}
    assert fd.display_label(name, fid, [], intel) == name
    assert fg.display_faction({"faction_intel": intel}, fid) not in ("", fg.UNKNOWN_FACTION)


def test_politicas_divergem_so_na_publica():
    """R19: HUD esconde a publica desconhecida, o NPC a cita; nas secretas as duas escondem."""
    assert fd.display_label("Soldado da Legião de Ferro", "legiao_ferro", [], {}) == "Soldado"
    assert fg.display_faction(UNKNOWN, "legiao_ferro") == "A Legião de Ferro"
    assert fg.display_faction(UNKNOWN, "mao_sombria") == fg.UNKNOWN_FACTION
