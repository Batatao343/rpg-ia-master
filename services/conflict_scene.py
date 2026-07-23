"""services/conflict_scene.py — cena de conflito posicional (spec conflito-03).

Estrutura de dados PURA (dict-based, serializável no save) para o combate novo:
zonas nomeadas (não-grid), 3 eixos independentes de posição (Distância/Postura/
Ocultação), Engajamento como relação separada, objetos interativos com catálogo
FECHADO de efeitos, e a regra de CENA CONGELADA (nada entra por interpretação
livre depois do início). NÃO resolve dano/efeito — isso é conflito-04/05.

Convivência: `round/active/order/idle_turns` do dict `combat` seguem existindo em
paralelo até o cutover (conflito-13). A ConflictScene mora em `combat["scene"]`.
"""
from typing import Dict, List, Optional

# --- Eixos independentes -----------------------------------------------------
DISTANCES = ("proximo", "distante", "separado")   # 3 estágios (R2)
POSTURAS = ("protegido", "neutro", "exposto")      # 3 estados (R2)
OCULTACOES = ("visivel", "escondido")              # 2 estados (R2)

# --- Catálogo FECHADO de efeitos (R6) — compartilhado com conflito-10/11 ------
EFFECT_KINDS = frozenset({
    "alter_terrain", "block_route", "unblock_route", "damage",
    "request_reaction", "apply_condition", "reposition",
    "spawn_reinforcement", "destroy_object", "change_environment_condition",
})

_COST_STATES = ("pre_acao", "pos_acao", "acao")

# --- Orçamento de ação por turno (conflito-06) -------------------------------
# Cada participante tem 1 Pré-Ação + 1 Ação + 1 Pós-Ação por turno. Manobras
# (Engajar/Desengajar/Guardar/Esconder-se/Procurar/alertar) debitam conforme R6-R10.
TURN_BUDGET = {"pre_acao": 1, "acao": 1, "pos_acao": 1}
_PRE_OU_POS = "pre_ou_pos"


def _pos(scene: dict, participant_id: str) -> Optional[dict]:
    return (scene.get("positions") or {}).get(participant_id)


def _spend_budget(pos: dict, cost: str) -> Optional[str]:
    """Debita 1 do orçamento; devolve o estado gasto ou None se indisponível.
    `pre_ou_pos` tenta Pré-Ação e cai pra Pós-Ação (R6)."""
    b = pos.setdefault("budget", dict(TURN_BUDGET))
    if cost == _PRE_OU_POS:
        for state in ("pre_acao", "pos_acao"):
            if int(b.get(state, 0) or 0) > 0:
                b[state] = int(b[state]) - 1
                return state
        return None
    if int(b.get(cost, 0) or 0) > 0:
        b[cost] = int(b[cost]) - 1
        return cost
    return None


def reset_turn_budget(scene: dict, participant_id: str) -> None:
    """Restaura Pré-Ação/Ação/Pós-Ação no começo do turno do participante."""
    pos = _pos(scene, participant_id)
    if pos is not None:
        pos["budget"] = dict(TURN_BUDGET)


def validate_effect_kind(effect: dict) -> bool:
    """True se `effect.kind` está no catálogo fechado (R6). Efeito inventado pela
    LLM fora do catálogo é rejeitado — nunca vira regra nova."""
    return bool(effect) and str(effect.get("kind")) in EFFECT_KINDS


# --- Construção --------------------------------------------------------------
def new_scene(zones: Optional[List[dict]] = None) -> dict:
    return {
        "zones": list(zones or [{"id": "z0", "name": "Campo", "connections": []}]),
        "positions": {},
        "objects": [],
        "frozen": False,
        "reinforcement_triggers": [],
    }


def place(scene: dict, participant_id: str, *, zone_id: str = "z0",
          distance_state: str = "proximo", postura: str = "neutro",
          ocultacao: str = "visivel") -> dict:
    """Posiciona um participante. Bloqueado se a cena já está congelada (R8) —
    participantes entram na preparação, não no meio do conflito."""
    if scene.get("frozen"):
        return {"ok": False, "error": "Cena congelada: participante não entra fora de gatilho.", "log": ""}
    scene.setdefault("positions", {})[participant_id] = {
        "zone_id": zone_id,
        "distance_state": distance_state if distance_state in DISTANCES else "proximo",
        "postura": {"state": postura if postura in POSTURAS else "neutro",
                    "mode": "sustentado", "cause": None},
        "ocultacao": ocultacao if ocultacao in OCULTACOES else "visivel",
        "engaged_with": [],
        "budget": dict(TURN_BUDGET),
        "guarding": False,
        "hidden_from": [],   # observadores que perderam a posição (Escondido relativo, R9)
        "approx_from": [],   # observadores com posição APROXIMADA (atacam com Desvantagem, R10)
    }
    return {"ok": True, "error": None, "log": f"{participant_id} posicionado."}


