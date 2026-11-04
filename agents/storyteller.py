"""Narration agent that advances the story and campaign plan."""

import random
import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from agents.npc import generate_new_npc
from agents.world_simulator import simulate_world
from llm_setup import get_llm
from observability.telemetry import log_event as _log_event
from rag import query_rag
from services import discovery as disc
from services import graph_resolver as gr
from services import latency_flags, quest_log
from services import law as _law_mod
from services.context_builder import build_context_pack
from services.lore_query import compose_lore_query
from services.prompt_guard import PLAYER_INPUT_RULE, guard_messages
from services.prompt_layout import compose as compose_prompt
from services.structured_outputs import (
    CrimeClaim,
    ProposedQuest,
    ProposedRumor,
    ProposedRumorWithClaim,
    ProposedWorldEvent,
    coerce_crime_claims,
    coerce_proposed_rumors,
)
from state import GameState
from world_utils import (
    advance_factions,
    apply_rest,
    apply_travel,
    check_encounter,
    clock_label,
    ensure_faction_intel,
    ensure_factions,
    ensure_world,
    find_travel_destination,
    is_rest,
    is_travel_intent,
    resolve_faction_completions,
)


class FactionImpact(BaseModel):
    faction_id: str = Field(
        description="id EXATO de uma fação listada em <FACÇÕES_CONHECIDAS>; vazio se nenhuma."
    )
    direction: Literal["ajudou", "prejudicou"] = Field(
        description="'ajudou' (jogador beneficiou a fação) ou 'prejudicou' (jogador a atrapalhou/traiu/atacou)."
    )
    magnitude: Literal["menor", "maior"] = Field(
        default="menor",
        description="'maior' só para ato decisivo e inequívoco; na dúvida 'menor'.",
    )


def _coerce_faction_impacts(raw: object) -> list:
    """SPEC-298 R10: impacto com direction/magnitude fora do Literal é DESCARTADO
    (nunca derruba a resposta inteira — padrão SPEC-045)."""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if isinstance(item, FactionImpact):
            out.append(item)
            continue
        if not isinstance(item, dict):
            continue
        if item.get("direction") not in ("ajudou", "prejudicou"):
            continue
        magnitude = item.get("magnitude", "menor")
        if magnitude not in ("menor", "maior"):
            magnitude = "menor"
        out.append({**item, "magnitude": magnitude})
    return out


class MembershipAction(BaseModel):
    """SPEC-301 R20: intenção do jogador sobre uma fação. O LLM só PROPÕE; Python decide."""

    action: str = Field(
        default="",
        description="'join' | 'leave' | 'ask_mission'; vazio se o jogador não pediu isso.",
    )
    faction_id: str = Field(default="", description="id EXATO de <FACÇÕES_CONHECIDAS>.")


class StoryUpdate(BaseModel):
    # default "" (não required): Gemini real às vezes omite o campo num schema
    # grande — melhor narrar via fallback do que perder o turno (smoke 2026-07-05)
    narrative: str = Field(
        default="", description="O texto narrativo da resposta. OBRIGATÓRIO: sempre preencha."
    )
    introduced_npcs: list[str] = Field(
        default_factory=list,
        description="Nomes de personagens que ENTRARAM na cena neste turno (novos ou conhecidos que reapareceram).",
    )
    npcs_left_scene: list[str] = Field(
        default_factory=list,
        description="Nomes de personagens JÁ CONHECIDOS que SAÍRAM da cena neste turno (foram embora, morreram, sumiram). Vazio se ninguém saiu.",
    )
    faction_impacts: list[FactionImpact] = Field(
        default_factory=list,
        description=(
            "Fações afetadas pela AÇÃO do jogador NESTE turno. Vazio se a ação não ajuda "
            "nem prejudica claramente uma fação listada. Use o faction_id EXATO."
        ),
    )

    membership_action: MembershipAction | None = Field(
        default=None,
        description=(
            "SOMENTE se o jogador pediu EXPLICITAMENTE, neste turno, para entrar numa fação, "
            "sair dela ou pedir uma missão a ela. Use o faction_id EXATO de "
            "<FACÇÕES_CONHECIDAS>. Na dúvida, deixe vazio. O motor decide se é possível."
        ),
    )

    @field_validator("faction_impacts", mode="before")
    @classmethod
    def _drop_invalid_impacts(cls, v: object) -> list:
        return _coerce_faction_impacts(v)

    crime_claims: list[CrimeClaim] = Field(
        default_factory=list,
        description=(
            "Crimes que a AÇÃO do jogador cometeu NESTE turno (furto, agressao, homicidio, "
            "dano_propriedade, magia_ilegal). Vazio se não houve crime — na dúvida, vazio."
        ),
    )

    @field_validator("crime_claims", mode="before")
    @classmethod
    def _drop_invalid_crimes(cls, v: object) -> list:
        return coerce_crime_claims(v)

    beat_completed: bool = Field(
        default=False,
        description=(
            "True SOMENTE se a ação deste turno cumpriu de forma clara o Objetivo Atual "
            "da cena (o beat ativo). Caso contrário False. Não marque True por progresso vago."
        ),
    )
    proposed_events: list[ProposedWorldEvent] = Field(
        default_factory=list,
        description=(
            "APENAS se a ação deste turno causou mudança PERSISTENTE no mundo "
            "(morte de personagem NOMEADO, segredo revelado, mudança de controle de local). "
            "Use ids EXATOS do bloco <ENTIDADES_CANONICAS>. Deixe vazio na dúvida. "
            "Para CONCLUIR uma quest listada em <QUESTS_ATIVAS>, proponha um evento "
            "type='quest_completed' com target_id=quest_id e payload={'quest_id': quest_id}."
        ),
    )
    proposed_quests: list[ProposedQuest] = Field(
        default_factory=list,
        description=(
            "APENAS se um personagem PRESENTE NA CENA ofereceu uma missão CONCRETA ao "
            "jogador NESTE turno. origin_name = quem pediu; origin_entity_id = id EXATO "
            "do bloco <ENTIDADES_CANONICAS> se houver, senão vazio; location_id só se o "
            "destino for claro. Deixe vazio na dúvida — não invente missões."
        ),
    )
    items_gained: list[str] = Field(
        default_factory=list,
        description=(
            "APENAS se a narrativa deu um item CONCRETO ao jogador NESTE turno "
            "(recebeu, pegou, ganhou). Nome do item conhecido — NÃO invente itens "
            "novos (criação de item é papel do baú/loja). Vazio na dúvida."
        ),
    )


class StoryUpdateWithRumors(StoryUpdate):
    """SPEC-312 P2-1: so com `RPG_RUMORS_PROPOSED=on` o provider ve o campo `proposed_rumors`."""

    proposed_rumors: list[ProposedRumor] = Field(
        default_factory=list,
        description=(
            "APENAS se um personagem PRESENTE NA CENA contou um BOATO neste turno (algo que "
            "ouviu dizer, não um fato). Use ids EXATOS de <ENTIDADES_CANONICAS>. Sem números. "
            "Vazio na dúvida — o motor decide se vale como boato."
        ),
    )

    @field_validator("proposed_rumors", mode="before")
    @classmethod
    def _drop_invalid_rumors(cls, v: object) -> list:
        return coerce_proposed_rumors(v)


class StoryUpdateWithRumorClaims(StoryUpdateWithRumors):
    """SPEC-315 R2: com `RPG_RUMORS_ADOPTED` != off o boato proposto pode levar uma `claim`
    (vocabulario fechado). Mesma chamada: o campo e so um objeto opcional a mais."""

    proposed_rumors: list[ProposedRumorWithClaim] = Field(
        default_factory=list,
        description=StoryUpdateWithRumors.model_fields["proposed_rumors"].description,
    )

    @field_validator("proposed_rumors", mode="before")
    @classmethod
    def _drop_invalid_rumors(cls, v: object) -> list:
        return coerce_proposed_rumors(v, ProposedRumorWithClaim)


_MONEY_CLAIM_RE = re.compile(r"\b(?:ouro|moedas?)\b", re.IGNORECASE)


def encounter_handoff(enc: dict) -> dict:
    """SPEC-203 R3(a): referência canônica one-shot do encontro sistêmico para o
    spawn do combate (o `enemy_id` do bestiário não se perde no handoff)."""
    enc = enc or {}
    out = {
        "enemy_id": str(enc.get("enemy_id") or ""),
        "reason": str(enc.get("reason") or ""),
        "hint": str(enc.get("hint") or ""),
    }
    # SPEC-292: rótulo seguro p/ o jogador só quando difere do canônico (fação oculta)
    public = str(enc.get("public_hint") or "")
    if public and public != out["hint"]:
        out["public_hint"] = public
    if enc.get("aproximacao"):  # SPEC-360 R17: a abertura do combate recebe a aproximação
        out["aproximacao"] = str(enc["aproximacao"])
    return out


def _is_monetary_claim(value: object) -> bool:
    """Dinheiro é economia, nunca um item a resolver pelo nome livre do LLM."""
    return bool(_MONEY_CLAIM_RE.search(str(value or "")))


def _inventory_counts(player: dict) -> Counter:
    counts: Counter = Counter()
    for entry in player.get("inventory") or []:
        if isinstance(entry, dict) and entry.get("id"):
            counts[str(entry["id"])] += int(entry.get("qty", 1) or 1)
    return counts


def _reward_confirmation(before: dict, after: dict) -> str:
    """Linha canônica derivada somente do delta mecânico confirmado."""
    rewards: list[str] = []
    gold_delta = int(after.get("gold", 0) or 0) - int(before.get("gold", 0) or 0)
    if gold_delta > 0:
        rewards.append(f"+{gold_delta} de ouro")
    before_items = _inventory_counts(before)
    after_items = _inventory_counts(after)
    if after_items:
        from inventory import item_display, make_entry

        for item_id, qty in (after_items - before_items).items():
            label = item_display(make_entry(item_id))
            rewards.append(f"{label}" + (f" ×{qty}" if qty > 1 else ""))
    return "Recompensa confirmada: " + ", ".join(rewards) + "." if rewards else ""


def _scene_canonical_entities(state: GameState, factions: list, intel: dict, loc: str) -> str:
    """Ids+nomes canônicos (entities.json) das entidades da cena — o LLM só pode usar estes.

    Fações conhecidas já trazem id canônico; local e NPCs presentes casam por nome com o
    grafo (best-effort). Defensivo: qualquer falha vira lista vazia (o validator é o gate real).
    """
    lines: list[str] = []
    seen = set()
    for f in factions:
        fid = f.get("id")
        if (
            fid
            and intel.get(fid, {}).get("known")
            and not f.get("defeated")
            and fid not in seen
            and gr.get_entity(fid)
        ):
            lines.append(f"- id={fid} · {f.get('name')} · faction")
            seen.add(fid)
    try:
        entities = gr.load_entities()
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "entities_unavailable", exc)
        entities = {}
    names_present = {n.lower() for n in state.get("npcs", {}).keys()}
    loc_l = (loc or "").strip().lower()
    for eid, ent in entities.items():
        if eid in seen:
            continue
        etype, ename = ent.get("type"), ent.get("name", "")
        nl = ename.lower()
        if etype == "location" and loc_l and (nl == loc_l or eid == loc_l):
            lines.append(f"- id={eid} · {ename} · location")
            seen.add(eid)
        elif etype == "npc" and nl in names_present:
            lines.append(f"- id={eid} · {ename} · npc")
            seen.add(eid)
    return "\n".join(lines) or "Nenhuma entidade canônica identificada na cena."


def _quests_ativas_block(quests: list[dict], state: dict | None = None) -> str:
    """Fase 3.3: side quests ativas — o LLM só pode referenciar estes ids em quest_completed.

    SPEC-223 R1: cada linha diz se o ESTADO já prova a conclusão; sem prova o
    motor rejeita a proposta (o narrador não decide que a missão acabou)."""
    ativas = [q for q in (quests or []) if q.get("status") == "active"]
    if not ativas:
        return "Nenhuma missão pendente registrada."

    def _prova(q: dict) -> str:
        if state is None:
            return ""
        ok, _why = quest_log.has_completion_proof(q, state)
        return " · prova: ok" if ok else " · prova: pendente"

    day = int((((state or {}).get("world") or {}).get("world_clock") or {}).get("day", 1) or 1)

    def _mundo(q: dict) -> str:
        # SPEC-305 R22: urgencia como ROTULO vago (nunca numero de dia) para quest de mundo.
        if not q.get("world_kind"):
            return ""
        view = quest_log.public_quest_view(q, day)
        label = view.get("deadline_label", "")
        return " · tipo: mundo" + (f" · prazo: {label}" if label else "")

    return "\n".join(
        f"- id={q.get('id')} · {q.get('title')} · origem: {q.get('origin_name', '?')}"
        f"{_mundo(q)}{_prova(q)}"
        for q in ativas
    )


def _story_schema_for_rumors(rumors_mod) -> type:
    """Schema do narrador: o campo `claim` so existe com a SPEC-315 ligada (R2)."""
    if rumors_mod.proposed_mode() != "on":
        return StoryUpdate
    from services import rumor_adoption

    return StoryUpdateWithRumorClaims if rumor_adoption.mode() != "off" else StoryUpdateWithRumors


def _rumor_proposal_hint() -> str:
    """SPEC-312 R25: so com `RPG_RUMORS_PROPOSED=on` o narrador e convidado a registrar o boato."""
    from services import rumors

    if rumors.proposed_mode() != "on":
        return ""
    return (
        "\n    <BOATOS>\n    Se um personagem PRESENTE NA CENA contar ao jogador, NESTE turno, "
        "um boato (algo que ouviu dizer e não pode confirmar: uma fofoca, um 'dizem que...'), "
        "registre em 'proposed_rumors' (text em 1 frase, sem números; entity_ids com ids EXATOS "
        "de <ENTIDADES_CANONICAS> citados no boato). Só o que foi dito em cena; nunca invente "
        "fatos. Na dúvida, deixe vazio.\n    </BOATOS>"
    ) + _rumor_claim_hint()


def _rumor_claim_hint() -> str:
    """SPEC-315: a LLM pode anexar `claim` (vocabulario fechado); o motor sorteia a verdade."""
    from services import rumor_adoption

    if rumor_adoption.mode() == "off":
        return ""
    return (
        "\n    <BOATOS_ALEGACAO>\n    Se o boato afirma algo CONCRETO sobre um local DISTANTE (não "
        "este), preencha 'claim' com kind em {esconderijo, item_perdido, perigo_na_estrada, "
        "criatura_avistada, npc_em_local}, location_id EXATO do mapa e, só para "
        "criatura_avistada/npc_em_local, o entity_id EXATO. Nunca fale de quantidade, item ou "
        "valor. O motor decide se é verdade; a narração NUNCA confirma o boato.\n    "
        "</BOATOS_ALEGACAO>"
    )


def _gancho_novo_block(created: list[dict]) -> str:
    """SPEC-305 R22: linha com o gancho recem-criado (texto do template + canal) para o
    narrador mostrar COMO o personagem soube. Sem chamada LLM nova; sem prazo exato."""
    rows = [
        f"- (canal: {q['heard_via']['channel']}) {q.get('description', '')}"
        for q in created or []
        if q.get("world_kind") and isinstance(q.get("heard_via"), dict)
    ]
    if not rows:
        return ""
    return (
        "<GANCHO_NOVO>\n"
        + "\n".join(rows)
        + "\nNarre, de forma breve, como o personagem toma conhecimento disso pelo canal "
        "indicado (testemunho, cartaz, alguém contando, rumor). NÃO invente prazo exato, "
        "números de dias nem o desfecho.\n</GANCHO_NOVO>"
    )


