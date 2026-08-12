"""services/chase.py — fuga e perseguição (spec conflito-09).

Trilha própria (Pressionado→Afastado→Quase Livre→Escapou), condutor sempre o
protagonista com Virtude por abordagem, Teste de Sorte por companheiro, e
simulação AUTOMÁTICA e DETERMINÍSTICA (seed) do destino de um companheiro
abandonado. 100% Python — nenhuma chamada de LLM durante a simulação (risco §7:
reprodutibilidade por seed).

ADITIVO (como 03-08): módulo novo + testes. Substituir o fluxo simplificado atual
(`combat_flee_attempt`/`combat_flee_destination`) e ajustar os perfis `fujao`/
`quester` do playtest é cutover (conflito-13).
"""
import random
from typing import Dict, List, Optional

from services.conflict_resolution import roll_kept, virtude_value
from services.tactical_profile import pick_action

# Trilha de perseguição (R2). Abaixo de "pressionado" = alcançado (combate volta).
TRACK = ("pressionado", "afastado", "quase_livre", "escapou")
_DISTANCE_TO_TRACK = {"proximo": "pressionado", "distante": "afastado",
                      "separado": "quase_livre"}
_PURSUE_TRIGGERS = frozenset({"alvo_fugindo", "fugitivo_foge", "cacar", "persegue"})

# Abordagem → Virtude do condutor (R4).
APPROACH_VIRTUDE = {
    "correr": "agilidade", "desviar": "agilidade",
    "rotas": "mente", "atalhos": "mente",
    "romper": "forca", "obstaculos": "forca",
    "resistencia": "corpo", "prolongada": "corpo",
    "coordenar": "carisma", "mobilizar": "carisma",
}

# Desfechos possíveis do companheiro abandonado (R6).
ABANDON_OUTCOMES = ("fuga", "captura", "rendicao", "esconderijo",
                    "combate", "morte", "reencontro_futuro")


# ==========================================================================
# Etapa 1 — trilha de perseguição
# ==========================================================================
def initial_track(distance_state: str) -> str:
    """R2: posição inicial na trilha deriva da distância no momento da fuga."""
    return _DISTANCE_TO_TRACK.get(str(distance_state or "").lower(), "pressionado")


def will_pursue(pursuer: dict, scene_state: Optional[dict] = None) -> bool:
    """R3: política fechada; prosa livre nunca autoriza perseguição."""
    profile = pursuer.get("tactical_profile") or {}
    policy = str(
        pursuer.get("pursuit_policy") or profile.get("pursuit_policy") or ""
    ).strip().lower()
    return policy == "persegue"


def start_chase(scene: dict, fugitive_id: str, pursuers: List[dict], *,
                scene_state: Optional[dict] = None) -> dict:
    """R2/R3: inicia a perseguição. Posição inicial pela distância do fugitivo;
    perseguidores filtrados pelo perfil (só os que decidem seguir). Sem perseguidor
    disposto → escapou."""
    pos = (scene.get("positions") or {}).get(fugitive_id) or {}
    trilha = initial_track(pos.get("distance_state", "proximo"))
    seguidores = [p for p in pursuers if will_pursue(p, scene_state)]
    if not seguidores:
        trilha = "escapou"
    return {"trilha": trilha, "perseguidores": [p.get("id") or p.get("name") for p in seguidores],
            "fugitive_id": fugitive_id, "alcancado": False, "escapou": trilha == "escapou"}


def can_resume(chase: Optional[dict], fugitive_id: str,
               pursuers: List[dict]) -> bool:
    """Confirma que um snapshot pertence à perseguição ativa atual.

    Estados terminais nunca são retomados. A comparação fechada dos IDs evita
    transportar progresso para outro encontro depois de morte/spawn de inimigo.
    """
    if not isinstance(chase, dict):
        return False
    if chase.get("alcancado") or chase.get("escapou"):
        return False
    if chase.get("trilha") not in TRACK[:-1]:
        return False
    if chase.get("fugitive_id") != fugitive_id:
        return False
    current = {
        str(p.get("id") or p.get("name"))
        for p in pursuers or [] if will_pursue(p)
    }
    stored = {str(pid) for pid in (chase.get("perseguidores") or [])}
    return bool(current) and current == stored


