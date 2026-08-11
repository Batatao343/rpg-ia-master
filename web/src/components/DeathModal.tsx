import { motion } from "motion/react";
import type { DeathView } from "../types";

interface Props {
  busy: boolean;
  onContinue: () => void;
  onAccept: () => void;
  death?: DeathView;
}

/** spec checkpoints-morte (D2): a queda letal abre a escolha — voltar ao último
 *  checkpoint (a saga segue, perdendo o progresso desde ali) ou aceitar o fim
 *  (memorial: a crônica encerra). O memorial nunca é imposto; é decisão do jogador. */
export function DeathModal({ busy, onContinue, onAccept, death }: Props) {
  const action = death?.last_action;
  const lastAction = action?.kind === "card"
    ? `Carta ${death?.last_action_label || action.card_id || "desconhecida"}`
    : action?.kind ? action.kind.replace(/_/g, " ") : "não registrada";
  return (
    <div className="overlay overlay--death" role="dialog" aria-modal="true">
      <motion.div
        className="death-card"
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="death-card__sigil" aria-hidden>☠</div>
        <h2 className="death-card__title">Você tombou</h2>
        <p className="death-card__body">
          A escuridão te engole — mas a Roda do Abismo ainda não decidiu. Voltar ao
          último respiro seguro, ou aceitar o fim aqui?
        </p>
        <dl className="death-card__ledger">
          <div><dt>Última ação</dt><dd>{lastAction}</dd></div>
          <div><dt>Estado Terminal</dt><dd>{death?.entered_terminal ? "atravessado" : "não registrado"}</dd></div>
          <div><dt>Estabilização</dt><dd>{death?.stabilization || `${death?.stabilization_attempts ?? 0} tentativa(s)`}</dd></div>
          {death?.killer && <div><dt>Queda diante de</dt><dd>{death.killer}</dd></div>}
        </dl>
        <div className="death-card__actions">
          <button
            type="button"
            className="death-btn death-btn--continue"
            disabled={busy}
            onClick={onContinue}
          >
            Continuar do checkpoint
          </button>
          <button
            type="button"
            className="death-btn death-btn--accept"
            disabled={busy}
            onClick={onAccept}
          >
            Aceitar a morte
          </button>
        </div>
        <p className="death-card__note">
          Continuar reverte ao último ponto seguro — o progresso desde ali se perde.
        </p>
      </motion.div>
    </div>
  );
}