def _npc_fallback_clause(state: GameState) -> str:
    """spec npc-fallback-sem-alvo (R2): quando a rota NPC não achou interlocutor,
    o storyteller narra a AUSÊNCIA (sem inventar NPC em cena) e dá um gancho útil
    (onde há gente / o objetivo atual). Pura — testável sem LLM."""
    hint = state.get("npc_fallback_hint")
    if not hint:
        return ""
    from services.social_direction import build_social_direction

    direction = build_social_direction(state)
    return (
        f"\n    - SEM INTERLOCUTOR: o jogador tentou falar com alguém "
        f'("{str(hint)[:120]}"), mas NÃO há ninguém por perto para responder. '
        "Narre a solidão/silêncio SEM inventar um NPC novo em cena, e ofereça "
        f"esta direção ÚTIL e canônica: {direction}"
    )


def _mediated_subject_view(state: GameState) -> dict | None:
    """SPEC-202 R11: recorte PÚBLICO (camada 2) do NPC de quem o narrador fala."""
    subject_id = state.get("mediated_subject_id")
    if not subject_id:
        return None
    from services import interlocutor, npc_layers

    for key, row in (state.get("npcs") or {}).items():
        if isinstance(row, dict) and interlocutor.canonical_npc_id(state, key) == subject_id:
            views = npc_layers.visible_npc_view({key: row})
            if not views:
                return None
            view = dict(views[0])
            # R15(b): pronome só se o registro já tiver o campo (P4: sem dado novo).
            for field in ("pronouns", "pronome", "gender", "genero"):
                if row.get(field):
                    view["pronome"] = str(row[field])
                    break
            return view
    return None


def _mediation_clause(state: GameState) -> str:
    """SPEC-202 R2/R7/R11: o narrador responde SOBRE um NPC ou media vários
    presentes — sem fala em 1ª pessoa de personagem, só dados públicos. Pura."""
    from services import interlocutor

    reason = state.get("interlocutor_reason")
    if reason not in interlocutor.MEDIATION_REASONS:
        return ""
    if reason == "ambiguous_multi_mediated":
        present = (
            ", ".join(
                interlocutor.canonical_npc_name(state, key)
                for key in interlocutor.scene_keys(state)
            )
            or "ninguém"
        )
        return (
            "\n    - VÁRIOS PRESENTES: o jogador falou sem indicar a quem "
            f"({present}). Descreva quem está presente e como cada um reage, "
            "sem eleger um porta-voz que responda em primeira pessoa."
        )
    clause = (
        "\n    - PERGUNTA AO NARRADOR: o jogador se dirigiu a VOCÊ (narrador), "
        "não a um personagem. Responda como narrador, em terceira pessoa, só com "
        "o que o herói pode observar ou já sabe; NENHUM personagem fala em "
        "primeira pessoa e nada oculto é revelado."
    )
    view = _mediated_subject_view(state)
    if view:
        traits = (
            ", ".join(
                t.get("name", "") for t in view.get("revealed_traits") or [] if isinstance(t, dict)
            )
            or "nenhum percebido"
        )
        parts = [
            f"nome={view.get('name', '')}",
            f"papel={view.get('role') or '?'}",
            "presente na cena="
            + ("sim (descreva o que o herói observa nele/nela)" if view.get("in_scene") else "não"),
            f"relação com o herói={view.get('relationship', 5)}/10",
            f"traços já percebidos={traits}",
        ]
        if view.get("pronome"):
            parts.append(f"pronome={view['pronome']}")
        if view.get("last_memory"):
            parts.append(f"última lembrança={str(view['last_memory'])[:160]}")
        clause += " Sujeito (dados públicos): " + "; ".join(parts) + "."
    return clause


def _log_narrative_rejected(kind: str, codes: list[str]) -> None:
    """SPEC-252 R2: `narrative.rejected` (kind item|event|mediation + reason_code fechado), 1 linha
    por (kind, reason_code) com `count`; a contagem por kind tambem vai em `rpg.turn`."""
    from observability.telemetry import count_turn

    for code, n in Counter(codes).items():
        _log_event("narrative", "rejected", level="info", kind=kind, reason_code=code, count=n)
    count_turn(kind, len(codes))


def _guard_mediation_secret(text: str, state: GameState) -> tuple[str, list[str]]:
    """SPEC-202 R11: parágrafo mediado com assinatura de segredo não revelado vira
    descrição observável neutra (determinística) + registro de rejeição."""
    from services import interlocutor
    from services.secret_signatures import find_unrevealed

    if state.get("interlocutor_reason") not in interlocutor.MEDIATION_REASONS:
        return text, []
    hit = find_unrevealed(text, state)
    if not hit:
        return text, []
    view = _mediated_subject_view(state) or {}
    who = view.get("name") or "A cena"
    neutral = (
        f"{who} não deixa transparecer mais do que o óbvio; o que você "
        "consegue observar não basta para afirmar nada além disso."
    )
    rejections: list[str] = []
    paragraphs = str(text).split("\n\n")
    out: list[str] = []
    for paragraph in paragraphs:
        found = find_unrevealed(paragraph, state)
        if found:
            rejections.append(f"mediation_secret:{found[0]}")
            if neutral not in out:
                out.append(neutral)
        else:
            out.append(paragraph)
    if not rejections:  # assinatura atravessando parágrafos: troca o texto todo
        out, rejections = [neutral], [f"mediation_secret:{hit[0]}"]
    return "\n\n".join(out), list(dict.fromkeys(rejections))


_DIGEST_MARK = "[ECOS DO MUNDO] O herói percebeu"


def _digest_player_text(note: str) -> str:
    """SPEC-318 P1-3: a nota inline do digest e instrucao de prompt; o jogador so ve os fatos
    (templates ja percebidos), com o boato como boato."""
    out = []
    for line in str(note).splitlines()[1:]:
        if line.startswith("FATO:"):
            out.append(line[len("FATO:") :].strip())
        elif line.startswith("BOATO:"):
            out.append("Dizem por aí: " + line[len("BOATO:") :].strip())
    return " ".join(t for t in out if t)


def _player_facing_note(note: str) -> str:
    """Converte notas de prompt em texto diegético; não vaza imperativos internos."""
    text = str(note or "").strip()
    if not text:
        return ""
    if text.startswith(_DIGEST_MARK):
        text = _digest_player_text(text)
        if not text:
            return ""
    text = re.sub(r"^O jogador VIAJOU para ", "Após a viagem, você chega a ", text)
    text = re.sub(r"^O jogador ENTROU em ", "Você entra em ", text)
    text = re.sub(
        r"^O jogador ENCONTROU um baú/esconderijo em ([^:]+):\s*",
        r"Entre os vestígios de \1, você encontra um baú/esconderijo: ",
        text,
    )
    text = re.sub(
        r"^Ao explorar ([^,]+), o jogador ENCONTROU:\s*", r"Ao explorar \1, você encontra ", text
    )
    # SPEC-233 R8: notas de descanso viram texto diegético de 2ª pessoa.
    text = re.sub(r"^O jogador DESCANSOU\.\s*", "Você descansa. ", text)
    text = text.replace("O tempo avançou para", "O tempo avança para")
    text = text.replace("e ele recuperou parte das forças", "e você recupera parte das forças")
    text = re.sub(r"^O jogador TENTOU descansar, mas", "Você tenta descansar, mas", text)
    text = text.replace("NÃO permite descanso seguro", "não permite descanso seguro")
    text = text.replace("NADA foi recuperado", "nada foi recuperado")
    text = re.sub(r"\s*Descreva\b[^.]*\.?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*Narre\b[^.]*\.?", "", text, flags=re.IGNORECASE)
    from services import prose_guard

    return prose_guard.sanitize_player_facing(text)


def _dedupe_encounter(enc, world: dict):
    """spec encontros-dedupe (R3) + SPEC-233 R6: não repete o MESMO template de encontro
    2x seguidas no mesmo local — exceto reforços/controle, consequência prometida."""
    if not enc:
        return enc
    if enc.get("reason") in ("reinforcements", "controlled", "rumor", "caca"):
        return enc
    if enc.get("presence_id"):  # SPEC-360: a criatura anunciada veio, não é o mesmo template
        return enc
    if (
        enc.get("hint")
        and enc.get("hint") == world.get("last_encounter_id")
        and world.get("last_encounter_loc") == world.get("current_location_id")
    ):
        return None
    return enc


def _deterministic_story_fallback(notes, light: dict) -> str:
    """Fallback visível e contextual; nunca expõe erro de provider ao jogador."""
    parts = [_player_facing_note(note) for note in notes if str(note or "").strip()]
    parts = [part for part in parts if part]
    if light.get("dark"):
        parts.append(
            "Sem fonte de luz, a escuridão limita sua visão; sons e cheiros "
            "chegam antes das formas."
        )
    elif light.get("label") == "iluminado pela sua luz":
        parts.append(
            "A luz que você carrega abre um círculo trêmulo no breu e revela o espaço imediato."
        )
    return "\n".join(parts) or ("O momento passa em silêncio; o mundo aguarda seu próximo passo.")


def _typed_by_player(name: str, player_inputs) -> bool:
    from services.shared_pool import name_typed_by_player

    return name_typed_by_player(name, player_inputs)


def _pool_enabled() -> bool:
    from services.shared_pool import enabled

    return enabled()


def _cast_match(cast: list | None, name: str):
    """Entrada do elenco oferecido cujo nome (dobrado) bate com o introduzido."""
    if not cast:
        return None
    from services.shared_pool_models import fold_name

    folded = fold_name(name)
    return next((e for e in cast if e.name_fold == folded), None)


def _with_new_npc(
    npcs: dict[str, dict],
    new_name: str,
    loc: str,
    narrative_text: str,
    game_id: str = "",
    home_id: str = "",
    turn: int = 0,
    cast: list | None = None,
    pool_used_out: list | None = None,
    player_inputs: tuple = (),
    state: dict | None = None,
    stub_only: bool = False,
    outcome_out: dict | None = None,
) -> dict[str, dict]:
    """`outcome_out` (SPEC-318) recebe `merged_into=<chave>` quando a ficha resolveu para um NPC
    ja existente, `blocked=<motivo>` quando o NPC nao pode (re)entrar, ou `failed=True`."""
    out = outcome_out if outcome_out is not None else {}
    from services import npc_layers, npc_world
    from services.entity_identity import find_runtime_npc_key

    canonical = find_runtime_npc_key(npcs, new_name)
    if canonical is not None and state is not None:
        # SPEC-304 R8: o narrador nao teleporta NPC ausente/viajando/morto/capturado.
        why = npc_world.reintroduction_block({**state, "npcs": npcs}, canonical, str(home_id or ""))
        if why:
            npc_world.log_reintroduction_blocked(why)
            out["blocked"] = why
            return npcs
    if canonical is not None:
        out["merged_into"] = canonical
        # já conhecido: a cena o trouxe de volta (camada 3).
        # spec encontros-dedupe (exceção narrativa): re-introduzir um NPC conhecido
        # é uma decisão DELIBERADA do narrador/player (com o filtro R1 ele nem
        # aparece no contexto fora do seu local, então não há reuso passivo). Logo,
        # se ele foi trazido para OUTRO local (viajou junto, mandado em missão),
        # RELOCALIZA — o home_location_id passa a ser o local atual.
        new_npcs = dict(npcs)
        if isinstance(new_npcs.get(canonical), dict):
            atual = new_npcs[canonical]
            new_npcs[canonical] = {
                **atual,
                "in_scene": True,
                "last_seen_turn": turn,
                "home_location_id": home_id or atual.get("home_location_id", ""),
            }
        return new_npcs
    if state is not None and npc_world.dead_graph_npc(state, {"name": new_name}):
        npc_world.log_reintroduction_blocked("dead")  # SPEC-304 R8/P3: morto nao volta vivo
        out["blocked"] = "dead"
        return npcs
    tpl = None
    pool_entry = _cast_match(cast, new_name)
    if pool_entry is not None:
        # SPEC-297 R23: elenco do pool = cópia da base, SEM chamada de LLM.
        from observability.telemetry import log_event
        from services import shared_pool

        tpl = shared_pool.materialize_npc(pool_entry, game_id=game_id, home_location_id=home_id)
        if pool_used_out is not None:
            pool_used_out.append(pool_entry.entry_id)
        log_event("pool", "cast_used", entry_id=pool_entry.entry_id)
    elif stub_only:
        # SPEC-318 R1: ficha provisoria deterministica (sem LLM/RAG); o no `enrich` completa.
        tpl = stub_npc_template(new_name, narrative_text)
    elif _pool_enabled():
        # R7: com o pool ligado a cena narrada NÃO entra no prompt de geração.
        tpl = generate_new_npc(
            new_name,
            context=f"Local: {loc}",
            game_id=game_id,
            location_id=home_id,
            # P1-3: nome que o jogador digitou e o narrador devolveu continua "player".
            name_origin=("player" if _typed_by_player(new_name, player_inputs) else "narrator"),
            turn=turn,
            player_inputs=player_inputs,
        )
    else:
        tpl = generate_new_npc(new_name, context=f"Local: {loc}. Cena: {narrative_text}")
    if not tpl:
        out["failed"] = True
        return npcs
    if state is not None and npc_world.dead_graph_npc(state, tpl):
        npc_world.log_reintroduction_blocked("dead")
        out["blocked"] = "dead"
        return npcs
    # O librarian/cache pode resolver uma referência técnica para uma ficha já
    # presente (ex.: npc_skriit_mil_olhos -> Skriit Mil-olhos). Revalida APÓS
    # a fábrica para não inserir o mesmo id sob uma segunda chave.
    canonical = find_runtime_npc_key(npcs, new_name, tpl)
    if canonical is not None:
        out["merged_into"] = canonical
        new_npcs = dict(npcs)
        atual = dict(new_npcs[canonical])
        new_npcs[canonical] = {
            **atual,
            "in_scene": True,
            "last_seen_turn": turn,
            "home_location_id": home_id or atual.get("home_location_id", ""),
        }
        return new_npcs
    new_npcs = dict(npcs)
    # A fábrica já devolve a ficha v4 materializada. Ela é a fonte da verdade:
    # recompor aqui apenas os campos antigos apagava Virtudes, Vitalidade,
    # Ferimentos e o perfil tático persistido.
    novo = dict(tpl)
    novo.setdefault("name", new_name)
    novo.setdefault("role", "Desconhecido")
    novo.setdefault("persona", "")
    novo["location"] = loc
    # SPEC-298 R8: a relação inicial é Python (raça/origem/fama/fação, faixa 2..8); o
    # `initial_relationship` que o LLM pôs na ficha é ignorado (vinha fora de 0..10).
    if novo.get("relationship_basis") is None:
        from services import reputation

        novo.setdefault("home_location_id", home_id)
        rel0, basis = reputation.initial_relationship(state or {}, novo)
        novo["relationship"] = rel0
        novo["relationship_basis"] = basis
    novo["relationship"] = max(0, min(10, int(novo.get("relationship", 5) or 0)))
    novo.setdefault("memory", [])
    novo.setdefault("last_interaction", "")
    novo.setdefault("attributes", {})
    novo.setdefault("combat_stats", {})
    # spec encontros-dedupe (R1/R2): vínculo de local + turnos p/ cooldown/invariante.
    novo.setdefault("created_turn", turn)
    novo["last_seen_turn"] = turn
    # spec npcs-3-camadas: quem a cena introduziu está EM cena e é conhecido.
    novo = npc_layers.ensure_npc_fields(novo, game_id, home_location_id=home_id, in_scene=True)
    if tpl.get("sheet_status") == "stub":
        novo["sheet_status"] = "stub"
    new_npcs[str(novo.get("name") or new_name)] = novo
    return new_npcs