# ==========================================================================
# Etapa 2 — condutor + dificuldade (R4)
# ==========================================================================
def chase_conductor(party: List[dict]) -> Optional[dict]:
    """R4: o protagonista SEMPRE conduz a fuga da party."""
    for m in party or []:
        if m.get("is_player") or m.get("player") or m.get("protagonist"):
            return m
    return (party or [None])[0]


def approach_virtude(approach: str) -> str:
    """R4: Virtude coerente com a abordagem de fuga (default Agilidade)."""
    return APPROACH_VIRTUDE.get(str(approach or "").lower(), "agilidade")


def chase_difficulty(pursuer_principal: dict) -> int:
    """R4: dificuldade da fuga depende do perseguidor principal (Agilidade dele)."""
    return 10 + virtude_value(pursuer_principal or {}, "agilidade")


# ==========================================================================
# Etapa 3 — Teste de Sorte dos companheiros (R5)
# ==========================================================================
def luck_roll(rng=None) -> int:
    """R5: 1d10 por companheiro — 1-2 Complicação (-1), 3-8 Neutro (0), 9-10 Ajuda (+1)."""
    rng = rng or random
    d = rng.randint(1, 10)
    if d <= 2:
        return -1
    if d >= 9:
        return 1
    return 0


def luck_to_advantage(rolls: List[int]) -> int:
    """R5: Ajuda e Complicação se anulam; saldo positivo = Vantagem (+1), negativo =
    Desvantagem (-1), empate = normal. NÃO acumula além de 1 (só o sinal importa)."""
    net = sum(1 if r > 0 else (-1 if r < 0 else 0) for r in rolls or [])
    return 1 if net > 0 else (-1 if net < 0 else 0)


def resolve_chase_round(chase: dict, *, condutor_virtude: int = 0, difficulty: int = 12,
                        companion_luck: Optional[List[int]] = None, rng=None) -> dict:
    """R2/R4/R5: um round de perseguição. Sucesso avança 1 na trilha; falha recua 1
    (abaixo de Pressionado = alcançado, combate normal retorna)."""
    if chase.get("trilha") == "escapou":
        return chase
    adv = luck_to_advantage(companion_luck or [])
    roll = roll_kept(adv, rng)
    total = sum(roll["kept"]) + int(condutor_virtude)
    sucesso = total >= int(difficulty)

    idx = TRACK.index(chase["trilha"]) if chase.get("trilha") in TRACK else 0
    if sucesso:
        new = TRACK[min(len(TRACK) - 1, idx + 1)]
    else:
        new = TRACK[idx - 1] if idx > 0 else "alcancado"
    chase["trilha"] = new
    chase["alcancado"] = new == "alcancado"
    chase["escapou"] = new == "escapou"
    chase["_last"] = {"total": total, "difficulty": int(difficulty),
                      "sucesso": sucesso, "advantage": adv}
    return chase


# ==========================================================================
# Etapa 4 — abandono + simulação automática (R6)
# ==========================================================================
def abandon_companion(party: List[dict], companion_id: str) -> Optional[dict]:
    """R6: remove o companheiro da party (separado) e o devolve pra simulação de
    destino. A Complicação que ele geraria some junto (ele sai do pool de Sorte)."""
    for i, m in enumerate(list(party or [])):
        if (m.get("id") or m.get("name")) == companion_id:
            m["separated"] = True
            m["in_party"] = False
            return party.pop(i)
    return None


def _weighted_choice(rng: random.Random, weights: Dict[str, float]) -> str:
    total = sum(weights.values()) or 1.0
    pick = rng.random() * total
    acc = 0.0
    for outcome, w in weights.items():
        acc += w
        if pick <= acc:
            return outcome
    return next(iter(weights))


