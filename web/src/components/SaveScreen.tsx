import { useRef, useState } from "react";
import type { SaveSummary } from "../types";
import * as api from "../api";
import { AUDIT_EXPORT_NOTICE, exportWithReauth } from "../lib/auditExport";
import { Frame, Divider, Medallion } from "./ornaments";

// spec polish-sessao (R3): tela "Continuar jornada" — lista campanhas salvas
// com Continuar / Excluir (confirmação com o nome do herói) / Nova jornada.
interface Props {
  saves: SaveSummary[];
  busy: boolean;
  onContinue: (gameId: string) => void;
  onDelete: (gameId: string) => void;
  onNew: () => void;
  onSimulate: () => void;
  /** SPEC-207: só nos perfis com conta (prova recente + owner). */
  auditExport?: boolean;
}

type AuditPhase = "confirm" | "password" | "busy";

export function SaveScreen({ saves, busy, onContinue, onDelete, onNew, onSimulate, auditExport = false }: Props) {
  const [confirming, setConfirming] = useState<SaveSummary | null>(null);
  const [auditing, setAuditing] = useState<SaveSummary | null>(null);
  const [auditPhase, setAuditPhase] = useState<AuditPhase>("confirm");
  const [auditPassword, setAuditPassword] = useState("");
  const [auditMessage, setAuditMessage] = useState("");
  const passwordResolver = useRef<((value: string | null) => void) | null>(null);

  function closeAudit() {
    passwordResolver.current?.(null);
    passwordResolver.current = null;
    setAuditing(null); setAuditPassword(""); setAuditPhase("confirm"); setAuditMessage("");
  }

  async function runAudit(save: SaveSummary) {
    setAuditPhase("busy"); setAuditMessage("");
    const result = await exportWithReauth(save.game_id, {
      exportGame: api.exportGameAudit,
      reauthenticate: (password) => api.reauthenticate(password),
      askPassword: () => new Promise<string | null>((resolve) => {
        passwordResolver.current = resolve;
        setAuditPhase("password");
      }),
    });
    passwordResolver.current = null;
    setAuditPassword("");
    if (result.status === "ok") {
      const url = URL.createObjectURL(result.blob);
      const link = document.createElement("a");
      link.href = url; link.download = "valoria-auditoria.zip";
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      setAuditPhase("confirm"); setAuditMessage("Pacote de auditoria pronto para download.");
    } else if (result.status === "error") {
      setAuditPhase("confirm"); setAuditMessage(result.message);
    } else {
      setAuditPhase("confirm");
    }
  }

  return (
    <main className="create saves-screen">
      <Frame className="create__frame">
        <div className="create__seal"><Medallion size={48} /></div>
        <h1 className="create__title">Continuar jornada</h1>
        <Divider />
        <ul className="savelist">
          {saves.map((s) => (
            <li key={s.game_id} className={"savecard" + (s.game_over ? " is-memorial" : "")}>
              <button
                className="savecard__main"
                type="button"
                disabled={busy}
                onClick={() => onContinue(s.game_id)}
              >
                <span className="savecard__name">
                  {s.name}
                  {s.game_over && <span className="savecard__badge">⚰ memorial</span>}
                  {s.combat_simulation && <span className="savecard__badge savecard__badge--lab">⚔ laboratório</span>}
                </span>
                <span className="savecard__meta">
                  {s.class_name} · nível {s.level}
                </span>
                <span className="savecard__meta">
                  {s.location} — dia {s.day}
                </span>
              </button>
              {auditExport && (
                <button
                  className="iconbtn savecard__audit"
                  type="button"
                  disabled={busy}
                  aria-label={"Exportar sessão de " + s.name + " para auditoria"}
                  title="Exportar sessão para auditoria"
                  onClick={() => { setAuditing(s); setAuditPhase("confirm"); setAuditMessage(""); }}
                >
                  ⇩
                </button>
              )}
              <button
                className="iconbtn savecard__del"
                type="button"
                disabled={busy}
                aria-label={"Excluir a jornada de " + s.name}
                onClick={() => setConfirming(s)}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
        <Divider />
        <button className="btn btn--primary" type="button" disabled={busy} onClick={onNew}>
          Nova jornada
        </button>
        <button className="btn btn--ghost" type="button" disabled={busy} onClick={onSimulate}>
          Simular combate
        </button>
      </Frame>

      {auditing && (
        <div className="overlay" role="dialog" aria-modal="true" aria-labelledby="audit-export-title">
          <div className="overlay__inner">
            <p className="overlay__big" id="audit-export-title">Exportar sessão para auditoria</p>
            <p className="muted">{AUDIT_EXPORT_NOTICE}</p>
            {auditPhase === "password" ? (
              <form onSubmit={(event) => {
                event.preventDefault();
                if (!auditPassword) return;
                const resolve = passwordResolver.current;
                passwordResolver.current = null;
                setAuditPhase("busy");
                resolve?.(auditPassword);
              }}>
                <label htmlFor="audit-export-password">Confirme sua senha</label>
                <input id="audit-export-password" type="password" autoComplete="current-password"
                  value={auditPassword} onChange={(event) => setAuditPassword(event.target.value)} />
                <div className="savecard__confirm">
                  <button className="btn btn--primary" type="submit" disabled={!auditPassword}>Confirmar</button>
                  <button className="btn" type="button" onClick={closeAudit}>Cancelar</button>
                </div>
              </form>
            ) : (
              <div className="savecard__confirm">
                <button className="btn btn--primary" type="button" disabled={auditPhase === "busy"}
                  onClick={() => void runAudit(auditing)}>
                  {auditPhase === "busy" ? "Gerando…" : "Exportar " + auditing.name}
                </button>
                <button className="btn" type="button" disabled={auditPhase === "busy"} onClick={closeAudit}>
                  Fechar
                </button>
              </div>
            )}
            <p aria-live="polite">{auditMessage}</p>
          </div>
        </div>
      )}

      {confirming && (
        <div className="overlay">
          <div className="overlay__inner">
            <p className="overlay__big">Apagar esta saga?</p>
            <p className="muted">
              A jornada de <strong>{confirming.name}</strong> será perdida para sempre —
              crônica, feitos e memórias.
            </p>
            <div className="savecard__confirm">
              <button
                className="btn btn--danger"
                type="button"
                disabled={busy}
                onClick={() => {
                  onDelete(confirming.game_id);
                  setConfirming(null);
                }}
              >
                Apagar {confirming.name}
              </button>
              <button className="btn" type="button" onClick={() => setConfirming(null)}>
                Manter
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