# palavra inteira (regex) -> papel. So vale ADJACENTE ao nome (aposto), nunca solta na frase.
_ROLE_HINTS = (
    (r"estalajadeir[oa]", "Estalajadeiro"),
    (r"taverneir[oa]", "Taverneiro"),
    (r"mercador(?:a)?", "Mercador"),
    (r"comerciante", "Comerciante"),
    (r"ferreir[oa]", "Ferreiro"),
    (r"sacerdot(?:e|isa)", "Sacerdote"),
    (r"curandeir[oa]", "Curandeiro"),
    (r"guarda", "Guarda"),
    (r"soldad[oa]", "Soldado"),
    (r"capit[ãa]o|capit[ãa]", "Capitão"),
    (r"ca[çc]ador(?:a)?", "Caçador"),
    (r"bardo", "Bardo"),
    (r"escriba", "Escriba"),
    (r"monge|monja", "Monge"),
    (r"viajante", "Viajante"),
    (r"mendig[oa]", "Mendigo"),
    (r"ladr[ãa]o|ladra", "Ladrão"),
    (r"barqueir[oa]", "Barqueiro"),
)


def _infer_role(name: str, text: str) -> str:
    """Papel so quando o texto JA narrado o liga ao nome por aposto ('o guarda Marta',
    'Marta, a estalajadeira'); palavra solta na frase ou subpalavra ('aguarda', 'capital',
    'ladrilhos') nao conta. Na duvida `Desconhecido` e a ficha completa decide."""
    clean = str(name or "").strip()
    if not clean:
        return "Desconhecido"
    n = re.escape(clean)
    art = r"(?:(?:o|a|um|uma)\s+)?"
    low = str(text or "")
    for pattern, role in _ROLE_HINTS:
        before = rf"(?<![\w]){art}(?:{pattern})\s+{n}(?!\w)"
        after = rf"(?<!\w){n}\s*,\s*(?:(?:é|era)\s+)?(?:o|a|um|uma)\s+(?:{pattern})(?!\w)"
        if re.search(before, low, flags=re.IGNORECASE) or re.search(
            after, low, flags=re.IGNORECASE
        ):
            return role
    return "Desconhecido"


def stub_npc_template(name: str, narrative_text: str) -> dict:
    """SPEC-318 R1: nome + papel inferido do TEXTO JA NARRADO + persona neutra. Nada que o
    jogador nao tenha visto (regra de ouro): traits ocultos vem do seed no `ensure_npc_fields`."""
    from agents.npc import _materialize_npc_combat_sheet
    from services.prompt_guard import sanitize_entity_name

    clean = sanitize_entity_name(name) or "Desconhecido"
    return _materialize_npc_combat_sheet(
        {
            "name": clean,
            "id": f"npc_{clean.lower().replace(' ', '_')}",
            "role": _infer_role(clean, narrative_text),
            "persona": "Pouco se sabe ainda sobre esta pessoa; reaja ao que a cena já mostrou.",
            "attributes": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "sheet_status": "stub",
        }
    )


def _cal_of(state: dict) -> dict | None:
    """SPEC-307 R13: calendário congelado de `world_sim` p/ o rótulo de data do narrador."""
    cal = (state.get("world_sim") or {}).get("calendar")
    return cal if isinstance(cal, dict) else None


def _season_line(world: dict) -> str:
    """SPEC-303 R21: linha 'Estação: <rótulo regional>' (vazia sem calendário)."""
    from services import world_calendar
    from services import world_pressures as _wp

    sid = world_calendar.active_season(world)
    if not sid:
        return ""
    region = _wp.region_of(str(world.get("current_location_id") or ""))
    return f" Estação: {world_calendar.label_for(sid, region)}."


def _engine_owns_factions() -> bool:
    """SPEC-302 R21b: no modo `on` o progresso das facções roda no tick diário."""
    from services import world_engine

    return world_engine.mode() == "on"


def _perception_state(state, world: dict, factions: list, intel: dict) -> dict:
    return {**state, "world": world, "factions": factions, "faction_intel": intel}


def _perceive_world(state, world: dict, factions: list, intel: dict, tick):
    """SPEC-302 R23/R25: filtra o digest pelo que o herói viu/ouviu, grava o TEXTO DO
    TEMPLATE em `world.news` e devolve (world, itens percebidos). Só no modo `on`."""
    if tick.sim_key != "world_sim" or not tick.days_ticked or tick.world_sim is None:
        return world, []
    try:
        from services import world_perception as wperc

        sim = tick.world_sim
        pst = _perception_state(state, world, factions, intel)
        items = list(sim.get("pending_digest") or [])
        seen = wperc.perceivable(pst, items)
        from services import rumors as _rumors

        day = int((world.get("world_clock") or {}).get("day", 1) or 1)
        seen = _rumors.limit_perceived(pst, sim, seen, day)  # SPEC-312 R13
        world = wperc.record_news(world, pst, seen)
        _rids = [str(i.get("subject_id") or "") for i in seen if _rumors.is_rumor_item(i)]
        if _rids:  # SPEC-312 R14: so o que o jogador percebeu marca a instancia
            _rumors.mark_perceived(sim, _rids, day)
            from observability.telemetry import log_event

            for _ in _rids:
                log_event("rumor", "perceived", level="info", channel="digest")
        world = _rumors.prune_news(world, day)
        done = {i["item_id"] for i in seen}
        stats = dict(sim.get("perceived_stats") or {})
        stats["items"] = int(stats.get("items", 0)) + len(seen)
        stats["signals"] = int(stats.get("signals", 0)) + sum(
            1 for i in seen if i["kind"] == "sinal"
        )
        stats["crises"] = int(stats.get("crises", 0)) + sum(1 for i in seen if i["kind"] == "crise")
        stats["festas"] = int(stats.get("festas", 0)) + sum(1 for i in seen if i["kind"] == "festa")
        sim["perceived_stats"] = stats
        # SPEC-305 R6: livro-razao do que o jogador percebeu (prova de `heard_via`).
        ledger = list(sim.get("perceived_ids") or [])
        # SPEC-312 (S6): o rumor percebido fica em `rumors[].perceived_day`, nao no livro-razao
        ledger += [
            str(i.get("subject_id") or i["item_id"]) for i in seen if not _rumors.is_rumor_item(i)
        ]
        for i in seen:  # SPEC-308 R2: tambem os GameEvents que originaram o item
            ledger += [str(e) for e in i.get("event_ids") or [] if e]
        sim["perceived_ids"] = ledger[-400:]
        # so rumores (com subject_id) esperam propagacao; o resto e testemunho do dia
        sim["pending_digest"] = [
            i
            for i in items
            if i["item_id"] not in done
            and i.get("subject_id")
            and day - int(i.get("day", day)) <= 10
        ]
        return world, seen
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "world_perception_failed", exc)
        return world, []


def _npc_beliefs_update(state, world: dict, sim_updates: dict, perceived: list) -> list:
    """SPEC-304 R22: o que o jogador percebeu vira crença (`npc_beliefs`); a morte percebida
    gera `npc_fate_learned` (cronica). Nunca levanta. Devolve eventos para a fila."""
    try:
        from services import npc_world

        if npc_world.mode() != "on":
            return []
        beliefs, learned = npc_world.on_perceived(
            {**state, **sim_updates, "world": world}, perceived
        )
        if beliefs != (state.get("npc_beliefs") or {}):
            sim_updates["npc_beliefs"] = beliefs
        return learned
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "npc_beliefs_failed", exc)
        return []


def _apply_proposed_rumors(state, updates: dict, update, turn: int, quarantined: bool) -> None:
    """SPEC-312 R25-R27: boato que alguem em cena contou. Validado em Python; aceito vira
    rumor `narrador` (falso, sem quest). Guard de FallbackLLM: `update` sem o campo e no-op.
    Nunca levanta."""
    try:
        from services import rumors

        if rumors.proposed_mode() != "on":
            return
        proposals = getattr(update, "proposed_rumors", None) or []
        from observability.telemetry import log_event

        # mede se o narrador propoe (0 propostas != 100% rejeitadas): 1 linha por turno com a flag on
        log_event("rumor", "proposed_seen", level="info", count=len(proposals))
        if not proposals:
            return
        sim_key = "world_sim"
        world = updates.get("world") or state.get("world") or {}
        day = int((world.get("world_clock") or {}).get("day", 1) or 1)
        # `updates["messages"]` e a narracao: o historico do JOGADOR (anti-direcao R8) fica
        pst = {**state, **updates, "world": world, "messages": state.get("messages") or []}
        extra: dict = {}  # SPEC-315: devolve `npc_sim` se a verdade agenda a visita de um NPC
        new_sim, new_world, _why = rumors.accept_proposed(
            pst, proposals, turn=turn, day=day, quarantined=quarantined, extra=extra
        )
        if new_sim is not None and new_world is not None:
            updates[sim_key] = new_sim
            updates["world"] = new_world
            if extra.get("npc_sim") is not None:
                updates[str(extra.get("npc_sim_key") or "npc_sim")] = extra["npc_sim"]
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "proposed_rumor_failed", exc)


def _same_region_travel(state: dict, world: dict) -> bool:
    from agents.campaign_manager import _same_region

    before = str((state.get("world") or {}).get("current_location") or "")
    after = str((world or {}).get("current_location") or "")
    return bool(before and after) and _same_region(before, after)


def _narrate_world(state, world: dict, factions: list, intel: dict, perceived: list) -> str:
    """SPEC-302 R26: no máximo 1 chamada por ação; só com itens percebidos."""
    if not perceived:
        return ""
    if latency_flags.day_digest_inline():
        # SPEC-318 R3: sem chamada FAST; os fatos PERCEBIDOS (templates) vao ao prompt do
        # narrador, que os tece na propria narracao. Marcos/perceived_ids seguem deterministicos.
        from agents.world_simulator import digest_prompt_lines

        lines = digest_prompt_lines(_perception_state(state, world, factions, intel), perceived)
        if not lines:
            return ""
        return (
            "[ECOS DO MUNDO] O herói percebeu, enquanto o tempo passava: teça estes fatos na "
            "narração em 1 a 3 frases, sem listá-los nem acrescentar nomes, números ou "
            "causas (BOATO só como boato: dizem, contam).\n" + "\n".join(lines)
        )
    from agents.world_simulator import narrate_day

    text = narrate_day(_perception_state(state, world, factions, intel), perceived)
    return f"[ECOS DO MUNDO] {text}" if text else ""


def _world_tick(state, world_before: dict, world: dict, factions: list, intel: dict):
    """SPEC-302 R1: 1 tick por dia virado após viagem/descanso. Nunca levanta: falha do
    motor não derruba o turno (devolve o mundo/facções como estavam e tick=None)."""
    try:
        from services import world_engine

        tick = world_engine.advance_days(state, world_before, world, factions, intel)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "world_tick_failed", exc)
        return world, factions, None
    new_world = tick.world
    if tick.sim_key == "world_sim":
        # SPEC-302 (revisão P2-1): o decaimento de perigo (SPEC-233 R2) nao depende do pulso.
        from world_utils import decay_danger_overrides

        new_world = decay_danger_overrides(dict(new_world))
    return new_world, tick.factions, tick


def _world_quests_tick(state, world: dict, factions: list, intel: dict, tick, perceived: list):
    """SPEC-305 R7/R16: depois do tick e da percepcao, vence/falha prazos e oferece quests
    de mundo do que o jogador percebeu. Devolve `(quests, eventos_do_motor, criadas)`.
    Nunca levanta: falha daqui nao derruba o turno."""
    quests = list(state.get("quests") or [])
    try:
        from services import world_quests as wq

        if (
            wq.mode() == "off"
            or tick is None
            or tick.sim_key != "world_sim"
            or not tick.days_ticked
            or tick.world_sim is None
        ):
            return quests, [], []
        day = int(((world or {}).get("world_clock") or {}).get("day", 1) or 1)
        qstate = {
            **_perception_state(state, world, factions, intel),
            "world_sim": tick.world_sim,
            "world_projection": wq.projection_after(state, tick.pending_events, day),
            "quests": quests,
        }
        quests, fail_events = wq.sync_deadlines(qstate, day, perceived=perceived)
        qstate["quests"] = quests
        quests, created = wq.offer_from_perceived(qstate, perceived, day)
        return quests, fail_events, created
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "world_quests_failed", exc)
        return list(state.get("quests") or []), [], []


def _world_quest_completions(state, world: dict, quests: list) -> list:
    """SPEC-305 R12: conclusoes que o proprio motor prova (resgate, objeto recuperado)."""
    if not any(q.get("world_kind") for q in quests or []):
        return []
    try:
        from services import world_quests as wq

        return wq.engine_completions({**state, "world": world, "quests": quests})
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "world_quest_completions_failed", exc)
        return []


def _rumor_cache_trigger(state, world: dict, sim_updates: dict, text: str, quests: list):
    """SPEC-315 R14/R15: boato VERDADEIRO de achado materializa uma vez, no alvo, com busca ou
    quest. Devolve `(player | None, nota)`; commit no `world_sim` via `sim_updates`. Nunca levanta."""
    try:
        from services import rumor_adoption as ra

        if ra.mode() != "on":
            return None, "", []
        day = int(((world or {}).get("world_clock") or {}).get("day", 1) or 1)
        here = str((world or {}).get("current_location_id") or "")
        view = {**state, **sim_updates, "world": world, "quests": quests}
        inst = (
            ra.due_materialization(view, "search", here, day, text)
            or ra.due_materialization(view, "quest", here, day)
            or ra.due_materialization(view, "present", here, day)  # NPC chegou depois do heroi
        )
        if inst is None:
            return None, "", []
        upd, marked = ra.materialize(view, inst, day)
        sim = sim_updates.get("world_sim") or state.get("world_sim") or {}
        sim_updates["world_sim"] = ra.commit(
            sim, str(inst["rumor_id"]), day, marked["materialization"]
        )
        if not upd:  # npc_em_local: so marca; nada a conceder
            return None, "", []
        world["looted_locations"] = list(upd["world"].get("looted_locations") or [])
        return upd["player"], str(upd.get("note") or ""), list(upd.get("events") or [])
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "rumor_cache_failed", exc)
        return None, "", []


_FIND_VERB_RE = re.compile(r"\b(encontr|ach[aeo]|descobr|revel|surg|aparec|desenterr)", re.I)
_CACHE_NOUN_RE = re.compile(
    r"(esconderij|ba[úu]|tesouro|al[çc]ap|cofre|compartiment|esconde |escondid|moedas|ouro\b|"
    r"fundo falso|fresta)",
    re.I,
)
NOTHING_FOUND_FACT = (
    "<RESULTADO_DA_BUSCA>: nada do que o boato prometia está aqui; há só os sinais comuns do "
    "lugar. NÃO narre esconderijo, baú, tesouro, alçapão nem qualquer achado escondido."
    "</RESULTADO_DA_BUSCA>"
)
NOTHING_FOUND_PROSE = "A busca não revela nada além dos sinais comuns do lugar."


def _neutralize_false_find(text: str) -> str:
    """SPEC-315 §6.2: a busca no alvo de um boato falso (ou ainda nao devido) nunca vira achado
    na prosa: frase que afirma esconderijo/tesouro encontrado e trocada pelo fato do motor."""
    parts = re.split(r"(?<=[.!?…])\s+", str(text or "").strip())
    out: list[str] = []
    changed = False
    for sent in parts:
        if _FIND_VERB_RE.search(sent) and _CACHE_NOUN_RE.search(sent):
            changed = True
            if NOTHING_FOUND_PROSE not in out:
                out.append(NOTHING_FOUND_PROSE)
        else:
            out.append(sent)
    return " ".join(out) if changed else str(text or "")


