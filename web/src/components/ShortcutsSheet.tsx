import { useRef } from "react";
import { useModalFocus } from "../workspace/useModalFocus";
import { SHORTCUTS, shortcutKeys, type Platform } from "../workspace/shortcuts";

/** SPEC-324 R4: folha "Atalhos" (tecla `?`). Modal com foco preso (`useModalFocus`); `Esc` fecha e devolve o foco. */
export function ShortcutsSheet({ platform, onClose }: { platform: Platform; onClose: () => void }) {
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
        <p className="muted shortcuts__note">
          No Linux, Alt+1…8 pode trocar de aba no Chrome/Firefox; no macOS, Ctrl+Option é o modificador do VoiceOver.
        </p>
        <button type="button" className="btn btn--ghost playmenu__item" onClick={onClose}>Fechar</button>
      </div>
    </div>
  );
}
