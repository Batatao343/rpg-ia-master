import { useEffect, useMemo, useRef, useState } from "react";
import type { ActionOptions, BasicActionView, CardView, GameResponse } from "../../types";
import { CombatTab } from "../../components/Hud";
import { CombatDeckTab } from "../../components/tabs/CombatDeckTab";
import { CardHand } from "../../components/CardHand";
import { DeckCombat } from "../../components/combat/DeckCombat";
import { ReactionPrompt } from "../../components/ReactionPrompt";
import { CombatOutcomePanel } from "../../components/CombatOutcomePanel";
import { EspolioPanel } from "../../components/combat/EspolioPanel";
import { ForjaPanel } from "../../components/combat/ForjaPanel";
import { forgeHasContent, type RewardSender } from "../../cardRewards";
import { resultFrom, shouldShowResult } from "../../combatOutcome";
import { Arena, buildParticipants } from "../../combat/Arena";
import { CardTooltip } from "../../combat/CardTooltip";
import type { AimMark } from "../../combat/TargetChip";
import {
  basicKey, basicPayload, BASIC_LABEL, cardPayload, planBasic, planCard, REASON_TEXT,
} from "../../combat/targeting";
import { useTargeting } from "../../combat/useTargeting";
import { objectChips, orderChips, reinforcementNote } from "../../combat/conflictChips";

const DETAIL_ID = "combat-card-detail";

/** Servidor antigo (sem `basic_actions`): mesmas manobras de antes + ataque básico. */
function legacyBasics(enemyIds: string[]): BasicActionView[] {
  const row = (kind: BasicActionView["kind"], maneuver?: BasicActionView["maneuver"], targets: string[] = []): BasicActionView =>
    ({ kind, maneuver, valid_targets: targets, invalid_reason: null, cost: 0 });
  return [row("attack", undefined, enemyIds), row("maneuver", "engajar", enemyIds), row("maneuver", "guardar"),
    row("maneuver", "esconder"), row("maneuver", "procurar", enemyIds), row("flee")];
}

/** SPEC-334 R7: no modo Baralho as manobras ficam atrás de um toque (poucos controles à vista). */
function ManeuverFold({ deck, children }: { deck: boolean; children: React.ReactNode }) {
  if (!deck) return <>{children}</>;
  return <details className="ws-combat__fold"><summary>Manobras e ações</summary>{children}</details>;
}

const isTyping = (el: EventTarget | null) => {
  const node = el as HTMLElement | null;
  return !!node && (node.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(node.tagName));
};

/** SPEC-204 R10 + SPEC-205: único lugar dos controles táticos. Uma ação por gesto:
 *  carta/ação básica → (alvo) → envio. Todos os números vêm de `data.combat`. */
