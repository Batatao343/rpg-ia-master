"""Matriz pareada de longruns por perfil, classe e nível inicial."""
from __future__ import annotations

from typing import TypedDict


class MatrixCase(TypedDict):
    index: int
    profile: str
    class_name: str
    start_level: int
    seed: int


LONGRUN_MATRIX: tuple[MatrixCase, ...] = (
    {"index": 1, "profile": "normal", "class_name": "Devoto do Abismo", "start_level": 1, "seed": 6200},
    {"index": 2, "profile": "explorador", "class_name": "Arcanista Cinzento", "start_level": 3, "seed": 6201},
    {"index": 3, "profile": "diplomatico", "class_name": "Médico de Campo", "start_level": 5, "seed": 6202},
    {"index": 4, "profile": "combate", "class_name": "Sangromante", "start_level": 7, "seed": 6203},
    {"index": 5, "profile": "comerciante", "class_name": "Corruptor", "start_level": 9, "seed": 6204},
    {"index": 6, "profile": "quester", "class_name": "Devoto do Abismo", "start_level": 11, "seed": 6205},
    {"index": 7, "profile": "recrutador", "class_name": "Médico de Campo", "start_level": 13, "seed": 6206},
    {"index": 8, "profile": "fujao", "class_name": "Arcanista Cinzento", "start_level": 15, "seed": 6207},
    {"index": 9, "profile": "secret_rusher", "class_name": "Corruptor", "start_level": 18, "seed": 6208},
    {"index": 10, "profile": "loot_abuser", "class_name": "Sangromante", "start_level": 20, "seed": 6209},
)


def case_label(case: MatrixCase) -> str:
    return f"{case['index']:02d}-{case['profile']}-lvl{case['start_level']}"