# --- Distância (R3) ----------------------------------------------------------
def move_distance(scene: dict, participant_id: str, direction: str,
                  via: str = "pre") -> dict:
    """Move 1 estágio de Distância por Pré-Ação OU Pós-Ação (R3). Usar as duas no
    mesmo turno = 2 chamadas = atravessa 2 estágios. `direction`: aproximar|afastar."""
    pos = (scene.get("positions") or {}).get(participant_id)
    if not pos:
        return {"ok": False, "error": f"{participant_id} não está na cena.", "log": ""}
    idx = DISTANCES.index(pos.get("distance_state", "proximo"))
    d = str(direction or "").lower()
    if d in ("aproximar", "approach", "closer", "-"):
        idx = max(0, idx - 1)
    elif d in ("afastar", "away", "farther", "+"):
        idx = min(len(DISTANCES) - 1, idx + 1)
    else:
        return {"ok": False, "error": "Direção inválida (aproximar|afastar).", "log": ""}
    pos["distance_state"] = DISTANCES[idx]
    # R11: mudar de estágio de Distância encerra o Escondido (não é ajuste pequeno).
    _reveal(pos)
    return {"ok": True, "error": None, "distance_state": DISTANCES[idx],
            "via": via, "log": f"{participant_id} -> {DISTANCES[idx]} ({via})"}


# --- Engajamento (relação separada da distância, R2/R6/R7) -------------------
def engage(scene: dict, a: str, b: str, *, via: str = _PRE_OU_POS, spend: bool = True) -> dict:
    """R6: `a` Engaja `b` gastando Pré-Ação OU Pós-Ação. Um personagem pode estar
    Engajado com vários inimigos ao mesmo tempo. `spend=False` só relaciona (uso
    interno/preparação)."""
    pa = _pos(scene, a)
    pb = _pos(scene, b)
    if not pa or not pb:
        return {"ok": False, "error": "Participante ausente da cena.", "log": ""}
    used = None
    if spend:
        used = _spend_budget(pa, via)
        if not used:
            return {"ok": False, "error": f"{a} sem Pré/Pós-Ação para Engajar.", "log": ""}
    if b not in pa["engaged_with"]:
        pa["engaged_with"].append(b)
    if a not in pb["engaged_with"]:
        pb["engaged_with"].append(a)
    return {"ok": True, "error": None, "via": used, "log": f"{a} e {b} engajados."}


def disengage(scene: dict, a: str, b: Optional[str] = None, *, spend: bool = True) -> dict:
    """R7: Desengajar custa a Ação e encerra COM SEGURANÇA os Engajamentos (sem AoO).
    `b=None` desengaja de todos. `spend=False` só desfaz a relação."""
    pa = _pos(scene, a)
    if not pa:
        return {"ok": False, "error": f"{a} não está na cena.", "log": ""}
    if spend and not _spend_budget(pa, "acao"):
        return {"ok": False, "error": f"{a} sem Ação para Desengajar.", "log": ""}
    alvos = [b] if b is not None else list(pa.get("engaged_with", []))
    for target in alvos:
        for x, y in ((a, target), (target, a)):
            p = _pos(scene, x)
            if p and y in p.get("engaged_with", []):
                p["engaged_with"].remove(y)
    return {"ok": True, "error": None, "safe": True, "log": f"{a} desengaja com segurança."}


def is_engaged(scene: dict, a: str, b: str) -> bool:
    p = (scene.get("positions") or {}).get(a) or {}
    return b in p.get("engaged_with", [])


# --- Postura / Ocultação (R4) ------------------------------------------------
def set_postura(scene: dict, participant_id: str, state: str, *,
                mode: str = "sustentado", cause: Optional[str] = None) -> dict:
    """Protegido/Exposto momentâneo (só o próximo ataque) ou sustentado (persiste
    enquanto a causa concreta existir)."""
    pos = (scene.get("positions") or {}).get(participant_id)
    if not pos:
        return {"ok": False, "error": f"{participant_id} não está na cena.", "log": ""}
    if state not in POSTURAS:
        return {"ok": False, "error": f"Postura inválida: {state}.", "log": ""}
    pos["postura"] = {"state": state,
                      "mode": "momentaneo" if mode == "momentaneo" else "sustentado",
                      "cause": cause}
    return {"ok": True, "error": None, "log": f"{participant_id}: {state} ({mode})."}