def _rumor_arrival(state, world: dict, sim_updates: dict, level: int, turn: int):
    """SPEC-315 R14/R16: ao VIAJAR ao alvo, boato verdadeiro de encontro vira `rumor_hint`;
    o de NPC agendado so e marcado (o NPC ja viajou de verdade, R17). Devolve
    `(hint | None, rumor_id)`. Nunca levanta."""
    try:
        from services import rumor_adoption as ra

        if ra.mode() != "on":
            return None, ""
        day = int(((world or {}).get("world_clock") or {}).get("day", 1) or 1)
        here = str((world or {}).get("current_location_id") or "")
        view = {**state, **sim_updates, "world": world}
        inst = ra.due_materialization(view, "travel", here, day)
        if inst is None:
            return None, ""
        kind = str((inst.get("claim") or {}).get("kind") or "")
        if kind == "npc_em_local":
            sim = sim_updates.get("world_sim") or state.get("world_sim") or {}
            _upd, marked = ra.materialize(view, inst, day)
            sim_updates["world_sim"] = ra.commit(
                sim, str(inst["rumor_id"]), day, marked["materialization"]
            )
            return None, ""
        return ra.encounter_hint(view, inst, world, level, turn), str(inst["rumor_id"])
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "rumor_arrival_failed", exc)
        return None, ""


@dataclass
class _StoryTurn:
    """Estado mutavel de um turno do storyteller (SPEC-382): o que antes eram locais compartilhados
    entre as fases de `storyteller_node`. Mesmas referencias, nunca copias (identidade de turn_bl)."""

    _aberturas: Any = None
    _cast: Any = None
    _fauna_day: Any = None
    _fauna_hunt: Any = None
    _fauna_sign_shown: Any = None
    _law_scene_updates: Any = None
    _ll: Any = None
    _open_salt: Any = None
    _pool_used_new: Any = None
    _replan_cause: Any = None
    active_step: Any = None
    ambiente_block: Any = None
    base_p: Any = None
    beat_done: Any = None
    beat_eligible: Any = None
    beats: Any = None
    campaign_plan: Any = None
    capacidades_block: Any = None
    cast_block_text: Any = None
    closed_pass: Any = None
    companion_ack: Any = None
    companion_block: Any = None
    companion_narrated: Any = None
    current_step: Any = None
    danger: Any = None
    dest: Any = None
    det: Any = None
    discovered_routes: Any = None
    discovery_events: Any = None
    discovery_player: Any = None
    enc: Any = None
    entidades_canonicas: Any = None
    eventos_turno: Any = None
    existing_npcs: Any = None
    extra_engine_events: Any = None
    extra_engine_events_tick: Any = None
    faccoes_conhecidas: Any = None
    faction_events: Any = None
    faction_member_block: Any = None
    faction_note: Any = None
    factions: Any = None
    fame_block: Any = None
    fm_events: Any = None
    fm_extra: Any = None
    fm_post_notes: Any = None
    game_id: Any = None
    gancho_novo: Any = None
    hero_state_block: Any = None
    intel: Any = None
    invalid_story_events: Any = None
    kind: Any = None
    last_user_input: Any = None
    law_resolved: Any = None
    law_updates: Any = None
    lei_block: Any = None
    level_up_events: Any = None
    leveled_player: Any = None
    llm: Any = None
    loc: Any = None
    lore_context: Any = None
    mediation_rejections: Any = None
    memoria_recente: Any = None
    messages: Any = None
    mundo_percebido_block: Any = None
    narrative_text: Any = None
    needs_replan: Any = None
    new_npcs: Any = None
    npc_fallback_clause: Any = None
    opcoes_clause: Any = None
    ouviu_block: Any = None
    pack: Any = None
    pending_llm_events: Any = None
    perceived_items: Any = None
    quarantine_llm_payload: Any = None
    quests_ativas: Any = None
    rep_events: Any = None
    rest_note: Any = None
    rested_player: Any = None
    reward_player_before: Any = None
    rumor_find: Any = None
    rumor_nothing: Any = None
    scene_npcs: Any = None
    scene_state: Any = None
    season_line: Any = None
    sim_updates: Any = None
    state: Any = None
    sys: Any = None
    track_bk: Any = None
    travel_needs_replan: Any = None
    travel_note: Any = None
    travel_periods: Any = None
    turn: Any = None
    turn_bl: Any = None
    turn_bl_pre_llm: Any = None
    update: Any = None
    updated_plan: Any = None
    updates: Any = None
    varie_clause: Any = None
    weather_note: Any = None
    world: Any = None
    world_note: Any = None
    world_tick: Any = None
    wq_changed: Any = None
    wq_created: Any = None
    wq_events: Any = None
    wq_quests: Any = None


def _fm_view(t: _StoryTurn) -> dict:
    return {
        **t.state,
        "world": t.world,
        "factions": t.factions,
        "faction_intel": t.intel,
        **t.fm_extra,
    }


def _fm_apply(t: _StoryTurn, result) -> str:
    upd, evs, note = result
    t.fm_events.extend(evs)
    for key, value in upd.items():
        if key == "factions":
            t.factions = value
        elif key == "faction_intel":
            t.intel = value
            t.fm_extra[key] = value
        elif key != "player":  # o storyteller não aplica custo de rito (event_processor)
            t.fm_extra[key] = value
    return note