def simulate_abandoned_companion(companion: dict, scene_state: Optional[dict],
                                 seed) -> dict:
    """R6: destino do companheiro abandonado por SIMULAÇÃO automática completa —
    estado, perfil, terreno, perseguidores — DETERMINÍSTICA por seed (nunca
    `random.random()` sem seed). Retorna {resultado, fatos_relacionais}."""
    rng = random.Random(seed)
    scene = scene_state or {}
    name = companion.get("name") or companion.get("id") or "O companheiro"

    weights = {o: 1.0 for o in ABANDON_OUTCOMES}
    maxv = int(companion.get("max_vitalidade", 0) or 0)
    vit = int(companion.get("vitalidade", maxv) or 0)
    vit_ratio = (vit / maxv) if maxv > 0 else 1.0
    agi = virtude_value(companion, "agilidade")
    perseguidores = int(scene.get("pursuers", len(scene.get("pursuer_ids", []) or [])) or 0)
    terreno_favoravel = bool(scene.get("terreno_favoravel"))

    # estado ferido pesa pra desfechos ruins; agilidade/terreno pesam pra escapar
    if vit_ratio <= 0.25:
        weights["morte"] += 2.5
        weights["captura"] += 1.5
    elif vit_ratio <= 0.5:
        weights["captura"] += 1.0
        weights["combate"] += 1.0
    weights["fuga"] += 0.4 * agi
    weights["esconderijo"] += 0.3 * agi + (1.0 if terreno_favoravel else 0.0)
    weights["captura"] += 0.6 * perseguidores
    weights["combate"] += 0.4 * perseguidores
    if companion.get("tactical_profile") and any(
            p.get("action_hint", "").find("rende") >= 0
            for p in companion["tactical_profile"].get("priorities", [])):
        weights["rendicao"] += 1.5
    weights["reencontro_futuro"] += 0.5

    resultado = _weighted_choice(rng, weights)
    fatos = [f"{name} foi deixado para trás durante a fuga."]
    fatos.append({
        "fuga": f"{name} conseguiu escapar por conta própria.",
        "captura": f"{name} foi capturado pelos perseguidores.",
        "rendicao": f"{name} se rendeu para sobreviver.",
        "esconderijo": f"{name} se escondeu e sumiu do radar.",
        "combate": f"{name} ficou preso em combate ao ser abandonado.",
        "morte": f"{name} não sobreviveu à separação.",
        "reencontro_futuro": f"{name} escapou e pode reaparecer mais tarde.",
    }[resultado])
    return {"resultado": resultado, "fatos_relacionais": fatos}


# ==========================================================================
# Etapa 5 — sacrifício voluntário + ataques em perseguição (R7/R8)
# ==========================================================================
def can_volunteer_sacrifice(companion: dict) -> bool:
    """R7: só um companheiro com traço apropriado em prioridade VÁLIDA pode se
    oferecer para ficar. Sem o traço, ninguém é obrigado a se sacrificar."""
    if companion.get("se_sacrifica_pelo_grupo"):
        return True
    profile = companion.get("tactical_profile") or {}
    for pr in profile.get("priorities", []) or []:
        hint = str(pr.get("action_hint", "")).lower()
        if "sacrific" in hint or "sacrifica_pelo_grupo" in (pr.get("blocks") or []):
            return True
    return False


def offer_sacrifice(companion: dict, accept: bool) -> dict:
    """R7: o jogador aceita ou recusa a oferta. Recusar não força nada (sem
    penalidade automática universal — a percepção dos NPCs é contextual)."""
    if not can_volunteer_sacrifice(companion):
        return {"sacrificed": False, "reason": "sem traço de sacrifício"}
    if not accept:
        return {"sacrificed": False, "reason": "recusado pelo jogador"}
    companion["sacrificed"] = True
    companion["in_party"] = False
    return {"sacrificed": True, "reason": "aceito"}


def chase_attack(chase: dict, *, melee: bool) -> dict:
    """R8: ataque à distância continua Ação normal durante a perseguição. Corpo a
    corpo exige reengajamento — em Pressionado, reengajar ENCERRA a perseguição
    (combate normal retorna); em Afastado/Quase Livre precisa reduzir distância antes."""
    trilha = chase.get("trilha")
    if not melee:
        return {"allowed": True, "ends_chase": False, "mode": "distancia"}
    if trilha == "pressionado":
        chase["trilha"] = "alcancado"
        chase["alcancado"] = True
        return {"allowed": True, "ends_chase": True, "mode": "reengajar"}
    return {"allowed": False, "ends_chase": False, "mode": "precisa_reduzir_distancia"}