def consume_postura_on_attack(scene: dict, participant_id: str) -> None:
    """Postura MOMENTÂNEA expira depois do próximo ataque aplicável (R4). A
    sustentada não é tocada aqui (some só quando a causa é removida)."""
    pos = (scene.get("positions") or {}).get(participant_id)
    if not pos:
        return
    postura = pos.get("postura") or {}
    if postura.get("mode") == "momentaneo" and postura.get("state") != "neutro":
        pos["postura"] = {"state": "neutro", "mode": "sustentado", "cause": None}


def clear_sustained_postura(scene: dict, participant_id: str, cause: str) -> None:
    """Remove a Postura sustentada quando a causa concreta (pilastra/corrente/
    cobertura/Guardar) deixa de existir (R4)."""
    pos = (scene.get("positions") or {}).get(participant_id)
    if not pos:
        return
    postura = pos.get("postura") or {}
    if postura.get("mode") == "sustentado" and postura.get("cause") == cause:
        pos["postura"] = {"state": "neutro", "mode": "sustentado", "cause": None}


# --- Objetos interativos (R5/R7) ---------------------------------------------
def add_object(scene: dict, obj: dict, *, from_trigger: bool = False) -> dict:
    """Adiciona objeto à cena. Bloqueado após o congelamento (R8), salvo se vier
    de um gatilho de reforço declarado antes do início."""
    if scene.get("frozen") and not from_trigger:
        return {"ok": False, "error": "Cena congelada: nenhum objeto novo entra.", "log": ""}
    o = dict(obj)
    o.setdefault("secret", False)
    o.setdefault("discovered", False)
    o.setdefault("destroyed", False)
    o.setdefault("interactions", [])
    scene.setdefault("objects", []).append(o)
    return {"ok": True, "error": None, "log": f"Objeto '{o.get('name', o.get('id'))}' na cena."}


def visible_objects(scene: dict) -> List[dict]:
    """Objetos que o jogador ENXERGA: não-destruídos e (não-secretos OU já
    descobertos) (R7). Cada interação expõe só label+cost, nunca o effect (R5)."""
    out = []
    for o in scene.get("objects", []):
        if o.get("destroyed"):
            continue
        if o.get("secret") and not o.get("discovered"):
            continue
        out.append({
            "id": o.get("id"), "name": o.get("name"),
            "distance_state": o.get("distance_state"), "zone_id": o.get("zone_id"),
            "interactions": [{"label": it.get("label"), "cost": it.get("cost")}
                             for it in o.get("interactions", [])],
            "uses_remaining": o.get("uses_remaining"),
        })
    return out


def discover_object(scene: dict, object_id: str) -> dict:
    for o in scene.get("objects", []):
        if o.get("id") == object_id:
            o["discovered"] = True
            return {"ok": True, "error": None, "log": f"'{o.get('name', object_id)}' descoberto."}
    return {"ok": False, "error": f"Objeto '{object_id}' não existe.", "log": ""}


def _find_object(scene: dict, object_id: str) -> Optional[dict]:
    for o in scene.get("objects", []):
        if o.get("id") == object_id:
            return o
    return None


def apply_object_interaction(scene: dict, object_id: str, interaction_label: str,
                             actor_id: str) -> dict:
    """Executa uma interação de objeto: devolve o EffectSpec (validado contra o
    catálogo fechado) e decrementa usos/destrói. NÃO resolve o efeito (conflito-04)."""
    obj = _find_object(scene, object_id)
    if not obj or obj.get("destroyed"):
        return {"ok": False, "error": f"Objeto '{object_id}' indisponível.", "effect": None}
    if obj.get("secret") and not obj.get("discovered"):
        return {"ok": False, "error": "Objeto secreto ainda não descoberto.", "effect": None}
    it = next((i for i in obj.get("interactions", []) if i.get("label") == interaction_label), None)
    if not it:
        return {"ok": False, "error": f"Interação '{interaction_label}' inexistente.", "effect": None}
    effect = it.get("effect") or {}
    if not validate_effect_kind(effect):
        return {"ok": False, "error": f"Efeito fora do catálogo: {effect.get('kind')!r}.", "effect": None}

    left = obj.get("uses_remaining")
    if left is not None:
        if int(left) <= 0:
            return {"ok": False, "error": "Objeto sem usos restantes.", "effect": None}
        obj["uses_remaining"] = int(left) - 1
        if obj["uses_remaining"] <= 0:
            obj["destroyed"] = True
    if effect.get("kind") == "destroy_object":
        obj["destroyed"] = True
    return {"ok": True, "error": None, "effect": effect,
            "log": f"{actor_id} usa '{interaction_label}' em '{obj.get('name', object_id)}'."}