def storyteller_node(state: GameState):
    t = _StoryTurn(state=state)
    t.messages = t.state.get("messages", [])
    if not t.messages:
        return {"messages": [AIMessage(content="Comece a história.")]}

    t.last_user_input = t.messages[-1].content if isinstance(t.messages[-1], HumanMessage) else ""
    from services.actor_lifecycle import is_recovery_turn

    recovery_turn = is_recovery_turn(t.state)
    if recovery_turn:
        # Recovery is passage of time/treatment, never permission for another action.
        t.last_user_input = "Descanso e aguardo socorro."
    t.world = ensure_world(t.state.get("world", {}))

    # --- Fase 0: viagem / descanso (determinístico) ---
    # --- Fase 2: o tempo que passa avança as fações off-screen (mundo vivo) ---
    t.travel_note = t.rest_note = t.faction_note = ""
    t.rested_player = None
    # SPEC-226 R10: ganhos individuais do turno (guard narrativo aceita o bruto).
    from services.turn_outcome import record_gain

    t.turn_bl = t.state.get("turn_baseline")
    t.factions = ensure_factions(t.state.get("factions"))
    t.intel = ensure_faction_intel(t.state.get("faction_intel"))
    # SPEC-299 P1-1: turno já resolvido pelo gate da lei (fuga/pena/multa): sem viagem/descanso.
    t.law_resolved = bool(t.state.get("law_gate_consumed"))
    travel_intent = bool(
        t.last_user_input
        and not t.law_resolved
        and is_travel_intent(str(t.last_user_input), t.world)
    )
    t.dest = find_travel_destination(t.world, t.last_user_input) if travel_intent else None
    if travel_intent and not t.dest:
        try:
            from world_utils import invalid_travel_message

            refusal = invalid_travel_message(t.world, str(t.last_user_input))
        except (ImportError, AttributeError):
            refusal = ""
        if refusal:
            from services.intent_guard import log_intent_guard

            log_intent_guard("travel_refused", "no_route", str(t.last_user_input))
            # Recusa canônica antes da LLM: destino impossível nunca aparece como
            # chegada na mensagem, no resumo nem na memória.
            return {
                "messages": [AIMessage(content=refusal)],
                "world": t.world,
                "archive_due": False,
            }
    t.travel_periods = 0
    t.closed_pass = False
    t.discovered_routes: list[str] = []
    world_before = t.world  # SPEC-302: relogio ANTES de viagem/descanso (dias virados)
    t.world_tick = None
    t.sim_updates: dict = {}
    t.faction_events: list = []
    t.discovery_events: list = []
    t.reward_player_before = deepcopy(t.state.get("player") or {})

    # SPEC-301: vínculo do jogador com fações (dono: services.faction_membership). O motor
    # decide; `fm_extra` leva os updates parciais e `fm_events` as propostas source=engine.
    from services import faction_membership as fm

    t.fm_events: list = []
    t.fm_post_notes: list = []
    t.fm_extra: dict = {}

    t.discovery_player = None
    if t.dest:
        from world_utils import travel_cost

        t.travel_periods = travel_cost(t.world, t.dest)  # custo ANTES de mover (usa origem)
        from services import world_calendar

        t.closed_pass = world_calendar.pass_closed(
            t.world, str(t.world.get("current_location_id") or ""), str(t.dest.get("id") or "")
        )  # SPEC-303 R11: passo fechado pela neve (travessia cara, nunca recusa)
        # spec loot-exploracao (R1): fog of war checado ANTES de apply_travel (que
        # carimba `visited`). Baú curado (R3) pode reconceder-se? Não — one-shot.
        first_visit = t.dest["id"] not in (t.world.get("visited") or [])
        try:  # SPEC-309 F2: rota bloqueada por evento nao percebido = descoberta ao tentar
            from services import world_perception as _wperc

            t.discovered_routes = _wperc.hidden_blocked_route_events(
                t.state, str(t.world.get("current_location_id") or ""), str(t.dest.get("id") or "")
            )
        except Exception as exc:
            from observability.telemetry import log_fallback

            log_fallback("storyteller", "route_discovery_failed", exc)
        t.world = apply_travel(t.world, t.dest)
        t.world, t.factions, t.world_tick = _world_tick(
            t.state, world_before, t.world, t.factions, t.intel
        )
        if not _engine_owns_factions():
            t.factions, t.faction_events = advance_factions(t.factions, t.travel_periods)
            t.factions, t.world, t.faction_note = resolve_faction_completions(
                t.factions, t.world, t.faction_events, t.intel
            )
        # spec loot-exploracao: achado ambiental (1ª visita) OU baú curado (sempre
        # que houver e não saqueado). Muta player.inventory/gold + world in-place
        # (propaga: viagem sem descanso não substitui o player no updates parcial).
        _pl = deepcopy(t.state.get("player"))
        if isinstance(_pl, dict) and (first_visit or (t.dest.get("treasure"))):
            from services import exploration

            _rng = exploration.arrival_rng(
                str(t.state.get("game_id", "")),
                t.dest["id"],
                int(t.world.get("turn_count", 0) or 0),
            )
            disc_note, t.discovery_events = exploration.discover_on_arrival(
                _pl,
                t.world,
                t.dest,
                int(_pl.get("level", 1) or 1),
                _rng,
                projection=t.state.get("world_projection"),
                first_visit=first_visit,
            )
            if disc_note:
                t.faction_note = (t.faction_note + " " + disc_note).strip()
            t.discovery_player = _pl
            t.turn_bl = record_gain(
                t.turn_bl,
                "gold",
                int(_pl.get("gold", 0) or 0)
                - int((t.state.get("player") or {}).get("gold", 0) or 0),
                "exploration",
            )
        if t.travel_periods == 0:
            t.discovered_routes = []  # entrar em interior nao descobre rota
            t.travel_note = (
                f"O jogador ENTROU em {t.dest['name']} (mesma cidade — o tempo não passou). "
                f"Contexto do local: {t.dest.get('lore_seed', '')} Descreva o que ele vê ao entrar."
            )
        else:
            t.travel_note = (
                f"O jogador VIAJOU para {t.dest['name']}"
                + (
                    f" (viagem longa: {t.travel_periods} períodos). "
                    if t.travel_periods > 1
                    else ". "
                )
                + f"Contexto do local: {t.dest.get('lore_seed', '')} Descreva a chegada e o que ele vê agora."
            )
            if t.discovered_routes:
                t.travel_note += (
                    " A estrada estava cortada (o comércio por ela está parado) e o jogador só "
                    "descobre isso agora: ele PASSOU com dificuldade e chegou. Narre a travessia "
                    "difícil e a descoberta, sem inventar a causa nem um desvio."
                )
            if t.closed_pass:
                t.travel_note += f" {world_calendar.CROSSING_NOTE} Descreva a travessia dura e a nevasca ao chegar."
    elif t.last_user_input and not t.law_resolved and is_rest(t.last_user_input):
        from world_utils import weather_effects

        rest_blocked = weather_effects(t.world).get("rest_block", False)  # Fase 6.5
        # spec refatoracao-sistema-classes (R6): aliado ativo mitiga a Insônia do Devoto.
        import party as _party_mod

        _rest_allies = _party_mod.active_allies(t.state)
        t.rested_player, t.world = apply_rest(
            dict(t.state.get("player", {})), t.world, allies=_rest_allies
        )
        # SPEC-233 R7: fações avançam pelo delta REAL do relógio (bloqueado = 1 período).
        t.world, t.factions, t.world_tick = _world_tick(
            t.state, world_before, t.world, t.factions, t.intel
        )
        if not _engine_owns_factions():
            t.factions, t.faction_events = advance_factions(t.factions, 1 if rest_blocked else 2)
            t.factions, t.world, t.faction_note = resolve_faction_completions(
                t.factions, t.world, t.faction_events, t.intel
            )
        if rest_blocked:
            t.rest_note = (
                f"O jogador TENTOU descansar, mas o clima ({t.world.get('weather', 'o miasma')}) "
                f"NÃO permite descanso seguro ao relento — NADA foi recuperado e o tempo passou "
                f"({clock_label(t.world, _cal_of(t.state))}). Narre a noite péssima e a exaustão."
            )
        else:
            t.rest_note = (
                f"O jogador DESCANSOU. O tempo avançou para {clock_label(t.world, _cal_of(t.state))} e ele recuperou parte das forças. "
                "Narre a passagem do tempo e o estado do mundo ao acordar."
            )
    t.perceived_items: list = []
    t.wq_created: list = []
    if t.world_tick is not None:
        if getattr(t.world_tick, "state_patch", None):
            # SPEC-304: escritas dos hooks (npc_sim, party/npcs de destino de companheiro...):
            # entram no estado do turno ANTES do resto (cena, contexto, quests leem `state`).
            t.sim_updates.update(t.world_tick.state_patch)
            t.state = {**t.state, **t.world_tick.state_patch}
        if t.world_tick.world_sim is not None:
            if t.closed_pass:  # SPEC-303 R27: telemetria de travessia de passo fechado
                _ps = t.world_tick.world_sim.setdefault("perceived_stats", {})
                _ps["pass_crossings"] = int(_ps.get("pass_crossings", 0)) + 1
            t.sim_updates[t.world_tick.sim_key] = t.world_tick.world_sim
            t.world, t.perceived_items = _perceive_world(
                t.state, t.world, t.factions, t.intel, t.world_tick
            )
            if t.discovered_routes:  # F2: o bloqueio descoberto entra no livro-razao do heroi
                _sim = t.world_tick.world_sim
                _sim["perceived_ids"] = [*(_sim.get("perceived_ids") or []), *t.discovered_routes][
                    -400:
                ]
            # SPEC-309 R7/R8: o que o heroi percebeu hoje vira memoria canonica (texto de
            # template, nunca a prosa da LLM), haja ou nao narracao do dia
            from services.perceived_world import day_memory_facts

            _day_facts = day_memory_facts(
                _perception_state(t.state, t.world, t.factions, t.intel), t.perceived_items
            )
            if _day_facts:
                t.sim_updates["memory_canonical_facts"] = list(
                    dict.fromkeys([*(t.state.get("memory_canonical_facts") or []), *_day_facts])
                )
                t.sim_updates["archive_due"] = True
        t.extra_engine_events_tick = list(t.world_tick.pending_events)
        t.extra_engine_events_tick += _npc_beliefs_update(
            t.state, t.world, t.sim_updates, t.perceived_items
        )
        if (
            t.perceived_items or "npc_beliefs" in t.sim_updates
        ):  # SPEC-308 R6: marco de evento do motor percebido so agora
            try:
                from services.chronicle import perceived_milestones

                _chron = perceived_milestones({**t.state, **t.sim_updates, "world": t.world})
                if _chron is not None:
                    t.sim_updates["chronicle"] = _chron
            except Exception as exc:
                from observability.telemetry import log_fallback

                log_fallback("storyteller", "perceived_milestones_failed", exc)
    else:
        t.extra_engine_events_tick = []
    # --- SPEC-301: o tempo passou -> a fação do jogador pode ter ascendido/sido destruída,
    # e rivais que já sabem do vínculo reagem (chegada à região deles ou notícia). ---
    if t.state.get("faction_membership"):
        _fm_notes: list = []
        _was_defeated = {f.get("id") for f in (t.state.get("factions") or []) if f.get("defeated")}
        for _f in list(t.factions):
            if _f.get("defeated") and _f.get("id") not in _was_defeated:
                _fm_notes.append(_fm_apply(t, fm.on_faction_defeated(_fm_view(t), _f.get("id"))))
        _asc_events = fm.new_ascensions(t.state.get("factions"), t.factions, t.faction_events)
        _asc = fm.ascension_member_note(_fm_view(t), _asc_events)
        if _asc:
            _fm_notes.append(_asc)
        _fm_notes.append(
            _fm_apply(
                t,
                fm.apply_rival_awareness(
                    _fm_view(t),
                    str(t.dest["id"]) if t.dest else str(t.world.get("current_location_id") or ""),
                    arrived=bool(t.dest),
                ),
            )
        )
        _fm_text = "\n".join(n for n in _fm_notes if n)
        if _fm_text:
            t.faction_note = (t.faction_note + "\n" + _fm_text).strip()

    # SPEC-305: quests de mundo (prazo/falha + oferta por percepcao); a lista parcial
    # `wq_quests` substitui `state["quests"]` em todo o resto do turno.
    wq_base = {**t.state, "quests": t.fm_extra["quests"]} if "quests" in t.fm_extra else t.state
    t.wq_quests, t.wq_events, t.wq_created = _world_quests_tick(
        wq_base, t.world, t.factions, t.intel, t.world_tick, t.perceived_items
    )
    t.extra_engine_events_tick += t.wq_events
    t.extra_engine_events_tick += _world_quest_completions(t.state, t.world, t.wq_quests)
    t.wq_changed = t.wq_quests != list(t.state.get("quests") or [])  # inclui quests da 301
    t.rumor_nothing = False  # SPEC-315 §6.2: busca no alvo de boato sem achado devido
    t.rumor_find = False  # SPEC-315: achado de boato => `world.looted_locations` tem de sobreviver
    if not t.dest and t.rested_player is None and not t.law_resolved and t.last_user_input:
        _cache_player, _cache_note, _cache_events = _rumor_cache_trigger(
            t.state, t.world, t.sim_updates, str(t.last_user_input), t.wq_quests
        )  # SPEC-315: boato verdadeiro de achado, no alvo, com busca/quest
        if _cache_player is None:
            try:
                from services import rumor_adoption as _ra_n

                t.rumor_nothing = _ra_n.nothing_found(
                    {**t.state, **t.sim_updates, "world": t.world},
                    str(t.world.get("current_location_id") or ""),
                    str(t.last_user_input),
                )
            except Exception as exc:
                from observability.telemetry import log_fallback

                log_fallback("storyteller", "rumor_nothing_failed", exc)
        if _cache_player is not None:
            t.rumor_find = True
            t.discovery_events = list(t.discovery_events) + _cache_events  # claim de unico
            t.discovery_player = _cache_player
            t.faction_note = (t.faction_note + " " + _cache_note).strip()
            t.turn_bl = record_gain(
                t.turn_bl,
                "gold",
                int(_cache_player.get("gold", 0) or 0)
                - int((t.state.get("player") or {}).get("gold", 0) or 0),
                "exploration",
            )
    # Viagem fecha a cena anterior antes de qualquer encontro ou contexto. Isso
    # também protege retornos antecipados de combate contra NPCs teleportados.
    from services import npc_layers

    t.scene_npcs = (
        npc_layers.reset_scene(t.state.get("npcs", {})) if t.dest else t.state.get("npcs", {})
    )
    t.scene_state = {**t.state, "world": t.world, "npcs": t.scene_npcs}
    t.travel_needs_replan = bool(t.state.get("needs_replan"))
    if t.dest:
        from agents.campaign_manager import _same_region

        planned_location = str((t.state.get("campaign_plan") or {}).get("location") or "")
        if planned_location and not _same_region(
            planned_location,
            str(t.world.get("current_location") or ""),
        ):
            t.travel_needs_replan = True
    # SPEC-311 R6-R8: o mundo mudou DIANTE do herói (crise na região, cidade caída, quest dele
    # falhou) => o arco replaneja. Lê só o que foi percebido hoje; vale em todo caminho de saída.
    from services.planner_context import world_replan_cause

    t._replan_cause = world_replan_cause(t.scene_state, t.perceived_items, t.wq_events)
    if t._replan_cause:
        t.travel_needs_replan = True
        _log_event("campaign", "world_replan_trigger", cause=t._replan_cause)

    # (Ação livre: o gating é feito pelo PRÓPRIO narrador no prompt — sem chamada extra ao Ruler.)

    # --- O tempo passou (viagem/descanso): ou cai em encontro, ou o mundo "respira" ---
    t.world_note = ""
    t.extra_engine_events: list = list(t.extra_engine_events_tick)
    t.track_bk = None  # Fase 6.4: rastro atualiza o Codex do jogador
    # SPEC-360 R20: "sigo o rastro" com sinal visto e presença no local = encontro no lugar.
    from services import fauna as _fauna

    t._fauna_hunt = None
    t._fauna_sign_shown = False  # no máximo 1 sinal de fauna por cena (R14)
    t._fauna_day = int((t.world.get("world_clock") or {}).get("day", 1) or 1)
    if not t.dest and t.rested_player is None and not t.law_resolved and t.last_user_input:
        try:
            t._fauna_hunt = _fauna.hunt_hint(
                {**t.state, **t.sim_updates, "world": t.world},
                t.world,
                int((t.state.get("player") or {}).get("level", 1) or 1),
                text=str(t.last_user_input),
            )
        except Exception as exc:
            from observability.telemetry import log_fallback

            log_fallback("storyteller", "fauna_hunt_failed", exc)
    # spec mapa-sublocais (R2): custo 0 (intra-cidade/interior) não rola encontro
    if (t.dest and t.travel_periods >= 1) or t.rested_player is not None or t._fauna_hunt:
        t.turn = int(t.world.get("turn_count", 0))
        # R5 (fix-playtest-achados): a FORÇA do encontro escala pelo nível (apex não).
        _plevel = int((t.state.get("player") or {}).get("level", 1) or 1)
        from gamedata import get_location as _get_location
        from world_utils import effective_danger, recovery_rest_safe

        danger_now = effective_danger(t.world)  # SPEC-233 R1
        # spec letalidade-early-game-v2 (alavanca 1): um DESCANSO de early-game em
        # zona não-apex de perigo baixo recupera SEM sortear encontro — o laço de
        # recuperação que faltava (viagem não cura; descanso interrompido = morte).
        # Só vale pra REST (rested_player is not None), nunca pra viagem.
        _rest_recovers = t.rested_player is not None and (
            recovery_rest_safe(
                _plevel, danger_now, _get_location(t.world.get("current_location_id", "")) or {}
            )
            # SPEC-301 R9: perk `abrigo` — descanso no QG da própria fação não sorteia encontro
            or fm.has_perk(
                _fm_view(t), "abrigo", location_id=str(t.world.get("current_location_id") or "")
            )
        )
        if _rest_recovers:
            t.enc = None
        elif t._fauna_hunt:  # SPEC-360 R20: a caça escolhe a criatura (a da presença)
            t.enc = dict(t._fauna_hunt)
            t.world["encounter_eff_danger"] = int(t.enc.get("eff_danger") or 1)
        else:
            # Fase 6.3: sorteio ponderado — pressão de caça/fação/migração
            _law_hint = _law_mod.hunter_encounter(
                {**t.state, "world": t.world},
                str(t.world.get("current_location_id") or ""),
                _law_mod.clock_of({**t.state, "world": t.world}),
            )
            from services import lore_quests as _lq

            _rumor_hint, _rumor_id = (
                _rumor_arrival(t.state, t.world, t.sim_updates, _plevel, t.turn)
                if t.dest and t.travel_periods >= 1
                else (None, "")
            )  # SPEC-315 R16
            t.enc = check_encounter(
                t.world,
                t.factions,
                t.intel,
                t.turn,
                bestiary_knowledge=t.state.get("bestiary_knowledge"),
                projection=t.state.get("world_projection"),
                player_level=_plevel,
                law_hint=_law_hint,
                exempt_factions=fm.passage_factions(_fm_view(t)),  # SPEC-301 perk `passagem`
                hunt_anchor=_lq.active_hunt_anchor({**t.state, "world": t.world}),  # SPEC-313 R26
                rumor_hint=_rumor_hint,
                world_sim=(
                    (t.sim_updates.get("world_sim") or t.state.get("world_sim") or {})
                    if _fauna.mode() != "off"
                    else None
                ),  # SPEC-360: ecologia, presença e conversão em sinal
                game_id=str(t.state.get("game_id") or ""),
                trama_stages=_fauna.fauna_tramas.stages_for(t.state, t.world),  # SPEC-372
            )
            if t.enc and t.enc.get("reason") == "rumor":
                from services import rumor_adoption as _ra

                t.sim_updates["world_sim"] = _ra.commit(
                    t.sim_updates.get("world_sim") or t.state.get("world_sim") or {},
                    _rumor_id,
                    int((t.world.get("world_clock") or {}).get("day", 1) or 1),
                    {"kind": "encounter", "enemy_id": str(t.enc.get("enemy_id") or "")},
                )
        # spec encontros-dedupe (R3): não repete o MESMO template de encontro 2x
        # seguidas no mesmo local (o mundo não é um carrossel).
        t.enc = _dedupe_encounter(t.enc, t.world)  # SPEC-233 R6
        if not t.enc:
            t.world.pop("encounter_eff_danger", None)  # SPEC-233 R5
        if t.enc and t.enc.get("fauna_convert"):
            # SPEC-360 R16: sem presença anunciada, o encontro vira sinal; cooldown carimbado.
            _fe = _fauna.entry(str(t.enc.get("enemy_id") or ""))
            _fnote, _fupd = (
                _fauna.convert_to_signal(
                    {**t.state, **t.sim_updates, "world": t.world},
                    _fe,
                    str(t.world.get("current_location_id") or ""),
                    t._fauna_day,
                )
                if _fe
                else ("", {})
            )
            # P2-9 (Sol): sem vaga para anunciar (teto da região/global), a criatura que não pôde
            # ser anunciada ataca como o encontro original; o turno não fica vazio nem gasta o
            # cooldown de um sinal que não houve.
            if _fnote:
                t.world["last_encounter_turn"] = t.turn
                t.world["last_encounter_id"] = "fauna_sinal"
                t.world["last_encounter_loc"] = t.world.get("current_location_id")
                t.world.pop("encounter_eff_danger", None)
                if _fupd.get("world_sim"):
                    t.sim_updates["world_sim"] = _fupd["world_sim"]
                t.world_note = f"ENCONTRO NA ESTRADA (sinal): {_fnote}\n{_fauna.SCENE_RULE}"
                t._fauna_sign_shown = True
                t.enc = None
        if t.enc:
            t.world["last_encounter_turn"] = t.turn
            t.world["last_encounter_id"] = t.enc.get("hint")
            t.world["last_encounter_loc"] = t.world.get("current_location_id")
            t.danger = effective_danger(t.world)
            t.base_p = (
                t.rested_player
                if t.rested_player is not None
                else dict(t.discovery_player or t.state.get("player") or {})
            )

            # Fase 6.4 (R1): percepção decide surpresa; (R2): nem todo perigo é combate.
            # Reforço/fação dominante SEMPRE é combate (eles vieram POR você).
            from world_utils import (
                detection_check,
                light_level,
                resolve_track,
                resolve_trap,
                roll_encounter_type,
                weather_effects,
            )

            # Fase 6.5: neblina/vendaval atrapalham a percepção.
            # spec itens-vivos-e-luz (R3): escuridão sem luz também penaliza.
            _perc_mod = weather_effects(t.world).get("perception_mod", 0) + light_level(
                t.world, t.base_p
            ).get("perception_mod", 0)
            if t.enc.get("presence_id"):  # SPEC-360 R18: quem leu os sinais se prepara
                _perc_mod += _fauna.detection_bonus(
                    t.sim_updates.get("world_sim") or t.state.get("world_sim") or {},
                    str(t.enc["presence_id"]),
                )
            t.det = detection_check(t.base_p, t.danger, perception_mod=_perc_mod)
            if t.enc.get("reason") == "caca":  # R20: quem caça chega primeiro
                t.det = {**t.det, "perceived": True}
            t.kind = (
                "combat"
                if t.enc.get("reason") in ("reinforcements", "controlled", "bounty_hunters")
                or t.enc.get("always_combat")
                else roll_encounter_type(t.danger)
            )

            if t.kind == "combat":
                from services.combat_origin import from_encounter

                # surpresa: percebeu -> herói embosca; falhou -> inimigo age antes
                t.world["encounter_surprise"] = "player" if t.det["perceived"] else "enemy"
                # R5: percebeu = tem AGÊNCIA — pode golpear OU recuar (a fuga já é
                # mecânica no combate: "fujo/corro/recuo"). Surpreendido = sem saída.
                sur_txt = (
                    "Você os percebe ANTES — há tempo de golpear primeiro OU RECUAR "
                    "(diga que foge/corre/recua para escapar)."
                    if t.det["perceived"]
                    else "Eles saem do nada — você é pego de surpresa, sem chance de recuar."
                )
                t.updates = {
                    "messages": [
                        SystemMessage(content=f"COMBAT START. {t.enc['flavor']} {sur_txt}")
                    ],
                    "world": t.world,
                    "factions": t.factions,
                    "combat_target": t.enc["hint"],
                    "combat_encounter_hint": encounter_handoff(t.enc),
                    "combat_origin_hint": from_encounter(
                        t.enc,
                        t.world,
                        trigger=("rest" if t.rested_player is not None else "travel"),
                    ),
                    "next": "combat_agent",
                    "archive_due": True,  # emboscada = evento relevante
                    "npcs": t.scene_npcs,
                    "needs_replan": t.travel_needs_replan,
                }
                if t.rested_player is not None:
                    t.updates["player"] = t.rested_player  # já curou no descanso antes da emboscada
                elif t.discovery_player is not None:
                    t.updates["player"] = t.discovery_player
                # spec loot-exploracao: claim de único do baú curado não se perde
                # se um encontro disparar na mesma chegada.
                if t.turn_bl is not t.state.get("turn_baseline"):
                    t.updates["turn_baseline"] = t.turn_bl
                # `npcs` do patch ja esta em `scene_npcs` (com o reset_scene da viagem): nao sobrescrever
                t.updates.update({k: v for k, v in t.sim_updates.items() if k != "npcs"})
                if t.enc.get("reason") == "bounty_hunters":  # SPEC-377 R7: depois do merge da poda
                    t.updates.update(
                        _law_mod.mark_hunters(
                            t.state,
                            str(t.enc.get("jurisdiction_id") or ""),
                            _law_mod.clock_of({**t.state, "world": t.world}),
                        )
                    )
                if t.wq_changed:
                    t.updates["quests"] = t.wq_quests
                if t.discovery_events or t.extra_engine_events:
                    t.updates["pending_world_events"] = (
                        (t.state.get("pending_world_events", []) or [])
                        + t.discovery_events
                        + list(t.extra_engine_events)
                    )
                # Fase 3.2 (R3): criatura nomeada no hint ANTES do combate = rumor.
                enemy_id = t.enc.get("enemy_id")
                if enemy_id:
                    t.updates["bestiary_knowledge"] = disc.record_rumor(
                        t.state.get("bestiary_knowledge", {}), enemy_id, t.turn
                    )
                if t.enc.get("presence_id"):  # SPEC-360 R23: o sinal visto ganha dono
                    _fsim, _shown = _fauna.mark_encountered(
                        t.updates.get("world_sim") or t.state.get("world_sim") or {},
                        str(t.enc["presence_id"]),
                        t._fauna_day,
                        status="cacada" if t.enc.get("reason") == "caca" else "encontrada",
                    )
                    t.updates["world_sim"] = _fsim
                    if enemy_id and _shown:
                        t.updates["bestiary_knowledge"] = disc.record_sinais(
                            t.updates.get("bestiary_knowledge")
                            or t.state.get("bestiary_knowledge"),
                            str(enemy_id),
                            _shown,
                            t.turn,
                        )
                return t.updates

            _story_noncombat_encounter(t)
        _story_world_pulse(t)

    _story_context_blocks(t)

    t.llm = get_llm(temperature=0.7)

    _story_prompt_blocks(t)

    _story_prompt_scene_blocks(t)

    _story_system_message(t)

    # SPEC-233 R8: ganhos registrados ANTES da LLM (o except não herda XP de beat
    # que só seria aplicado no caminho feliz).
    t.turn_bl_pre_llm = t.turn_bl
    t.companion_narrated = False  # SPEC-300 R13: o ack só vale no caminho feliz
    try:
        _story_narrate(t)

        _story_guard_narrative(t)

        _story_engine_proposals(t)

        _story_beat_and_npcs(t)

        _story_assemble_base(t)

        _story_assemble_items(t)
        _story_assemble_events(t)

        _story_assemble_quests(t)
        return t.updates

    except Exception as e:
        _log_event("storyteller", "failed", level="error", error=type(e).__name__)
        return _story_exception_fallback(t)


