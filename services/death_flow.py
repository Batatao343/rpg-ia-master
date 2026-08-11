"""services/death_flow.py — Última Ação, Estado Terminal, Cicatriz e rendição (spec conflito-07).

Fluxo de morte RICO do conflito v2, 100% determinístico (só a Cicatriz é narrada
por LLM, com o guard obrigatório): preencher o último espaço de Ferimento Crítico
dispara Última Ação → Estado Terminal → morte imediata sem aliado capaz, ou até 2
tentativas de estabilização → sobreviver ao fluxo marca Cicatriz obrigatória.
Também: golpe final não-letal, rendição determinística por perfil e as condições
de encerramento do combate.

ADITIVO (como 04/05/06): entrega o motor puro + testes. A reconciliação final com
`services/checkpoints.py` (death_pending/save-restore/UI) e o hook no pipeline de
dano ao vivo acontecem no cutover (conflito-13) — os pontos estão marcados.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from services.conflict_resolution import roll_kept, virtude_value

# --- Categorias de inimigo (R7) — conteúdo real é conflito-15 ----------------
FULL_FLOW_CATEGORIES = frozenset({"elite", "chefe", "nomeado", "companheiro"})
NO_TERMINAL_CATEGORIES = frozenset({"padrao"})
MINION_CATEGORIES = frozenset({"lacaio"})

# Dificuldade da estabilização (2ª tentativa mais difícil, R3).
STABILIZE_DC = 12
STABILIZE_DC_SECOND = 15
MAX_STABILIZE_ATTEMPTS = 2


# ==========================================================================
# Categorias de inimigo (R7)
# ==========================================================================
def _categoria(actor: dict) -> str:
    return str(actor.get("categoria") or "").strip().lower()


def uses_full_death_flow(actor: dict) -> bool:
    """R7: quem usa Última Ação/Estado Terminal. Jogador e Nomeado/companheiro/
    Elite/Chefe SEMPRE; Lacaio e Padrão NÃO (Padrão é derrotado ao preencher o
    último Crítico, sem Estado Terminal salvo regra explícita)."""
    if actor.get("is_player") or actor.get("player"):
        return True
    return _categoria(actor) in FULL_FLOW_CATEGORIES


def minion_defeated_by_wound(actor: dict) -> bool:
    """R7: Lacaio sai do combate com QUALQUER Ferimento (Vitalidade simplificada)."""
    return _categoria(actor) in MINION_CATEGORIES


# ==========================================================================
# Detecção do último Crítico (R1) — hook do pipeline de dano (fiação: conflito-13)
# ==========================================================================
def _wound_spaces(actor: dict) -> Dict[str, int]:
    if actor.get("ferimento_espacos"):
        return actor["ferimento_espacos"]
    import gamedata
    return gamedata.espacos_ferimento_para_corpo((actor.get("virtudes") or {}).get("corpo", 0))


def critical_spaces_full(actor: dict) -> bool:
    """True quando o último espaço de Ferimento Crítico foi preenchido (R1)."""
    fer = actor.get("ferimentos") or {}
    espacos = _wound_spaces(actor)
    return len(fer.get("critico", []) or []) >= int(espacos.get("critico", 0) or 0) > 0


def should_trigger_last_stand(actor: dict) -> bool:
    """Gate do fluxo completo: último Crítico cheio E o ator usa Última Ação (R1/R7).
    Um ator que já morreu/estabilizou não redispara."""
    if (actor.get("dead") or actor.get("estado_terminal")
            or actor.get("last_stand_pending")
            or actor.get("last_stand_resolved")):
        return False
    return uses_full_death_flow(actor) and critical_spaces_full(actor)


# ==========================================================================
# Etapa 1 — Última Ação (R1)
# ==========================================================================
class LastStandResult(BaseModel):
    vantagem_extrema: bool = True
    acao_declarada: Dict = Field(default_factory=dict)
    ruptura_declarada: bool = False
    entra_em_estado_terminal: bool = True
    ignora_recursos: bool = True


def trigger_last_stand(participant: dict, *, acao: Optional[dict] = None,
                       ruptura: bool = False) -> dict:
    """R1: dispara a Última Ação imediatamente (mesmo fora da ordem). Vantagem
    extrema, ignora limitações dos Ferimentos e recursos ausentes; pode declarar
    Ruptura (gera Carga normalmente). Marca o Estado Terminal a seguir (R2)."""
    if participant.get("last_stand_resolved"):
        return LastStandResult(
            acao_declarada=dict(acao or {}),
            ruptura_declarada=False,
        ).model_dump()
    if ruptura and not participant.get("last_stand_pending"):
        participant["abyss_charge"] = int(participant.get("abyss_charge", 0) or 0) + 1
    if not participant.get("last_stand_pending"):
        participant["_last_stand_count"] = int(
            participant.get("_last_stand_count", 0) or 0) + 1
    participant["last_stand_pending"] = True
    return LastStandResult(
        acao_declarada=dict(acao or {}),
        ruptura_declarada=bool(ruptura),
    ).model_dump()


def last_stand_roll(rng=None) -> dict:
    """Vantagem extrema (R1): 3 dados, mantém os 2 melhores (mesma engine da
    Vantagem, mas sempre concedida). Crítico por dupla vale normalmente."""
    return roll_kept(1, rng)


def last_stand_pay(participant: dict, *, entropy: int = 0, vitality: int = 0) -> dict:
    """R1: custo da Última Ação paga o que HOUVER; o déficit é ignorado e — ao
    contrário do sacrifício comum (conflito-05) — NÃO cria Ferimento novo."""
    ent = int(participant.get("entropy", 0) or 0)
    participant["entropy"] = max(0, ent - int(entropy))
    vit = int(participant.get("vitalidade", 0) or 0)
    participant["vitalidade"] = max(0, vit - int(vitality))
    import gamedata
    gamedata.sync_legacy_hp_aliases(participant)
    return {"entropy": participant["entropy"], "vitalidade": participant["vitalidade"],
            "wound_criado": False}


# ==========================================================================
# Etapa 2 — Estado Terminal + morte/estabilização (R2/R3/R4)
# ==========================================================================
def enter_terminal_state(participant: dict) -> dict:
    """R2: entra em Estado Terminal depois da Última Ação. Cura comum NÃO cancela
    (só uma Ruptura de sobrevivência específica)."""
    participant["estado_terminal"] = True
    participant["last_stand_pending"] = False
    participant["last_stand_resolved"] = True
    participant.setdefault("stabilization_attempts", 0)
    return {"estado_terminal": True}


def _revive(target: dict, *, fraction: Optional[float] = None, minimum_one: bool = False,
            auto: bool = False, kit_cargas: int = 0, log: str = "") -> dict:
    maxv = int(target.get("max_vitalidade", 0) or 0)
    if fraction is not None:
        target["vitalidade"] = max(1, int(maxv * fraction))
    elif minimum_one:
        target["vitalidade"] = 1
    target["estado_terminal"] = False
    target["dead"] = False
    target["scar_pending"] = True   # sobreviveu ao fluxo completo → Cicatriz (R6)
    import gamedata
    gamedata.sync_legacy_hp_aliases(target)
    return {"revived": True, "dead": False, "auto": auto, "kit_cargas": kit_cargas,
            "vitalidade": target["vitalidade"],
            "attempts": int(target.get("stabilization_attempts", 0)), "log": log}


def _die(target: dict, cause: str) -> dict:
    target["estado_terminal"] = False
    target["dead"] = True
    target["vitalidade"] = 0
    import gamedata
    gamedata.sync_legacy_hp_aliases(target)
    return {"revived": False, "dead": True, "cause": cause, "vitalidade": 0,
            "attempts": int(target.get("stabilization_attempts", 0))}


def attempt_stabilization(target: dict, helper: Optional[dict] = None, *,
                          has_kit: bool = False, is_medico: bool = False,
                          has_potion: bool = False, rng=None) -> dict:
    """R3/R4: resolve uma tentativa de tirar o alvo do Estado Terminal.

    Caminhos AUTOMÁTICOS (sem rolagem, sem gastar tentativa): Médico com kit
    (metade da Vitalidade máx, 1 carga de kit) e poção adequada (metade da máx).
    Sem aliado capaz → morte imediata. Com aliado: rolagem — kit ou Médico dão
    Vantagem; senão teste normal. Sucesso improvisado volta com 1 Vitalidade,
    adequado (kit) com metade da máx. 2ª tentativa é mais difícil; 2 falhas = morte."""
    if is_medico and has_kit:
        return _revive(target, fraction=0.5, auto=True, kit_cargas=1,
                       log="Médico de Campo com kit: reanimação automática.")
    if has_potion:
        return _revive(target, fraction=0.5, auto=True,
                       log="Poção adequada: reanimação automática.")
    if helper is None:
        return _die(target, "sem aliado próximo e capaz")

    attempt = int(target.get("stabilization_attempts", 0)) + 1
    target["stabilization_attempts"] = attempt
    dc = STABILIZE_DC_SECOND if attempt >= 2 else STABILIZE_DC
    advantage = 1 if (has_kit or is_medico) else 0
    roll = roll_kept(advantage, rng)
    total = sum(roll["kept"]) + virtude_value(helper, "mente")

    if total >= dc:
        if has_kit:
            return _revive(target, fraction=0.5, kit_cargas=1,
                           log=f"Estabilizado (tratamento adequado, {total}≥{dc}).")
        return _revive(target, minimum_one=True,
                       log=f"Estabilizado (tratamento improvisado, {total}≥{dc}).")
    if attempt >= MAX_STABILIZE_ATTEMPTS:
        return _die(target, "duas falhas de estabilização")
    return {"revived": False, "dead": False, "attempts": attempt,
            "dc": dc, "total": total, "log": f"Falha na estabilização ({total}<{dc})."}


# ==========================================================================
# Etapa 3 — Consciência pós-conflito (R5)
# ==========================================================================
def post_combat_consciousness(participant: dict) -> str:
    """R5: 'acordado' (só Leves, acorda em segurança) / 'tratavel' (algum Grave,
    precisa tratamento, pode acordar em descanso curto) / 'inconsciente' (algum
    Crítico, até intervenção adequada)."""
    fer = participant.get("ferimentos") or {}
    if fer.get("critico"):
        return "inconsciente"
    if fer.get("grave"):
        return "tratavel"
    return "acordado"


# ==========================================================================
# Etapa 4 — Cicatriz obrigatória (R6, LLM + guard)
# ==========================================================================
class ScarModel(BaseModel):
    consequencia_negativa: str = Field(description="1 consequência negativa real do trauma")
    habilidade_positiva_relacionada: str = Field(description="1 habilidade positiva ligada ao trauma")
    origem: str = Field(description="local do Ferimento / causa (arma, criatura, contexto)")


def check_scar_required(participant: dict) -> bool:
    """R6: True se o personagem sobreviveu ao fluxo completo e ainda deve receber a
    Cicatriz (não recusável)."""
    return bool(participant.get("scar_pending"))


def _scar_prompt(participant: dict, context: Optional[dict]) -> str:
    ctx = context or {}
    fer = participant.get("ferimentos") or {}
    regioes = [w.get("regiao") for c in ("critico", "grave") for w in fer.get(c, [])]
    return (
        "Gere UMA Cicatriz permanente para um personagem que sobreviveu ao Estado "
        "Terminal em Valoria. Baseie-se no trauma. Toda Cicatriz tem EXATAMENTE 1 "
        "consequência negativa real e 1 habilidade positiva causalmente ligada ao "
        "mesmo trauma.\n"
        f"Classe: {participant.get('class_name', '?')}. "
        f"Regiões feridas: {regioes or ['torso']}. "
        f"Causa: {ctx.get('causa', 'combate brutal')}. "
        f"Relação com o Abismo (Carga): {participant.get('abyss_charge', 0)}."
    )


def _fallback_scar(participant: dict) -> dict:
    fer = participant.get("ferimentos") or {}
    regiao = next((w.get("regiao") for c in ("critico", "grave")
                   for w in fer.get(c, [])), "torso")
    return {
        "id": f"scar_{regiao}_{len(participant.get('scars', []))}",
        "consequencia_negativa": f"Dor crônica no {regiao} em esforço extremo.",
        "habilidade_positiva_relacionada": "Tolerância à dor: resiste 1 vez ao primeiro atordoamento por conflito.",
        "origem": regiao,
    }


def generate_scar(participant: dict, llm, *, context: Optional[dict] = None) -> dict:
    """R6: gera a Cicatriz pós-combate via LLM (structured output) com o GUARD de
    resiliência obrigatório — `FallbackLLM`/erro cai num template determinístico.
    Anexa em `participant['scars']`, limpa `scar_pending`. Jogador não pode recusar."""
    scar: Optional[dict] = None
    try:
        result = llm.with_structured_output(ScarModel).invoke(_scar_prompt(participant, context))
        if isinstance(result, ScarModel):
            fer = participant.get("ferimentos") or {}
            regiao = next((w.get("regiao") for c in ("critico", "grave")
                           for w in fer.get(c, [])), result.origem or "torso")
            scar = {
                "id": f"scar_{regiao}_{len(participant.get('scars', []))}",
                "consequencia_negativa": result.consequencia_negativa,
                "habilidade_positiva_relacionada": result.habilidade_positiva_relacionada,
                "origem": result.origem or regiao,
            }
    except Exception:
        scar = None
    if scar is None:
        scar = _fallback_scar(participant)
    participant.setdefault("scars", []).append(scar)
    participant["scar_pending"] = False
    return scar


# ==========================================================================
# Etapa 6 — Golpe não-letal + rendição + encerramento (R8/R9/R10)
# ==========================================================================
_LETHAL_FORMS = frozenset({"destruicao_total", "queda_fatal"})


def can_be_nonlethal(attack_form: Optional[dict]) -> bool:
    """R8: o golpe final pode ser declarado não-letal, SALVO se a forma do ataque
    for destruição total, queda fatal ou efeito explicitamente letal."""
    form = attack_form or {}
    if form.get("letal_forcado"):
        return False
    return str(form.get("tipo") or "").lower() not in _LETHAL_FORMS


def apply_nonlethal_finish(target: dict) -> dict:
    """R8: alvo fica inconsciente/incapacitado em vez de morrer."""
    target["dead"] = False
    target["conscious"] = False
    target["incapacitated"] = True
    target["estado_terminal"] = False
    return {"dead": False, "incapacitated": True}


# Gatilhos de rendição (R9) — todos determinísticos, sem LLM.
def resolve_surrender(enemy: dict, profile: dict, scene_state: Optional[dict] = None) -> bool:
    """R9: rendição 100% determinística pelo perfil tático. Gatilhos: líder
    derrotado, Vitalidade muito baixa, aliados insuficientes, rota de fuga
    bloqueada + objetivo impossível, medo/lealdade quebrada. Fanático (`nunca_rende`)
    nunca se rende. Marca `enemy['surrendered']`."""
    profile = profile or {}
    scene = scene_state or {}
    if profile.get("nunca_rende"):
        return False

    triggers = False
    if profile.get("rende_com_lider_caido") and scene.get("leader_defeated"):
        triggers = True
    thr = profile.get("rende_abaixo_de_vitalidade")
    if thr is not None:
        maxv = int(enemy.get("max_vitalidade", 0) or 0)
        vit = int(enemy.get("vitalidade", 0) or 0)
        if maxv > 0 and (vit / maxv) <= float(thr):
            triggers = True
    min_allies = profile.get("rende_com_aliados_abaixo_de")
    if min_allies is not None and int(scene.get("allies_remaining", 99)) < int(min_allies):
        triggers = True
    if (profile.get("rende_sem_fuga") and scene.get("escape_blocked")
            and scene.get("objective_impossible")):
        triggers = True
    if profile.get("rende_com_medo") and scene.get("morale_broken"):
        triggers = True

    if triggers:
        enemy["surrendered"] = True
        enemy["conscious"] = enemy.get("conscious", True)
    return triggers


def combat_should_end(sides_state: dict) -> dict:
    """R10: combate termina quando um lado não tem hostis ativos, todos fugiram,
    todos se renderam, o objetivo mecânico foi concluído, ou um gatilho preparado
    encerrou. NUNCA por interpretação livre de 'perderam interesse'. Retorna
    {'ended': bool, 'reason': str}."""
    if sides_state.get("objective_completed"):
        return {"ended": True, "reason": "objetivo mecânico concluído"}
    if sides_state.get("ending_trigger_fired"):
        return {"ended": True, "reason": "gatilho de encerramento preparado"}
    hostiles = sides_state.get("hostiles") or []

    def _inactive(h: dict) -> bool:
        return bool(h.get("dead") or h.get("fled") or h.get("surrendered")
                    or not h.get("conscious", True) or h.get("incapacitated"))

    if hostiles and all(_inactive(h) for h in hostiles):
        if all(h.get("fled") for h in hostiles):
            reason = "todos os hostis fugiram"
        elif all(h.get("surrendered") for h in hostiles):
            reason = "todos se renderam"
        else:
            reason = "nenhum hostil ativo"
        return {"ended": True, "reason": reason}
    return {"ended": False, "reason": ""}