# --- Cena congelada (R8) -----------------------------------------------------
def freeze(scene: dict) -> dict:
    """Congela a cena no início do conflito: nada é acrescentado por interpretação
    livre depois disso (R8)."""
    scene["frozen"] = True
    return scene


def add_reinforcement_trigger(scene: dict, trigger: dict) -> dict:
    """Declara ANTES do início um gatilho de reforço (spawn_reinforcement). Só
    esses podem introduzir participantes/objetos depois do congelamento (R8)."""
    if scene.get("frozen"):
        return {"ok": False, "error": "Gatilhos de reforço só antes de congelar.", "log": ""}
    scene.setdefault("reinforcement_triggers", []).append(dict(trigger))
    return {"ok": True, "error": None, "log": "Gatilho de reforço registrado."}


def fire_reinforcement(scene: dict, trigger_id: str) -> dict:
    """Dispara um gatilho de reforço preparado — a única via de entrada de novos
    elementos numa cena congelada (R8)."""
    trig = next((t for t in scene.get("reinforcement_triggers", [])
                 if t.get("id") == trigger_id), None)
    if not trig:
        return {"ok": False, "error": f"Gatilho '{trigger_id}' não foi preparado.", "effect": None}
    for obj in trig.get("objects", []) or []:
        add_object(scene, obj, from_trigger=True)
    for pid, ppos in (trig.get("participants") or {}).items():
        scene.setdefault("positions", {})[pid] = ppos
    return {"ok": True, "error": None, "log": f"Reforço '{trigger_id}' disparado.",
            "effect": {"kind": "spawn_reinforcement", "params": {"trigger": trigger_id}}}


# --- Guardar (R8) ------------------------------------------------------------
def guard(scene: dict, participant_id: str, *, spend: bool = True) -> dict:
    """R8: Guardar custa a Ação. Postura universal (não depende de escudo). Enquanto
    Guardando, ataques Defensáveis CONTRA o personagem sofrem Desvantagem — e os
    ataques DO próprio personagem também."""
    pos = _pos(scene, participant_id)
    if not pos:
        return {"ok": False, "error": f"{participant_id} não está na cena.", "log": ""}
    if spend and not _spend_budget(pos, "acao"):
        return {"ok": False, "error": f"{participant_id} sem Ação para Guardar.", "log": ""}
    pos["guarding"] = True
    return {"ok": True, "error": None, "log": f"{participant_id} assume a Guarda."}


def stop_guard(scene: dict, participant_id: str) -> dict:
    """Abandona a Guarda livremente antes de agir (perde a proteção). Não devolve Ação."""
    pos = _pos(scene, participant_id)
    if pos is not None:
        pos["guarding"] = False
    return {"ok": True, "error": None, "log": f"{participant_id} abandona a Guarda."}


def is_guarding(scene: dict, participant_id: str) -> bool:
    return bool((_pos(scene, participant_id) or {}).get("guarding"))


def guard_defense_modifier(scene: dict, defender_id: str) -> int:
    """R8: -1 (Desvantagem) para quem ataca um alvo que está Guardando; 0 senão."""
    return -1 if is_guarding(scene, defender_id) else 0


def guard_offense_modifier(scene: dict, attacker_id: str) -> int:
    """R8: -1 (Desvantagem) nos ataques FEITOS por quem está Guardando; 0 senão."""
    return -1 if is_guarding(scene, attacker_id) else 0


# --- Ocultação relativa por observador (R9/R10/R11) --------------------------
def _reveal(pos: dict) -> None:
    """Encerra o Escondido: fica Visível para todos (usado em movimento/pós-ataque)."""
    pos["ocultacao"] = "visivel"
    pos["hidden_from"] = []
    pos["approx_from"] = []
    pos.pop("hide_source", None)