def _story_noncombat_encounter(t: _StoryTurn) -> None:
    """Encontro sem combate: armadilha, rastro ou social."""
    from gamedata import get_location
    from services import fauna as _fauna
    from services.turn_outcome import record_gain
    from world_utils import resolve_track, resolve_trap

    loc_node = get_location(t.world.get("current_location_id", "")) or {}
    t.world.pop("encounter_eff_danger", None)  # SPEC-233 R5: não-combate
    if t.kind == "trap":
        from party import active_allies

        helper = next(iter(active_allies(t.state)), None)
        new_p, trap_logs, info = resolve_trap(
            t.base_p,
            loc_node,
            t.danger,
            helper=helper,
        )
        t.rested_player = new_p  # reusa o encanamento de player existente
        t.turn_bl = record_gain(
            t.turn_bl,
            "xp",
            int(new_p.get("xp", 0) or 0) - int(t.base_p.get("xp", 0) or 0),
            "exploration",
        )
        t.world_note = (
            "ENCONTRO NA ESTRADA (armadilha — números JÁ resolvidos, narre-os):\n"
            + "\n".join(trap_logs)
        )
        if info:
            t.extra_engine_events += info.get("level_up_events", [])
    elif t.kind == "track":
        from services import lore_quests as _lq

        _track_entry: dict = {}

        def _describe_track(e: dict) -> str | None:
            fe = _fauna.entry(str((e or {}).get("id") or ""))
            text = ((fe or {}).get("sinais") or {}).get("rastro")
            if text:
                _track_entry["e"] = fe
            return text

        t.track_bk, note, hint = resolve_track(
            t.state.get("bestiary_knowledge", {}),
            loc_node,
            t.danger,
            t.turn,
            hunt_anchor=_lq.active_hunt_anchor({**t.state, "world": t.world}),  # SPEC-313 R26
            describe=_describe_track if _fauna.sinais_mode() == "on" else None,
            trama_stages=_fauna.fauna_tramas.stages_for(t.state, t.world),  # SPEC-372
        )
        if hint:
            t.world["treasure_hint"] = True
        t.world_note = f"ENCONTRO NA ESTRADA (rastro): {note}"
        if _track_entry:  # SPEC-360 R22: o rastro cria/reforça a presença, sem nome
            _tnote, _tupd = _fauna.track_signal(
                {**t.state, **t.sim_updates, "world": t.world},
                _track_entry["e"],
                str(t.world.get("current_location_id") or ""),
                t._fauna_day,
            )
            if _tupd.get("world_sim"):
                t.sim_updates["world_sim"] = _tupd["world_sim"]
            t.world_note += f"\n{_fauna.SCENE_RULE}"
            t._fauna_sign_shown = True
    else:  # social
        t.world_note = (
            "ENCONTRO NA ESTRADA (social): um grupo HOSTIL-MAS-NEGOCIÁVEL aborda o "
            "jogador (ligado ao perigo local). Narre a abordagem tensa SEM iniciar "
            "combate — eles querem algo (pedágio, informação, escolta). Se surgir um "
            "porta-voz, registre-o em introduced_npcs."
        )


def _story_world_pulse(t: _StoryTurn) -> None:
    """Sem emboscada: o mundo gera 1 evento off-screen narrado."""
    # Sem emboscada: o mundo gera 1 evento off-screen narrado (e grava no RAG da sessão).
    try:
        if _engine_owns_factions():
            # modo on: a narracao diaria substitui o pulso (SPEC-302 R26); so se o dia
            # virou e algo foi percebido (0 chamadas caso contrario)
            t.world_note = t.world_note or _narrate_world(
                t.state, t.world, t.factions, t.intel, t.perceived_items
            )
        else:
            t.world, t.world_note = simulate_world(
                t.state, t.world, t.factions, t.intel, 1 if t.dest else 2
            )
            if t.world_note.startswith("[ECOS DO MUNDO]"):
                # SPEC-296 R6: rumor percebido persiste ("Ouvi dizer").
                from services.ambient import append_news

                t.world = append_news(
                    t.world,
                    text=t.world_note[len("[ECOS DO MUNDO]") :].strip(),
                    location_id=t.world.get("current_location_id", ""),
                    location_name=t.world.get("current_location", ""),
                    turn=int(t.world.get("turn_count", 0) or 0),
                )
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "world_pulse_failed", exc)
        t.world_note = ""


def _story_context_blocks(t: _StoryTurn) -> None:
    """Contexto híbrido: pacote de lore/memória, ambiente, clima e beat ativo."""
    t.loc = t.world.get("current_location", "")
    # spec encontros-dedupe (R1): só NPCs vinculados ao local/em cena/party —
    # NPC gerado em outro lugar não é reciclado nesta cena.
    from services.npc_layers import npcs_for_context

    t.scene_state = {**t.scene_state, "world": t.world}
    t.existing_npcs = npcs_for_context(t.scene_state)

    # --- Contexto Híbrido ---
    t.game_id = t.state.get("game_id")
    # --- Fase 2.8: contexto centralizado (estado dinâmico + lore + memória, com budget) ---
    # ESTADO ATUAL entra ANTES da lore base: a verdade viva vence o canônico.
    t.pack = build_context_pack(
        t.scene_state,
        query=compose_lore_query(t.scene_state, t.last_user_input),
        purpose="story",
        game_id=t.game_id,
    )
    t.lore_context = t.pack.lore_block or "Dark Fantasy Genérica."
    t.memoria_recente = t.pack.memory_block or "Sem memória recente dentro do budget deste turno."
    # spec arvores-habilidade-classes (§3.3): utilitárias conhecidas — gate
    # determinístico; a LLM só narra o que a ficha PERMITE.
    from services.context_builder import utility_context_block

    t.capacidades_block = utility_context_block(t.state.get("player", {}) or {})

    # SPEC-296 R4/R5: bloco de ambiente único (período, clima local/global, luz,
    # perigo, abrigo e saídas) — substitui luz_block/clima_block.
    from services.ambient import ambient_block, heard_block
    from world_utils import weather_effects as _weather_effects

    t.ambiente_block = ambient_block(t.world, t.state.get("player", {}) or {}, audience="story")
    t.ouviu_block = heard_block(t.world)
    from services.perceived_world import perceived_world_block

    t.mundo_percebido_block = perceived_world_block(
        {**t.state, **t.sim_updates, "world": t.world}, audience="story"
    )  # SPEC-309 R18
    from world_utils import light_level as _light_level

    t._ll = _light_level(t.world, t.state.get("player", {}) or {})
    t.weather_note = ""
    if t.world.get("weather_global"):
        t.weather_note = (
            f"Fenômeno global ativo: {_weather_effects(t.world).get('label', 'clima anômalo')}. "
            "Ele domina o céu e afeta toda a cena."
        )

    t.season_line = _season_line(t.world)  # SPEC-303 R21 (determinística, sem chamada LLM)
    from services import world_calendar as _wcal

    if _wcal.clock_date_label(t.world, _cal_of(t.state)):  # SPEC-307 R18
        t.season_line += (
            " Use só os nomes de mês e de dia de Valoria que aparecem em Momento; "
            "não invente datas nem meses de outro mundo."
        )

    t.campaign_plan = t.state.get("campaign_plan") or {}
    t.beats = [dict(beat) for beat in t.campaign_plan.get("beats", [])]
    t.current_step = t.campaign_plan.get("current_step", 0)
    t.beat_eligible = (
        isinstance(t.current_step, int)
        and not isinstance(t.current_step, bool)
        and 0 <= t.current_step < len(t.beats)
        and t.beats[t.current_step].get("status", "pending") in {"pending", "active"}
    )
    t.active_step = (
        t.beats[t.current_step].get("description") if t.beat_eligible else "Clímax ou Ação Livre."
    )


def _story_prompt_blocks(t: _StoryTurn) -> None:
    """Eventos do turno, fações, entidades, quests e herói do prompt."""
    # PROMPT ATUALIZADO
    t.eventos_turno = (
        "\n".join(
            n
            for n in (
                t.travel_note,
                t.rest_note,
                t.faction_note,
                t.world_note,
                NOTHING_FOUND_FACT if t.rumor_nothing else "",
            )
            if n
        )
        or "Nenhum evento especial."
    )

    # Fações que o JOGADOR conhece (não-onisciência): só estas podem ser citadas/afetadas.
    t.faccoes_conhecidas = (
        "\n".join(
            f"- id={f.get('id')} · {f.get('name')} ({f.get('region', '')}) · disposição={f.get('disposition', 'neutro')}"
            for f in t.factions
            if t.intel.get(f.get("id"), {}).get("known") and not f.get("defeated")
        )
        or "Nenhuma fação conhecida pelo jogador ainda."
    )

    # Fase 2.6: ids canônicos que o LLM pode usar em proposed_events (defesa em profundidade).
    t.entidades_canonicas = _scene_canonical_entities(t.scene_state, t.factions, t.intel, t.loc)
    # Fase 3.3: quests ativas que o LLM pode concluir via proposed_events(quest_completed).
    # SPEC-305 (revisao P1-2): quest que falha NESTE turno sai do bloco que o narrador pode concluir.
    _failing = {e.get("target_id") for e in t.wq_events if e.get("type") == "quest_failed"}
    _prompt_quests = [q for q in t.wq_quests if q.get("id") not in _failing]
    t.quests_ativas = _quests_ativas_block(
        _prompt_quests, {**t.state, "world": t.world, "quests": t.wq_quests}
    )
    t.gancho_novo = _gancho_novo_block(t.wq_created) + _rumor_proposal_hint()
    from services import lore_quests as _lore  # SPEC-313 R23: desfecho do rumor investigado

    _desfecho = _lore.desfecho_block({**t.state, "world": t.world, "quests": t.wq_quests})
    if _desfecho:
        t.gancho_novo += "\n" + _desfecho

    # spec npc-fallback-sem-alvo (R2): rota NPC sem interlocutor delegou aqui.
    t.npc_fallback_clause = _npc_fallback_clause(t.scene_state)
    # SPEC-202 R2/R7/R11: mediação do narrador (dados públicos do sujeito).
    t.npc_fallback_clause += _mediation_clause(t.scene_state)
    # spec polish-prosa: R1 (varie a abertura) + R3 (menu de opções concretas).
    from services import prose_guard

    t._aberturas = prose_guard.ultimas_aberturas(t.messages)
    t.varie_clause = prose_guard.openings_clause(t._aberturas)
    t.opcoes_clause = (
        "\n    - FECHE com 2 a 3 OPÇÕES concretas de ação, cada uma numa "
        "linha iniciada por '— ', e termine com '— Ou outra ação.' "
        "(dê rumo ao jogador; as opções mecânicas de combate vêm à parte)."
    )
    _hero = t.state.get("player", {}) or {}
    t.hero_state_block = (
        "<ESTADO_DO_HEROI>\n"
        f"Nível: {int(_hero.get('level', 1) or 1)} · "
        f"Vitalidade: {int(_hero.get('vitalidade', _hero.get('hp', 0)) or 0)}/"
        f"{int(_hero.get('max_vitalidade', _hero.get('max_hp', 0)) or 0)} · "
        f"Ouro: {int(_hero.get('gold', 0) or 0)}\n"
        "Se mencionar o saldo do herói, use EXATAMENTE esse Ouro.\n"
        "</ESTADO_DO_HEROI>"
    )


def _story_prompt_scene_blocks(t: _StoryTurn) -> None:
    """Blocos de fama, vínculo, elenco, companheiros, lei e fauna."""
    from services import faction_membership as fm
    from services import fauna as _fauna

    # SPEC-298 R25: fama do local atual (rótulo, nunca número) — só se o jogador é conhecido ali.
    from services.reputation import fame_line

    _fame = fame_line(t.state)
    t.fame_block = f"<FAMA_LOCAL>\n{_fame}\n</FAMA_LOCAL>" if _fame else ""
    t.faction_member_block = fm.prompt_block(_fm_view(t))  # SPEC-301 R21 (vazio sem vínculo)

    # SPEC-297 R22: elenco oferecido ao NARRADOR (não ao jogador); vazio salvo flag `on`.
    try:
        from services import shared_pool

        t._cast = shared_pool.cast_entries(t.state)
        t.cast_block_text = shared_pool.cast_block_text(t._cast)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "pool_cast_failed", exc)
        t._cast, t.cast_block_text = [], ""

    # SPEC-300: companheiros com alma (fala espontânea sem chamada LLM extra).
    try:
        from services.companion_prompt import companion_prompt_block

        t.companion_block, t.companion_ack = companion_prompt_block(t.state, "story")
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "companion_block_failed", exc)
        t.companion_block, t.companion_ack = "", []

    # SPEC-299 R9/R16/R19: fato de cena da lei (patrulha, confronto, sinais). Sem nada a
    # dizer o bloco nem existe (zero token). Nunca heat/bounty/nível (R17).
    # P1-3: a cena é a do DESTINO (viagem já aplicada em `world`/`scene_npcs`).
    law_scene = {**t.state, "world": t.world, "npcs": t.scene_npcs}
    _law_text, t._law_scene_updates = _law_mod.scene_block(law_scene)
    t.lei_block = _law_text
    if _law_mod.crime_hint_enabled(law_scene):
        t.lei_block = "\n".join(p for p in (t.lei_block, _law_mod.CRIME_CLAIM_HINT) if p)
    # SPEC-360 R14: 1 sinal de fauna por cena, só se houver (0 token sem sinal).
    if not t._fauna_sign_shown:
        try:
            _fauna_text, _fauna_upd = _fauna.scene_block(
                {**t.state, **t.sim_updates, "world": t.world}
            )
        except Exception as exc:
            from observability.telemetry import log_fallback

            log_fallback("storyteller", "fauna_scene_failed", exc)
            _fauna_text, _fauna_upd = "", {}
        if _fauna_upd.get("world_sim"):
            t.sim_updates["world_sim"] = _fauna_upd["world_sim"]
        if _fauna_text:
            t.lei_block = "\n".join(p for p in (t.lei_block, _fauna_text) if p)


