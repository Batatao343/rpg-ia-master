import { useRef } from "react";
import { useModalFocus } from "../workspace/useModalFocus";
import { SHORTCUTS, shortcutKeys, type Platform } from "../workspace/shortcuts";

/** SPEC-324 R4: folha "Atalhos" (tecla `?`). Modal com foco preso (`useModalFocus`); `Esc` fecha e devolve o foco. */
export function ShortcutsSheet({ platform, onClose, deck = false }: { platform: Platform; onClose: () => void; deck?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useModalFocus(ref, onClose);
  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- toque fora fecha; o equivalente de teclado é Esc (useModalFocus)
    <div className="playmenu__scrim" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={ref} className="playmenu shortcuts" role="dialog" aria-modal="true"
        aria-labelledby="shortcuts-title" tabIndex={-1}>
        <p id="shortcuts-title" className="playmenu__title">Atalhos</p>
        <ul className="shortcuts__list">
          {SHORTCUTS.map((s) => (
            <li key={s.id}>
              <kbd className="shortcuts__keys">{shortcutKeys(s.id, platform)}</kbd>
              <span>{s.label}</span>
            </li>
          ))}
        </ul>
        {deck && (
          <section aria-labelledby="shortcuts-deck">
            <p id="shortcuts-deck" className="playmenu__title">No combate com Baralho</p>
            <ul className="shortcuts__list">
              <li><kbd className="shortcuts__keys">1–5</kbd><span>Armar a carta da mão</span></li>
              <li><kbd className="shortcuts__keys">Enter</kbd><span>Encerrar a rodada</span></li>
              <li><kbd className="shortcuts__keys">Esc</kbd><span>Desarmar ou desfazer a fila</span></li>
            </ul>
          </section>
        )}
        <p className="muted shortcuts__note">
          No Linux, Alt+1…8 pode trocar de aba no Chrome/Firefox; no macOS, Ctrl+Option é o modificador do VoiceOver.
        </p>
        <button type="button" className="btn btn--ghost playmenu__item" onClick={onClose}>Fechar</button>
      </div>
    </div>
  );
}
