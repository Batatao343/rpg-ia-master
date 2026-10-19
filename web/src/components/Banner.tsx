import { useEffect } from "react";
import { SupportCode } from "./SupportCode";

export interface BannerState {
  msg: string;
  kind: "error" | "warn";
  /** SPEC-243: request_id do erro; vira "Código de suporte" copiável. */
  requestId?: string;
}

export function Banner({ state, onDone }: { state: BannerState | null; onDone: () => void }) {
  useEffect(() => {
    if (!state) return;
    const ms = state.kind === "warn" ? 9000 : state.requestId ? 15000 : 6000;
    const t = setTimeout(onDone, ms);
    return () => clearTimeout(t);
  }, [state, onDone]);

  if (!state) return null;
  return (
    <div className={"banner" + (state.kind === "warn" ? " is-warn" : "")} role="alert">
      {state.msg}
      {state.requestId ? <> <SupportCode requestId={state.requestId} /></> : null}
    </div>
  );
}