def _story_narrate(t: _StoryTurn) -> None:
    """Chamada estruturada do narrador (stream) com o guard de FallbackLLM."""
    from services import interlocutor as _interlocutor
    from services import prose_guard
    from services import rumors as _rumors_mod
    from services.narrative_sink import narrate_structured

    # SPEC-319 (revisao P1-1/P2-1): o guard de segredo da narracao mediada (SPEC-202 R11) e o
    # de achado falso de boato (SPEC-315) so rodam no texto FINAL; nesses turnos nada vai
    # ao vivo (a 316 entrega o texto ja guardado).
    _stream_ok = not t.rumor_nothing and (
        t.state.get("interlocutor_reason") not in _interlocutor.MEDIATION_REASONS
    )

    # SPEC-223 R5: entrada do jogador delimitada como dado.
    # SPEC-319: com sink ligado (so no stream SSE) `narrative` sai token a token;
    # sem sink e o `with_structured_output(...).invoke` de sempre.
    t._open_salt = (
        f"{t.state.get('game_id', '')}:{(t.world or {}).get('turn_count', 0)}:storyteller"
    )
    _gold_now = int((t.state.get("player") or {}).get("gold", 0) or 0)

    def _stream_view(partial: str) -> str:
        # Follow-up D1: as mesmas correcoes do texto final, em fluxo — saldo de ouro e
        # abertura repetida — para o stream ser prefixo do final (ordem igual a de baixo).
        return prose_guard.vary_repeated_opening(
            prose_guard.reconcile_player_gold_claims(partial, _gold_now),
            t._aberturas,
            salt=t._open_salt,
        )

    t.update = narrate_structured(
        t.llm,
        _story_schema_for_rumors(_rumors_mod),
        [t.sys] + guard_messages(t.messages[-3:]),
        state=t.state,
        stream=_stream_ok,
        finalize=_stream_view,
        hold_extra=72,  # o maior padrao de saldo de ouro fecha em ~60 caracteres
        min_words=8 if t._aberturas else 0,
        # follow-up tail: o guard de evidencia/item roda no final; o stream para antes da
        # 1a frase que ele pode cortar (estado do turno apos viagem/descanso/achado)
        evidence_state={
            **t.state,
            "world": t.world,
            "player": t.rested_player or t.discovery_player or t.state.get("player") or {},
        },
        hold_acquisition=True,
    )

    # Guard crítico: FallbackLLM devolve AIMessage, não o schema solicitado.
    t.companion_narrated = isinstance(t.update, StoryUpdate)
    if not isinstance(t.update, StoryUpdate):
        from observability.telemetry import log_fallback

        log_fallback("storyteller", "structured_invalid")
        t.update = StoryUpdate(
            narrative=_deterministic_story_fallback(
                (t.travel_note, t.rest_note, t.world_note, t.faction_note, t.weather_note),
                t._ll,
            )
        )


def _story_guard_narrative(t: _StoryTurn) -> None:
    """Pré-validação de eventos, quarentena, sanitização e mediação da narrativa."""
    from services import prose_guard

    t.narrative_text = t.update.narrative
    # Pré-validação read-only das propostas da própria LLM. O processor no
    # archivist continua sendo o único escritor, mas a mensagem visível não
    # pode afirmar como fato uma mudança que ele rejeitará logo depois.
    from services.event_processor import prevalidate_event_batch

    llm_event_proposals = [
        event.model_dump() if hasattr(event, "model_dump") else dict(event)
        for event in (getattr(t.update, "proposed_events", []) or [])
    ]
    t.invalid_story_events = []
    # SPEC-223 (revisão Sol): a pré-validação usa as quests ANTES do progresso
    # deste turno, de propósito: a mesma mensagem que pede a conclusão não pode
    # ser também a sua prova ("Investigo… e marque a missão como concluída").
    # Custo: conclusão proposta no mesmo turno da 1ª evidência vai para
    # quarentena; no turno seguinte passa (medido real: 0/30 turnos).
    preview_state = {
        **t.state,
        "world": t.world,
        "event_log": list(t.state.get("event_log") or []),
    }
    validations = prevalidate_event_batch(llm_event_proposals, preview_state)
    for proposal, validation in zip(llm_event_proposals, validations):
        if not validation.ok:
            t.invalid_story_events.append(
                {
                    "type": str(proposal.get("type") or ""),
                    "target_id": str(proposal.get("target_id") or ""),
                    "reason": str(validation.reason or "")[:240],
                }
            )
    # Política atômica/conservadora: uma proposta inválida põe em quarentena
    # TODO o payload livre da mesma resposta. Mantemos apenas as propostas
    # inválidas na fila para auditoria; propostas irmãs aparentemente válidas
    # não podem virar mudanças silenciosas depois que a narrativa foi descartada.
    t.quarantine_llm_payload = bool(t.invalid_story_events)
    t.pending_llm_events = (
        [
            {
                "type": rejected["type"],
                "target_id": rejected["target_id"],
                "actor_id": "player",
                "payload": {},
                "source": "storyteller_prevalidation",
                "_prevalidation_rejected": True,
                "_prevalidation_reason": rejected["reason"],
            }
            for rejected in t.invalid_story_events
        ]
        if t.quarantine_llm_payload
        else llm_event_proposals
    )
    if not str(t.narrative_text).strip():
        # Fallback digno: o TURNO MECÂNICO sobrevive mesmo com LLM flaky —
        # as notas determinísticas (viagem/descanso/encontro) viram a narração.
        t.narrative_text = _deterministic_story_fallback(
            (t.travel_note, t.rest_note, t.world_note, t.faction_note, t.weather_note),
            t._ll,
        )
    t.narrative_text = prose_guard.sanitize_player_facing(str(t.narrative_text))
    if t.rumor_nothing:
        t.narrative_text = _neutralize_false_find(t.narrative_text)
    t.narrative_text = prose_guard.reconcile_player_gold_claims(
        t.narrative_text, int((t.state.get("player") or {}).get("gold", 0) or 0)
    )
    if t.invalid_story_events:
        # Não há fact-check semântico confiável frase a frase. Em vez de
        # deixar a alegação rejeitada sobreviver, usa somente consequências
        # determinísticas já aplicadas neste turno.
        safe_parts = [note for note in (t.travel_note, t.rest_note, t.faction_note) if note]
        t.narrative_text = (
            _deterministic_story_fallback(safe_parts, t._ll)
            if safe_parts
            else (
                "A tentativa altera apenas o momento imediato; nenhuma mudança "
                "permanente no mundo foi confirmada."
            )
        )
        t.narrative_text += (
            "\n\n[SISTEMA] Uma mudança permanente proposta pela narração "
            "foi rejeitada pelo estado canônico."
        )

    t.narrative_text = prose_guard.vary_repeated_opening(
        str(t.narrative_text),
        t._aberturas,
        salt=t._open_salt,
    )

    # SPEC-202 R11: narração mediada não revela segredo não revelado.
    t.narrative_text, t.mediation_rejections = _guard_mediation_secret(
        str(t.narrative_text), t.scene_state
    )

    # spec polish-prosa (R4): telemetria de abertura repetida (não re-tenta).
    prose_guard.log_if_repeats(
        str(t.narrative_text), t._aberturas[0] if t._aberturas else "", where="storyteller"
    )


def _story_engine_proposals(t: _StoryTurn) -> None:
    """Propostas do motor: faction_deed, crimes (lei) e intenção de vínculo."""
    from services import faction_membership as fm

    # --- SPEC-298 R11: a ação do jogador NÃO altera mais a reputação aqui. O storyteller
    # só enfileira propostas `faction_deed`; o validador exige a fação em cena e o
    # processador (services.reputation) aplica com delta tabelado — ou guarda como
    # pendência até a fação saber (regra de ouro).
    t.rep_events = []
    faction_impacts = (
        [] if t.quarantine_llm_payload else (getattr(t.update, "faction_impacts", []) or [])
    )
    # SPEC-226 R8: 1 impacto por facção/turno (último vence).
    _by_fid: dict = {}
    for imp in faction_impacts:
        _by_fid[getattr(imp, "faction_id", "")] = imp
    for imp in _by_fid.values():
        fid = getattr(imp, "faction_id", "")
        if not fid:
            continue
        t.rep_events.append(
            {
                "type": "faction_deed",
                "actor_id": "player",
                "target_id": fid,
                "payload": {
                    "direction": getattr(imp, "direction", ""),
                    "magnitude": getattr(imp, "magnitude", "menor"),
                    "location_id": (t.world or {}).get("current_location_id", ""),
                },
                "source": "storyteller",
            }
        )

    # --- SPEC-299 R4(a)/R6/R7: crimes classificados pelo LLM; o motor valida e registra.
    # Guard de FallbackLLM: `update` não-StoryUpdate já caiu no except acima (sem claim).
    t.law_updates: dict = {}
    try:
        t.law_updates = _law_mod.apply_claims(
            {**t.state, **t._law_scene_updates, "world": t.world, "npcs": t.scene_npcs},
            getattr(t.update, "crime_claims", []) or [],
            player_text=str(t.last_user_input or ""),
            quarantine=bool(t.quarantine_llm_payload),
        )
    except Exception as exc:  # silent-ok: lei nunca derruba o turno
        _log_event("law", "claims_failed", level="warning", error=type(exc).__name__)
    # --- SPEC-301 R20: intenção de vínculo proposta pelo LLM, validada em Python. ---
    # FallbackLLM/quarentena: campo ignorado. Recusa vira nota narrável, sem estado.
    _member_action = (
        None if t.quarantine_llm_payload else getattr(t.update, "membership_action", None)
    )
    if isinstance(_member_action, MembershipAction) and _member_action.action:
        _intent_note = _fm_apply(
            t, fm.apply_intent(_fm_view(t), _member_action.action, _member_action.faction_id)
        )
        if _intent_note:
            t.fm_post_notes.append(_intent_note)


def _story_system_message(t: _StoryTurn) -> None:
    """Monta o SystemMessage (SPEC-317 compose_prompt)."""
    # SPEC-317 R9: o prompt é montado em pedaços (texto, estático?) — ver prompt_layout.
    _head = f"""
    <PERSONA>
    Você é o Narrador (Mestre) de um RPG.
    Local Atual: {t.loc}.
    Momento: {clock_label(t.world, _cal_of(t.state))}.{t.season_line}
    NPCs na cena: {t.existing_npcs}.
    Objetivo Atual: {t.active_step}
    </PERSONA>

    <EVENTOS_DESTE_TURNO>
    {t.eventos_turno}
    </EVENTOS_DESTE_TURNO>
    {t.ambiente_block}
    {t.mundo_percebido_block}
    {t.ouviu_block}
    {t.hero_state_block}
    {t.companion_block}
    {t.fame_block}
    {t.lei_block}
    {t.faction_member_block}

    <FACÇÕES_CONHECIDAS>
    {t.faccoes_conhecidas}
    Se a ação do jogador NESTE turno claramente ajudar ou prejudicar uma destas fações,
    registre em 'faction_impacts' (faction_id EXATO + direction 'ajudou'/'prejudicou' + magnitude 'menor'/'maior').
    Caso contrário, deixe 'faction_impacts' vazio. NÃO invente ids fora da lista.
    Só se o jogador pediu EXPLICITAMENTE para entrar numa destas fações, sair dela ou pedir
    uma missão a ela, registre em 'membership_action' (join|leave|ask_mission + faction_id
    EXATO); o motor decide se é possível. Não narre a entrada, a saída ou a missão como
    concluídas: o resultado vem do motor.
    </FACÇÕES_CONHECIDAS>

    <ENTIDADES_CANONICAS>
    {t.entidades_canonicas}
    Se — e SÓ se — a ação deste turno causou mudança PERSISTENTE no mundo (morte de
    personagem NOMEADO, segredo revelado, mudança de controle de local), registre em
    'proposed_events' usando os ids EXATOS acima. Na dúvida, deixe vazio. NUNCA invente
    ids fora desta lista.
    </ENTIDADES_CANONICAS>

    <QUESTS_ATIVAS>
    {t.quests_ativas}
    Se um personagem PRESENTE NA CENA ofereceu uma missão concreta ao jogador NESTE
    turno, registre em 'proposed_quests' (origem = quem pediu; location_id só se o
    destino é claro). Se a ação deste turno CONCLUIU uma das quests listadas acima
    COM "prova: ok", proponha em 'proposed_events' um evento type='quest_completed'
    com target_id=quest_id e payload={{"quest_id": quest_id}} usando o id EXATO.
    Quest com "prova: pendente" NÃO pode ser concluída (o motor rejeita): falta ir
    ao local e investigar, ou voltar a quem pediu. Na dúvida, deixe vazio. NUNCA
    invente ids.
    </QUESTS_ATIVAS>
    {t.gancho_novo}

    {t.capacidades_block}

    {t.cast_block_text}{t.pack.world_state_block}
    (Se o ESTADO ATUAL DO MUNDO acima contradisser o lore/fatos passados abaixo, o ESTADO ATUAL VENCE.)

    <MEMORIA_RECENTE>
    Resumo dos fatos anteriores: {t.memoria_recente}
    </MEMORIA_RECENTE>

    <LORE_PUBLICO_CANONICO>
    {t.lore_context}
    </LORE_PUBLICO_CANONICO>

    """
    _rules_a = f"""<INSTRUÇÕES>
    - Responda em 2 a 3 parágrafos.
    - JULGUE a ação: se for implausível para a classe/ficha do personagem ({t.state.get("player", {}).get("class_name", "")})
      ou impossível no contexto, faça-a FALHAR de forma crível na narração (não conceda o impossível).
    - Não afirme como cânone nome, item, facção, local ou evento ausente do ESTADO,
      da MEMÓRIA ou do LORE PÚBLICO acima. Quando faltar base, descreva incerteza
      ou admita que o personagem não sabe; não preencha a lacuna com fato novo.
    - Termine com opções ou pergunta para ação.
    - Se um personagem ENTRAR na cena (novo ou conhecido que reapareceu), adicione o nome em 'introduced_npcs'.
    - Se um personagem conhecido SAIR da cena (foi embora, sumiu), adicione o nome em 'npcs_left_scene'."""
    _rules_b = f"""
    - {PLAYER_INPUT_RULE}
    """
    t.sys = SystemMessage(
        content=compose_prompt(
            [
                (_head, False),
                (_rules_a, True),
                (f"{t.npc_fallback_clause}{t.varie_clause}{t.opcoes_clause}", False),
                (_rules_b, True),
            ]
        )
    )