def hide(scene: dict, participant_id: str, *, source: Optional[str] = None,
         observers: Optional[List[str]] = None, spend: bool = True) -> dict:
    """R9: Esconder-se custa a Ação e EXIGE fonte plausível (escuridão, fumaça,
    vegetação, multidão, cobertura, obstáculo). Ocultação é RELATIVA — fica
    Escondido de `observers` (default: todos os outros da cena)."""
    pos = _pos(scene, participant_id)
    if not pos:
        return {"ok": False, "error": f"{participant_id} não está na cena.", "log": ""}
    if not source or not str(source).strip():
        return {"ok": False,
                "error": "Esconder-se exige fonte plausível (escuridão, fumaça, cobertura...).",
                "log": ""}
    if spend and not _spend_budget(pos, "acao"):
        return {"ok": False, "error": f"{participant_id} sem Ação para Esconder-se.", "log": ""}
    obs = list(observers) if observers is not None else [
        o for o in (scene.get("positions") or {}) if o != participant_id]
    pos["ocultacao"] = "escondido"
    pos["hidden_from"] = list(obs)
    pos["approx_from"] = []
    pos["hide_source"] = source
    return {"ok": True, "error": None, "log": f"{participant_id} se esconde ({source})."}


def is_hidden_from(scene: dict, participant_id: str, observer_id: str) -> bool:
    """R9: True se `participant_id` está Escondido do olhar de `observer_id`."""
    return observer_id in ((_pos(scene, participant_id) or {}).get("hidden_from") or [])


def has_approx_position(scene: dict, participant_id: str, observer_id: str) -> bool:
    """R10: True se `observer_id` só conhece a posição APROXIMADA do escondido."""
    return observer_id in ((_pos(scene, participant_id) or {}).get("approx_from") or [])


def search(scene: dict, searcher_id: str, target_id: str, *,
           found: bool = True, spend: bool = True) -> dict:
    """R10: Procurar custa a Ação. Encontrar deixa o alvo Visível SÓ para quem
    procurou (remove-o do Escondido/aproximado daquele observador)."""
    sp = _pos(scene, searcher_id)
    tp = _pos(scene, target_id)
    if not sp or not tp:
        return {"ok": False, "error": "Participante ausente da cena.", "found": False, "log": ""}
    if spend and not _spend_budget(sp, "acao"):
        return {"ok": False, "error": f"{searcher_id} sem Ação para Procurar.", "found": False, "log": ""}
    if not found:
        return {"ok": True, "error": None, "found": False,
                "log": f"{searcher_id} procura, mas não encontra."}
    for key in ("hidden_from", "approx_from"):
        lst = tp.get(key) or []
        if searcher_id in lst:
            lst.remove(searcher_id)
        tp[key] = lst
    if not tp["hidden_from"]:
        tp["ocultacao"] = "visivel"
    return {"ok": True, "error": None, "found": True,
            "log": f"{searcher_id} encontra {target_id}."}


def alert_party(scene: dict, alerter_id: str, target_id: str, party_ids: List[str], *,
                spend: bool = True) -> dict:
    """R10: alertar a party custa Pré/Pós-Ação e PROPAGA a posição APROXIMADA do
    escondido para todos os aliados (podem atacar com Desvantagem — não o revela)."""
    ap = _pos(scene, alerter_id)
    tp = _pos(scene, target_id)
    if not ap or not tp:
        return {"ok": False, "error": "Participante ausente da cena.", "log": ""}
    if spend and not _spend_budget(ap, _PRE_OU_POS):
        return {"ok": False, "error": f"{alerter_id} sem Pré/Pós-Ação para alertar.", "log": ""}
    hidden = set(tp.get("hidden_from") or [])
    approx = set(tp.get("approx_from") or [])
    for pid in party_ids:
        if pid in hidden:            # ainda não o VÊ, mas agora tem a posição aproximada
            approx.add(pid)
    tp["approx_from"] = sorted(approx)
    return {"ok": True, "error": None, "log": f"{alerter_id} alerta a party sobre {target_id}."}


def occlusion_attack_modifier(scene: dict, attacker_id: str, target_id: str) -> dict:
    """R10/R11: combina ocultação num veredito de ataque.
      - atacante Escondido do alvo → ataca OCULTO: Vantagem (+1);
      - alvo Escondido do atacante SEM posição aproximada → não pode mirar direto;
      - alvo Escondido COM posição aproximada → Desvantagem (-1).
    Retorna {"can_target": bool, "advantage": -1|0|1}."""
    adv = 0
    can = True
    if is_hidden_from(scene, attacker_id, target_id):
        adv += 1
    if is_hidden_from(scene, target_id, attacker_id):
        if has_approx_position(scene, target_id, attacker_id):
            adv -= 1
        else:
            can = False
    return {"can_target": can, "advantage": (1 if adv > 0 else (-1 if adv < 0 else 0))}


def reveal_after_attack(scene: dict, participant_id: str) -> None:
    """R11: quem atacou oculto permanece Escondido durante a resolução e vira
    Visível DEPOIS (mesmo errando), salvo Carta específica."""
    pos = _pos(scene, participant_id)
    if pos is not None:
        _reveal(pos)