/** SPEC-325 R9: o servidor reconhece esta frase (regex fechada em death_flow.NONLETHAL_RE). */
const SPARE_TEXT = "Sem matar.";
/** SPEC-325 R12/R13: frases que o servidor reconhece (combat_intents.abandon_target / accepts_sacrifice). */
const ABANDON_TEXT = (name: string) => `Fujo e deixo ${name} para trás.`;
const SACRIFICE_TEXT = "Aceito o sacrifício.";
export function CombateTab({ data, busy, blocked, hitKey, ended, touch = false, reactionCardId, onReaction, onAction, onPrepareCards, onCardReward, onOpenLevelUp, dismissedResult, onDismissResult }: {
  data: GameResponse | null;
  busy: boolean;
  blocked: boolean;
  hitKey: number;
  /** O combate terminou nesta sessão e o jogador ainda não navegou (D2). */
  ended?: boolean;
  /** SPEC-216: toque — "Cancelar mira" no lugar de Esc e "Detalhes" no lugar de hover. */
  touch?: boolean;
  reactionCardId?: string;
  onReaction: (cardId?: string) => void;
  onAction: (text: string, options?: ActionOptions) => void;
  /** SPEC-209: preparar Cartas fora de encontro; devolve a mensagem de erro (ou null). */
  onPrepareCards?: (prepared: string[]) => Promise<string | null>;
  /** SPEC-333: espólio de Cartas e Forja do baralho (só quando a API trouxer os blocos). */
  onCardReward?: RewardSender;
  onOpenLevelUp?: () => void;
  /** SPEC-212: dispensa controlada pelo PlayScreen (sequencia o modal de nível); sem props = local. */
  dismissedResult?: string | null;
  onDismissResult?: (resultEventId: string) => void;
}) {
  const combat = data?.combat;
  const [localDismissed, setLocalDismissed] = useState<string | null>(null);
  const controlled = !!onDismissResult;
  const dismissed = controlled ? (dismissedResult ?? null) : localDismissed;
  const dismissResult = (id: string) => (controlled ? onDismissResult!(id) : setLocalDismissed(id));
  const combatResult = resultFrom(data?.combat_result);
  const fighting = !!combat?.active;
  const live = fighting && !!combat && !blocked;

  const resetKey = `${combat?.round ?? ""}|${combat?.active}|${blocked}|${data?.game_id ?? ""}`;
  const targeting = useTargeting(busy, resetKey);
  const [ruptureId, setRuptureId] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [announce, setAnnounce] = useState("");
  const [spare, setSpare] = useState(false); // SPEC-325: golpe não-letal ("Sem matar")
  const rootRef = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const prevPhase = useRef(targeting.state.phase);

  const spareOn = spare && !!combat?.nonlethal_available; // flag saiu de `on` -> ignora
  const cards = combat?.cards ?? [];
  const enemies = combat?.enemies ?? [];
  const people = useMemo(() => (combat ? buildParticipants(combat, data?.party ?? []) : []), [combat, data?.party]);
  const nameOf = (id: string) => people.find((p) => p.id === id)?.name;
  const basics = combat ? (combat.basic_actions ?? legacyBasics(enemies.map((e) => e.id))) : [];
  const activeCards = cards.filter((c) => c.type === "ativa");
  const deckMode = !!combat?.pilhas; // SPEC-334: sem `pilhas` (flag off) a UI atual segue idêntica
  const espolio = data?.player_stats?.espolio_pendente; // SPEC-333: só com RPG_CARD_REWARDS=on
  const forja = data?.player_stats?.forja;

  const state = targeting.state;
  const aimingCard: CardView | undefined = state.phase === "aiming" && state.source.kind === "card"
    ? activeCards.find((c) => c.id === (state.source as { cardId: string }).cardId) : undefined;
  const sourceKey = state.phase === "aiming" && state.source.kind === "basic" ? state.source.key : null;
  const aimingBasic = sourceKey ? basics.find((a) => basicKey(a) === sourceKey) : undefined;

  const aimTargets: string[] | null = aimingCard
    ? planCard(aimingCard, enemies, false).targets
    : aimingBasic ? planBasic(aimingBasic, false).targets : null;
  const aimMarks: Record<string, AimMark> | undefined = aimTargets ? Object.fromEntries(people.map((p) => {
    const valid = aimTargets.includes(p.id);
    const supportCard = aimingCard?.target_kind === "self";
    const reason = valid ? undefined
      : p.role === "enemy" ? (supportCard ? "Esta carta só mira você e aliados" : "Oculto ou fora de alcance")
      : "Esta ação só mira inimigos";
    return [p.id, { valid, reason }];
  })) : undefined;

  const aimLabel = aimingCard ? aimingCard.name : aimingBasic ? BASIC_LABEL[basicKey(aimingBasic)] : "";

  // Foco e anúncio: entra na mira → 1º alvo válido; sai sem enviar → volta ao gatilho.
  useEffect(() => {
    const before = prevPhase.current;
    prevPhase.current = state.phase;
    if (state.phase === "aiming") {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
      setAnnounce(`Mirando ${aimLabel}: escolha um alvo.`);
      rootRef.current?.querySelector<HTMLElement>("button[data-target].is-valid")?.focus();
    } else if (before === "aiming" && state.phase === "idle") {
      setAnnounce("Mira cancelada.");
      trigger.current?.focus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.phase]);

  const lastResult = combat?.last_player_action?.result;
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    if (combat?.round && lastResult) setAnnounce(`Resultado da rodada ${combat.round}: ${lastResult}.`);
  }, [combat?.round, lastResult]);

  function sendCard(card: CardView, targetId: string | undefined) {
    if (!targeting.begin()) return;
    const [text, options] = cardPayload(card, targetId, targetId ? nameOf(targetId) : undefined,
      ruptureId === card.id, reactionCardId);
    setRuptureId(null);
    onAction(spareOn ? `${text} ${SPARE_TEXT}` : text, options);
    setSpare(false); // vale só para o próximo golpe
  }

  function sendBasic(action: BasicActionView, targetId: string | undefined) {
    if (!targeting.begin()) return;
    const [text, options] = basicPayload(action, targetId, targetId ? nameOf(targetId) : undefined, reactionCardId);
    onAction(spareOn && action.kind === "attack" ? `${text} ${SPARE_TEXT}` : text, options);
    if (action.kind === "attack") setSpare(false);
  }

  function gestureCard(card: CardView, el?: HTMLElement) {
    if (el) trigger.current = el;
    const plan = planCard(card, enemies, busy);
    if (plan.mode === "blocked") { setAnnounce(plan.reason ? `${card.name}: ${REASON_TEXT[plan.reason]}.` : ""); return; }
    if (plan.mode === "direct") {
      if (!targeting.beginDirect()) return;
      const [text, options] = cardPayload(card, plan.directTarget, plan.directTarget ? nameOf(plan.directTarget) : undefined,
        ruptureId === card.id, reactionCardId);
      setRuptureId(null);
      onAction(text, options);
      return;
    }
    targeting.aim({ kind: "card", cardId: card.id });
  }

  function gestureBasic(action: BasicActionView, el?: HTMLElement) {
    if (el) trigger.current = el;
    const plan = planBasic(action, busy);
    if (plan.mode === "blocked") { setAnnounce(plan.reason ? `${BASIC_LABEL[basicKey(action)]}: ${REASON_TEXT[plan.reason]}.` : ""); return; }
    if (plan.mode === "direct") {
      if (!targeting.beginDirect()) return;
      const [text, options] = basicPayload(action, plan.directTarget, plan.directTarget ? nameOf(plan.directTarget) : undefined, reactionCardId);
      onAction(text, options);
      return;
    }
    targeting.aim({ kind: "basic", key: basicKey(action) });
  }

  function pick(targetId: string) {
    if (aimingCard) sendCard(aimingCard, targetId);
    else if (aimingBasic) sendBasic(aimingBasic, targetId);
  }

  // Atalhos 1–9 para a mão (P2): opcionais, ignorados ao digitar.
  useEffect(() => {
    if (!live || deckMode) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey || isTyping(event.target)) return;
      if (!/^[1-9]$/.test(event.key)) return;
      const card = activeCards[Number(event.key) - 1];
      if (card) {
        event.preventDefault();
        gestureCard(card, rootRef.current?.querySelector<HTMLElement>(`[data-card="${card.id}"]`) ?? undefined);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const detailCard = cards.find((c) => c.id === (detailId ?? aimingCard?.id)) ?? null;
  const locked = busy || state.phase === "submitting";

  return (
    <div className="ws-combat" ref={rootRef}>
      <p className="sr-only" aria-live="polite">{announce}</p>
      {combatResult && shouldShowResult(combatResult, dismissed) && (
        <CombatOutcomePanel result={combatResult} outcome={data?.turn_outcome}
          onContinue={() => dismissResult(combatResult.result_event_id)} />
      )}
      {!fighting && onCardReward && espolio && (
        <EspolioPanel espolio={espolio} busy={busy} onChoose={onCardReward} />
      )}
      {!fighting && ended && (
        <p className="ws-combat__ended" role="note">Combate encerrado — o desfecho está na narrativa.</p>
      )}
      {live && combat && (
        <>
          <Arena combat={combat} party={data?.party ?? []} aim={aimMarks} onPick={pick} />
          {deckMode && state.phase === "aiming" && (
            <div className="aimbar" data-aim-safe>
              <span>{`Mirando ${aimLabel}: escolha um alvo`}</span>
              <button type="button" className="aimbar__cancel" onClick={() => targeting.cancel()}>{touch ? "Cancelar mira" : "Cancelar (Esc)"}</button>
            </div>
          )}
          {deckMode ? (
            <DeckCombat combat={combat} gameId={data?.game_id ?? null} entropy={data?.player_stats?.entropy ?? null}
              busy={locked} touch={touch} nameOf={nameOf} onAnnounce={setAnnounce}
              onEnd={(text, jogadas) => { if (targeting.beginDirect()) onAction(text, { jogadas, reaction_card_id: reactionCardId }); }} />
          ) : (
            <>
              <div className="aimbar" data-aim-safe>
                <span>{state.phase === "aiming" ? `Mirando ${aimLabel}: escolha um alvo`
                  : state.phase === "submitting" ? "Enviando…" : "Escolha uma carta ou ação"}</span>
                {state.phase === "aiming" && (
                  <button type="button" className="aimbar__cancel" onClick={() => targeting.cancel()}>{touch ? "Cancelar mira" : "Cancelar (Esc)"}</button>
                )}
              </div>
              <CardHand cards={cards} enemies={enemies} busy={locked}
                aimingCardId={aimingCard?.id} ruptureId={ruptureId} detailId={DETAIL_ID}
                onToggleRupture={(id) => setRuptureId((cur) => (cur === id ? null : id))}
                onGesture={gestureCard} onDetail={setDetailId} touch={touch} detailOpenId={detailId} />
              <CardTooltip card={detailCard} id={DETAIL_ID} touch={touch} />
            </>
          )}
          {reinforcementNote(combat) && (
            <p className="ws-combat__ended" role="note">{reinforcementNote(combat)}</p>
          )}
          <ReactionPrompt cards={cards} selected={reactionCardId} disabled={busy} onSelect={onReaction} />
          <ManeuverFold deck={deckMode}>
          <div className="actionchips ws-combat__maneuvers" role="group" aria-label="Manobras táticas" data-aim-safe>
            {basics.map((action) => {
              const key = basicKey(action);
              const plan = planBasic(action, locked);
              const reason = plan.reason ? REASON_TEXT[plan.reason] : undefined;
              return (
                <button key={key} className="actionchip" type="button" data-basic={key}
                  aria-pressed={sourceKey === key}
                  aria-disabled={plan.mode === "blocked" || undefined} title={reason}
                  onClick={(event) => { if (plan.mode !== "blocked" || sourceKey === key) gestureBasic(action, event.currentTarget); }}>
                  {BASIC_LABEL[key] ?? key}
                </button>
              );
            })}
            {combat?.nonlethal_available && (
              <button className="actionchip" type="button" data-spare aria-pressed={spare}
                title="O próximo golpe derruba o alvo sem matá-lo (se a forma do ataque permitir)."
                onClick={() => setSpare((v) => !v)}>
                Sem matar
              </button>
            )}
            {combat?.chase?.abandon_candidates?.map((c) => (
              <button key={`abandon-${c.id}`} className="actionchip" type="button" data-abandon={c.id}
                disabled={locked}
                title="Foge deixando o companheiro para trás. O destino dele só se revela depois."
                onClick={() => { if (targeting.beginDirect()) onAction(ABANDON_TEXT(c.name)); }}>
                Deixar {c.name}
              </button>
            ))}
            {objectChips(combat).map((c) => (
              <button key={c.key} className="actionchip" type="button" data-object={c.data}
                disabled={locked} title={c.title}
                onClick={() => { if (targeting.beginDirect()) onAction(c.text); }}>
                {c.label}
              </button>
            ))}
            {orderChips(combat).map((c) => (
              <button key={c.key} className="actionchip" type="button" data-order={c.data}
                disabled={locked} title={c.title}
                onClick={() => { if (targeting.beginDirect()) onAction(c.text); }}>
                {c.label}
              </button>
            ))}
            {combat?.chase?.sacrifice_offer && (
              <button className="actionchip" type="button" data-sacrifice disabled={locked}
                title="Aceita que o companheiro fique para segurar os perseguidores. Recusar não tem custo: é só fugir."
                onClick={() => { if (targeting.beginDirect()) onAction(SACRIFICE_TEXT); }}>
                Aceitar sacrifício de {combat.chase.sacrifice_offer.name}
              </button>
            )}
          </div>
          </ManeuverFold>
        </>
      )}
      {!fighting && !data?.combat_simulation?.enabled && (
        <CombatDeckTab stats={data?.player_stats} busy={busy} onPrepare={onPrepareCards} onOpenLevelUp={onOpenLevelUp} />
      )}
      {!fighting && !data?.combat_simulation?.enabled && onCardReward && forgeHasContent(forja) && (
        <ForjaPanel forja={forja} cards={data?.player_stats?.cards ?? []} busy={busy} onForge={onCardReward} />
      )}
      <CombatTab c={combat} hitKey={hitKey} party={data?.party ?? []} arena={live} />
    </div>
  );
}
