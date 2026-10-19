"""SPEC-200 R13: jornadas FIXAS e versionadas do baseline de latencia.

Cada jornada declara nome, turnos de aquecimento (nao medidos), turnos medidos,
rota esperada e tamanho de entrada. As entradas sao imutaveis: mudar uma delas
invalida a comparacao com runs antigos (suba ``JOURNEYS_VERSION``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from collections.abc import Callable

JOURNEYS_VERSION = 1

_SHORT = "Observo o ambiente com atenção."
_MEDIUM = ("Observo com calma as pessoas, as portas e os caminhos ao redor, tentando "
           "entender onde estou e o que mudou desde que cheguei aqui.")
_LONG = ("Paro por um instante, respiro fundo e examino cada detalhe do lugar: as marcas "
         "no chão, o cheiro no ar, a forma como as sombras caem sobre as paredes e os sons "
         "distantes que chegam de todos os lados, tentando decidir com cuidado qual é o "
         "próximo passo mais sensato para mim e para quem possa estar me observando.")
_WARMUP = "Olho ao redor."


def _first_neighbor_name(region: str = "Nova Arcádia") -> str:
    import gamedata
    start = gamedata.start_location_for_region(region)
    neighbors = gamedata.get_connections(start.get("id", ""))
    return neighbors[0]["name"] if neighbors else start.get("name", "Nova Arcádia")


@dataclass(frozen=True)
class Journey:
    name: str
    description: str
    expected_route: str
    warmup: list[str] = field(default_factory=list)
    turns: list[str] = field(default_factory=list)
    turns_factory: Callable[[], list[str]] | None = None

    def measured_turns(self) -> list[str]:
        return list(self.turns_factory()) if self.turns_factory else list(self.turns)


JOURNEYS = {
    j.name: j for j in (
        Journey("J1_story_simple", "narracao simples, entradas curta/media/longa",
                "storyteller", [_WARMUP], [_SHORT, _MEDIUM, _LONG]),
        Journey("J2_combat_start", "primeiro golpe e rodada seguinte de combate",
                "combat_agent", [_WARMUP],
                ["Ataco com minha espada o inimigo à frente.", "Golpeio o inimigo de novo."]),
        Journey("J3_npc_dialogue", "conversa com NPC", "npc_actor", [_WARMUP],
                ["Falo com o viajante e pergunto sobre a estrada.",
                 "Pergunto se ele sabe de rumores na região."]),
        Journey("J4_loot_shop", "comercio / saque", "loot", [_WARMUP],
                ["Quero comprar uma poção de cura.", "Vasculho o baú com cuidado."]),
        Journey("J5_travel_replan", "viagem para local vizinho (replan por regiao)",
                "storyteller", [_WARMUP], [],
                turns_factory=lambda: [f"Viajo para {_first_neighbor_name()}."]),
        Journey("J6_first_turn_new_game", "primeiro turno logo apos /game/new",
                "storyteller", [], ["Começo a explorar o lugar."]),
    )
}


def select(spec: str) -> list[Journey]:
    if spec.strip().lower() == "all":
        return list(JOURNEYS.values())
    chosen = []
    for token in (t.strip() for t in spec.split(",") if t.strip()):
        match = [j for name, j in JOURNEYS.items() if name == token or name.startswith(token + "_")]
        if not match:
            raise SystemExit(f"jornada desconhecida: {token}")
        chosen.append(match[0])
    return chosen
