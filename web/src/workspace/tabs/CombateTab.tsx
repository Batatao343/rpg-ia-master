import type { ActionOptions, GameResponse } from "../../types";
import { CombatTab } from "../../components/Hud";
import { CardHand } from "../../components/CardHand";
import { ReactionPrompt } from "../../components/ReactionPrompt";

const TACTICAL_MANEUVERS = [
  { label: "Engajar", kind: "maneuver" as const, maneuver: "engajar" as const },
  { label: "Guardar", kind: "maneuver" as const, maneuver: "guardar" as const },
  { label: "Esconder-se", kind: "maneuver" as const, maneuver: "esconder" as const },
  { label: "Procurar", kind: "maneuver" as const, maneuver: "procurar" as const },
  { label: "Fugir", kind: "flee" as const },
];

/** SPEC-204 R10: único lugar dos controles táticos (Cartas, Reação, manobras,
 *  Ferimentos, zonas). Lê `data.combat` — sem store paralelo. */
export function CombateTab({ data, busy, blocked, hitKey, ended, reactionCardId, onReaction, onAction }: {
  data: GameResponse | null;
  busy: boolean;
  blocked: boolean;
  hitKey: number;
  /** O combate terminou nesta sessão e o jogador ainda não navegou (D2). */
  ended?: boolean;
  reactionCardId?: string;
  onReaction: (cardId?: string) => void;
  onAction: (text: string, options?: ActionOptions) => void;
}) {
  const combat = data?.combat;
  const fighting = !!combat?.active;
  const simulation = !!data?.combat_simulation?.enabled;
  const live = fighting && !!combat && !blocked;
  const maneuvers = live
    ? (simulation ? [{ label: "Ataque básico", kind: "attack" as const }, ...TACTICAL_MANEUVERS] : TACTICAL_MANEUVERS)
    : [];
  return (
    <div className="ws-combat">
      {!fighting && ended && (
        <p className="ws-combat__ended" role="note">Combate encerrado — o desfecho está na narrativa.</p>
      )}
      {live && combat && (
        <>
          <CardHand cards={combat.cards} enemies={combat.enemies} busy={busy}
            reactionCardId={reactionCardId} onPlay={onAction} />
          <ReactionPrompt cards={combat.cards} selected={reactionCardId} disabled={busy} onSelect={onReaction} />
        </>
      )}
      {maneuvers.length > 0 && (
        <div className="actionchips ws-combat__maneuvers" role="group" aria-label="Manobras táticas">
          {maneuvers.map((maneuver) => (
            <button key={maneuver.label} className="actionchip" type="button" disabled={busy}
              onClick={() => onAction(maneuver.label, {
                action_kind: maneuver.kind,
                maneuver: "maneuver" in maneuver ? maneuver.maneuver : undefined,
                reaction_card_id: reactionCardId,
              })}>
              {maneuver.label}
            </button>
          ))}
        </div>
      )}
      <CombatTab c={combat} hitKey={hitKey} party={data?.party ?? []} />
    </div>
  );
}
