import { useEffect, useRef } from "react";
import { SupportCode } from "./SupportCode";
import { Icon } from "../design/icons";

export interface BannerState {
  msg: string;
  /** error = persiste até o jogador fechar; warn/info somem sozinhos (SPEC-320 R9). */
  kind: "error" | "warn" | "info";
  /** SPEC-243: request_id do erro; vira "Código de suporte" copiável. */
  requestId?: string;
}

export const BANNER_AUTO_DISMISS_MS = 9000;

export function Banner({ state, onDone }: { state: BannerState | null; onDone: () => void }) {
  // Timer chaveado pela identidade da mensagem: re-render com o mesmo `state` não o reinicia.
  const doneRef = useRef(onDone);
  useEffect(() => { doneRef.current = onDone; });
  useEffect(() => {
    if (!state || state.kind === "error") return;
    const t = setTimeout(() => doneRef.current(), BANNER_AUTO_DISMISS_MS);
    return () => clearTimeout(t);
  }, [state]);

  if (!state) return null;
  const isError = state.kind === "error";
  return (
    <div className={"banner" + (state.kind === "warn" ? " is-warn" : state.kind === "info" ? " is-info" : "")}
         role={isError ? "alert" : "status"}>
      <span className="banner__msg">
        {state.msg}
        {state.requestId ? <> <SupportCode requestId={state.requestId} /></> : null}
      </span>
      <button type="button" className="banner__close" aria-label="Fechar aviso" onClick={onDone}><Icon name="close" /></button>
    </div>
  );
}