def _story_beat_and_npcs(t: _StoryTurn) -> None:
    """Beat concluído (XP do motor) e NPCs que entram/saem da cena."""
    from services.turn_outcome import record_gain

    # --- Avanço de beat: o narrador sinaliza quando o objetivo da cena foi cumprido ---
    t.needs_replan = t.travel_needs_replan
    t.updated_plan = t.campaign_plan
    t.beat_done = (
        bool(getattr(t.update, "beat_completed", False))
        and not t.quarantine_llm_payload
        and t.beat_eligible
    )
    # Fase 4.1: beat concluído = XP determinístico (o LLM só sinaliza o beat;
    # valor/level up são do motor). Level ups viram eventos source="progression".
    t.leveled_player = None
    t.level_up_events: list = []
    # Cena de abertura roda com turn_count==1 (campaign_manager incrementa antes):
    # narrador generoso marcando beat no prólogo não pode virar XP grátis na
    # criação (achado do smoke real 2026-07-05). XP de beat só do turno 2 em diante.
    if t.beat_done and int(t.world.get("turn_count", 0) or 0) > 1:
        from progression import XP_PER_BEAT, grant_xp

        # SPEC-226 R3: compõe sobre o jogador já atualizado (descanso/achado).
        t.base_p = (
            t.rested_player
            if t.rested_player is not None
            else t.discovery_player
            if t.discovery_player is not None
            else dict(t.state.get("player") or {})
        )
        t.leveled_player, t.level_up_events = grant_xp(t.base_p, XP_PER_BEAT)
        t.turn_bl = record_gain(t.turn_bl, "xp", XP_PER_BEAT, "beat")
    if t.beat_done:
        t.beats[t.current_step] = {**t.beats[t.current_step], "status": "done"}
        new_step = t.current_step + 1
        t.updated_plan = {**t.campaign_plan, "beats": t.beats, "current_step": new_step}
        # Esgotou os beats → próximo turno o campaign_manager replaneja (vê _should_replan).
        if new_step >= len(t.beats):
            t.needs_replan = True

    # spec npcs-3-camadas (R5): viagem zera a cena (ninguém teleporta junto);
    # introduced_npcs entram em cena; npcs_left_scene saem.
    t.new_npcs = t.scene_npcs
    home_id = t.world.get("current_location_id", "")
    _turn = int(t.world.get("turn_count", 0) or 0)
    introduced_npcs = [] if t.quarantine_llm_payload else (t.update.introduced_npcs or [])
    t._pool_used_new: list = []
    _recent_player_inputs = tuple(
        str(m.content) for m in [m for m in t.messages if isinstance(m, HumanMessage)][-3:]
    )
    npcs_left_scene = (
        [] if t.quarantine_llm_payload else (getattr(t.update, "npcs_left_scene", []) or [])
    )
    for new_name in introduced_npcs:
        t.new_npcs = _with_new_npc(
            t.new_npcs,
            new_name,
            t.loc,
            t.narrative_text,
            game_id=str(t.game_id or ""),
            home_id=home_id,
            turn=_turn,
            cast=t._cast,
            pool_used_out=t._pool_used_new,
            player_inputs=_recent_player_inputs,
            state=t.state,
            stub_only=latency_flags.two_phase_on(),
        )
    for gone_name in npcs_left_scene:
        key = next((k for k in t.new_npcs if k.lower() == str(gone_name).lower()), None)
        if key and isinstance(t.new_npcs.get(key), dict):
            t.new_npcs = {**t.new_npcs, key: {**t.new_npcs[key], "in_scene": False}}


def _story_assemble_base(t: _StoryTurn) -> None:
    """Base do dict de retorno do turno."""
    t.updates = {
        **t.sim_updates,
        "messages": [AIMessage(content=t.narrative_text)],
        "npcs": t.new_npcs,
        "world": t.world,
        "factions": t.factions,
        "campaign_plan": t.updated_plan,
        "needs_replan": t.needs_replan,
    }
    if t._pool_used_new:  # SPEC-297 R24: nunca duas vezes no mesmo jogo
        t.updates["pool_used"] = list(
            dict.fromkeys([*(t.state.get("pool_used") or []), *t._pool_used_new])
        )
    # sinais mostrados + crime novo: o crime parte do estado já com os sinais
    t.updates.update(t._law_scene_updates)
    t.updates.update(t.law_updates)
    for _k, _v in t.fm_extra.items():  # SPEC-301: vínculo/intel/quests parciais
        t.updates[_k] = _v
    # Rumores/cores do simulador são percepção narrativa, não fatos globais.
    # A consequência mecânica aplicada já é persistida diretamente pelo
    # world_simulator; o archivist deve ignorar inferências livres deste texto.
    if t.world_note:
        t.updates["memory_fact_policy"] = "canonical_only"
    if t.rested_player is not None:
        t.updates["player"] = t.rested_player
    elif t.discovery_player is not None:
        t.updates["player"] = t.discovery_player
    if t.leveled_player is not None:  # Fase 4.1: XP do beat (inclui o descanso, se houve)
        t.updates["player"] = t.leveled_player


def _story_assemble_items(t: _StoryTurn) -> None:
    """Itens narrados: só entram os que resolvem no ARTIFACTS_DB."""
    from services import prose_guard

    # Fase 4.3 (R5): item narrado ENTRA no inventário — só se resolver no
    # ARTIFACTS_DB (storyteller não cria item; isso é papel do loot_node).
    gained = [
        g
        for g in ([] if t.quarantine_llm_payload else (getattr(t.update, "items_gained", []) or []))
        if str(g).strip()
    ]
    rejected_claims: list[str] = []
    rejected_item_codes: list[str] = []
    if gained:
        from inventory import add_item, get_qty, is_unique, resolve_item_name
        from services.economy import claim_event, is_unique_available

        proj = t.state.get("world_projection") or {}
        cur_p = dict(t.updates.get("player") or t.state.get("player") or {})
        inv = list(cur_p.get("inventory") or [])
        changed = False
        seen_unique: set[str] = set()
        for g in gained:
            if _is_monetary_claim(g):
                # O valor válido já foi aplicado pela exploração/economia.
                # Texto do provider nunca concede nem rejeita moeda.
                continue
            iid = resolve_item_name(str(g))
            if not iid:
                _log_event("storyteller", "unknown_item_ignored", level="warning")
                rejected_claims.append(str(g))
                rejected_item_codes.append("unknown_item")
                continue
            # Fase 6.2: único já reclamado NUNCA re-entra pela narrativa
            unique = is_unique(iid)
            if unique and iid in seen_unique:
                # Name/ID aliases in one payload represent one grant, not a
                # second rejection that would erase the valid first grant.
                continue
            if unique:
                seen_unique.add(iid)
            if unique and (get_qty(inv, iid) > 0 or not is_unique_available(iid, proj)):
                _log_event(
                    "storyteller", "unique_item_claimed_ignored", level="warning", item_id=iid
                )
                rejected_claims.append(str(g))
                rejected_item_codes.append("unique_claimed")
                _log_event(
                    "economy",
                    "unique_claim_conflict",
                    level="warning",
                    source="narrative",
                    item_id=iid,
                )
                continue
            inv = add_item(inv, iid, 1)
            changed = True
            if unique:
                t.rep_events.append(claim_event(iid, "player"))
        if changed:
            cur_p["inventory"] = inv
            t.updates["player"] = cur_p
    if rejected_item_codes:
        _log_narrative_rejected("item", rejected_item_codes)
    if rejected_claims:
        clean = prose_guard.remove_rejected_claims(t.narrative_text, rejected_claims)
        clean = clean or "A busca não produz nenhum objeto utilizável."
        rejection_note = (
            "Nenhum outro objeto foi acrescentado aos seus pertences."
            if changed
            else "Ao conferir seus pertences, você percebe que nada novo foi obtido."
        )
        clean = f"{clean}\n\n{rejection_note}"
        t.updates["messages"] = [AIMessage(content=clean)]
        t.updates["narrative_rejections"] = [
            f"item_rejected:{name}" for name in dict.fromkeys(rejected_claims)
        ]
        from persistence import normalize_rejected_item_claims

        t.updates["rejected_item_claims"] = normalize_rejected_item_claims(
            [
                *list(t.state.get("rejected_item_claims") or []),
                *rejected_claims,
            ]
        )


def _story_assemble_events(t: _StoryTurn) -> None:
    """Recibo de recompensa, notas do motor, eventos pendentes e morte em armadilha."""
    reward_note = _reward_confirmation(
        t.reward_player_before,
        t.updates.get("player") or t.state.get("player") or {},
    )
    if reward_note:
        current_text = str(t.updates["messages"][0].content or "").rstrip()
        t.updates["messages"] = [AIMessage(content=f"{current_text}\n\n{reward_note}")]
    if t.fm_post_notes:  # SPEC-301: resultado do motor sobre a intenção (entrada/recusa/missão)
        current_text = str(t.updates["messages"][0].content or "").rstrip()
        t.updates["messages"] = [
            AIMessage(content=f"{current_text}\n\n" + "\n".join(t.fm_post_notes))
        ]
    if t.invalid_story_events:
        from services.world_validators import reason_code as _reason_code

        _log_narrative_rejected(
            "event", [_reason_code(e.get("reason")) for e in t.invalid_story_events]
        )
        t.updates["narrative_rejections"] = [
            *list(t.updates.get("narrative_rejections") or []),
            *[
                f"event_rejected:{entry['type']}:{entry['target_id']}"
                for entry in t.invalid_story_events
            ],
        ]
    # Viagem/descanso/beat concluído = evento relevante → pede arquivamento.
    if t.dest or t.rested_player is not None or t.beat_done:
        t.updates["archive_due"] = True
    if t.track_bk is not None:  # Fase 6.4: rastro alimenta o Codex (3.2)
        t.updates["bestiary_knowledge"] = t.track_bk
    # Fase 2.6: enfileira propostas de evento estruturado (motor valida no archivist).
    # Fase 3.4: reputation_changed (Python) entra na mesma fila. 4.1: level_up idem.
    # Fase 6.4: XP de esquiva de armadilha pode ter gerado level_up.
    pending = (
        t.pending_llm_events
        + t.rep_events
        + t.fm_events
        + t.level_up_events
        + t.extra_engine_events
        + t.discovery_events
    )
    if pending:
        t.updates["pending_world_events"] = (
            t.state.get("pending_world_events", []) or []
        ) + pending
        t.updates["archive_due"] = True  # mudança de mundo é evento relevante
    if t.rested_player is not None and t.rested_player.get("dead"):
        t.updates["death_pending"] = True
        t.updates["archive_due"] = True
        t.updates["pending_world_events"] = list(
            t.updates.get("pending_world_events") or t.state.get("pending_world_events", []) or []
        ) + [
            {
                "type": "player_downed",
                "actor_id": "player",
                "target_id": "player",
                "detail": "O herói tombou numa armadilha durante a viagem.",
                "payload": {
                    "location": t.world.get("current_location", ""),
                    "cause": "armadilha",
                },
                "source": "trap",
            }
        ]


def _story_assemble_quests(t: _StoryTurn) -> None:
    """Quests propostas, eventos de quest, rumores e arquivamento baixo."""
    # Fase 3.3: side quests propostas nesta cena (validadas/criadas em Python).
    t.turn = int(t.world.get("turn_count", 0))
    proposed_quests = (
        [] if t.quarantine_llm_payload else (getattr(t.update, "proposed_quests", []) or [])
    )
    # SPEC-313 R6: so o `npc_actor` ancora; `kind` do narrador vira quest comum.
    _downgraded = [
        p for p in proposed_quests if str(getattr(p, "kind", "comum") or "comum") != "comum"
    ]
    if _downgraded:
        from services import lore_quests as _lq2

        _lq2._log("downgraded", kind="storyteller", reason="not_npc", count=len(_downgraded))
    new_quests, created = quest_log.register_proposed_quests(
        t.wq_quests, proposed_quests, turn=t.turn
    )
    new_quests = quest_log.sync_location_progress(
        new_quests,
        str(t.world.get("current_location_id") or ""),
        turn=t.turn,
    )
    new_quests, ready_quest_ids = quest_log.sync_action_progress(
        new_quests,
        str(t.world.get("current_location_id") or ""),
        t.last_user_input,
        turn=t.turn,
    )
    if ready_quest_ids:
        quest_events = [
            {
                "type": "quest_completed",
                "actor_id": "player",
                "target_id": quest_id,
                "detail": "Objetivo concluído por investigação verificável.",
                "payload": {"quest_id": quest_id},
                "source": "system",
            }
            for quest_id in ready_quest_ids
        ]
        t.updates["pending_world_events"] = (
            list(
                t.updates.get("pending_world_events")
                or t.state.get("pending_world_events", [])
                or []
            )
            + quest_events
        )
    if created or t.wq_created or new_quests != list(t.state.get("quests", []) or []):
        t.updates["quests"] = new_quests
        t.updates["archive_due"] = True  # nova missão é evento relevante
    if t.turn_bl is not t.state.get("turn_baseline"):
        t.updates["turn_baseline"] = t.turn_bl
    if t.companion_narrated and t.companion_ack:
        t.updates["companion_voice_ack"] = list(t.companion_ack)
    if t.mediation_rejections:
        _log_narrative_rejected("mediation", ["secret_signature"] * len(t.mediation_rejections))
        t.updates["narrative_rejections"] = [
            *list(t.updates.get("narrative_rejections") or []),
            *t.mediation_rejections,
        ]
    _apply_proposed_rumors(t.state, t.updates, t.update, t.turn, bool(t.quarantine_llm_payload))
    # SPEC-318 R5: viagem dentro da mesma regiao, sem descanso/beat/evento/missao, e baixo valor.
    if (
        latency_flags.archive_low_wanted()
        and t.dest
        and t.rested_player is None
        and not t.beat_done
        and not t.updates.get("pending_world_events")
        and "quests" not in t.updates
        and "memory_canonical_facts" not in t.updates
        and _same_region_travel(t.state, t.world)
    ):
        t.updates["archive_low"] = t.turn


def _story_exception_fallback(t: _StoryTurn) -> dict:
    """Fallback do except: a mecânica já aplicada sobrevive à falha do narrador."""
    fallback = {
        **t.sim_updates,
        "messages": [
            AIMessage(
                content=_deterministic_story_fallback(
                    (t.travel_note, t.rest_note, t.world_note, t.faction_note, t.weather_note),
                    t._ll,
                )
            )
        ],
    }
    if t.dest:
        # viagem mecânica sobrevive ao LLM flaky: mundo anda e a cena esvazia
        from services import npc_layers

        fallback["world"] = t.world
        fallback["needs_replan"] = t.travel_needs_replan
        fallback["npcs"] = npc_layers.reset_scene(t.state.get("npcs", {}))
    # SPEC-233 R8: TODA mecânica já aplicada sobrevive à exceção — o texto não pode
    # prometer descanso/achado que o estado não registra (nem o inverso).
    applied_player = t.rested_player if t.rested_player is not None else t.discovery_player
    if applied_player is not None:
        fallback["player"] = applied_player
    if t._replan_cause:  # SPEC-311 R7: o gatilho do mundo também sobrevive ao fallback
        fallback["needs_replan"] = t.travel_needs_replan
    if t.rumor_find:
        fallback["world"] = t.world
    if t.dest or t.rested_player is not None:
        fallback["world"] = t.world
        fallback["factions"] = t.factions
        fallback["archive_due"] = True
    for _k, _v in t.fm_extra.items():  # SPEC-301: a mecânica já aplicada sobrevive à exceção
        fallback[_k] = _v
    if t.discovery_events or t.extra_engine_events or t.fm_events:
        fallback["pending_world_events"] = (
            (t.state.get("pending_world_events", []) or [])
            + list(t.discovery_events)
            + list(t.extra_engine_events)
            + list(t.fm_events)
        )
    if t.wq_changed:
        fallback["quests"] = t.wq_quests
    if t.turn_bl_pre_llm is not t.state.get("turn_baseline"):
        fallback["turn_baseline"] = t.turn_bl_pre_llm
    if t.track_bk is not None:  # rastro narrado no fallback também chega ao Codex
        fallback["bestiary_knowledge"] = t.track_bk
    if t.rested_player is not None and t.rested_player.get("dead"):
        fallback["death_pending"] = True
        fallback["archive_due"] = True
        fallback["pending_world_events"] = list(
            fallback.get("pending_world_events") or t.state.get("pending_world_events", []) or []
        ) + [
            {
                "type": "player_downed",
                "actor_id": "player",
                "target_id": "player",
                "detail": "O herói tombou numa armadilha durante a viagem.",
                "payload": {
                    "location": t.world.get("current_location", ""),
                    "cause": "armadilha",
                },
                "source": "trap",
            }
        ]
    return fallback
