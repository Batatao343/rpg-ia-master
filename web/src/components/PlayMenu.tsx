import { useRef, useState } from "react";
import { shards } from "./AccountScreen";
import { useModalFocus } from "../workspace/useModalFocus";

/** SPEC-321 R2: menu "⋯" da cabeça única no celular — Conta (com saldo), Nova jornada, Sair e Laboratório.
 *  Folha modal com foco preso (`useModalFocus`), `Esc` fecha e o foco volta ao botão. */
export function PlayMenu({ busy, simulation, accountBalance, onAccount, onNew, onLogout }: {
  busy: boolean;
  simulation: boolean;
  accountBalance?: string | null;
  onAccount?: () => void;
  /** Já passa pela confirmação de saída quando há turno em andamento (PlayScreen). */
  onNew: () => void;
  onLogout?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <>
      <button type="button" className="iconbtn playmenu__trigger" aria-haspopup="dialog" aria-expanded={open}
        aria-label="Menu" onClick={() => setOpen(true)}>
        <span aria-hidden>⋯</span>
      </button>
      {open && (
        <PlayMenuSheet onClose={close}>
          {simulation && <p className="laboratory-flag playmenu__flag">Laboratório</p>}
          {onAccount && (
            <button type="button" className="btn playmenu__item" disabled={busy}
              onClick={() => { close(); onAccount(); }}>
              Conta{accountBalance != null ? ` · ${shards(accountBalance)} Estilhas` : ""}
            </button>
          )}
          <button type="button" className="btn playmenu__item" disabled={busy}
            onClick={() => { close(); onNew(); }}>
            {simulation ? "Reiniciar" : "Nova jornada"}
          </button>
          {onLogout && (
            <button type="button" className="btn btn--ghost playmenu__item" disabled={busy}
              onClick={() => { close(); onLogout(); }} aria-label="Encerrar sessão">
              Sair
            </button>
          )}
          <button type="button" className="btn btn--ghost playmenu__item playmenu__close" onClick={close}>
            Fechar
          </button>
        </PlayMenuSheet>
      )}
    </>
  );
}

function PlayMenuSheet({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useModalFocus(ref, onClose);
  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- toque fora fecha; o equivalente de teclado é Esc (useModalFocus)
    <div className="playmenu__scrim" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={ref} className="playmenu" role="dialog" aria-modal="true" aria-label="Menu da partida" tabIndex={-1}>
        {children}
      </div>
    </div>
  );
}

/** SPEC-321 R3: "Nova jornada" com turno/ação pendente não salva pede confirmação antes de sair. */
export function ConfirmNewDialog({ simulation, onCancel, onConfirm }: {
  simulation: boolean; onCancel: () => void; onConfirm: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useModalFocus(ref, onCancel);
  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- toque fora fecha; o equivalente de teclado é Esc (useModalFocus)
    <div className="playmenu__scrim" onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div ref={ref} className="playmenu playmenu--confirm" role="alertdialog" aria-modal="true"
        aria-labelledby="confirm-new-title" aria-describedby="confirm-new-desc" tabIndex={-1}>
        <p id="confirm-new-title" className="playmenu__title">{simulation ? "Reiniciar a simulação?" : "Sair desta jornada?"}</p>
        <p id="confirm-new-desc" className="muted">
          Há uma ação em andamento ou ainda não confirmada. O que já foi salvo continua na lista de jornadas;
          a ação pendente será abandonada.
        </p>
        <button type="button" className="btn btn--primary playmenu__item" onClick={onCancel}>Continuar aqui</button>
        <button type="button" className="btn btn--ghost playmenu__item" onClick={onConfirm}>
          {simulation ? "Reiniciar" : "Nova jornada"}
        </button>
      </div>
    </div>
  );
}
