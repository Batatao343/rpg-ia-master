import { useEffect } from "react";

export interface BannerState {
  msg: string;
  kind: "error" | "warn";
}

export function Banner({ state, onDone }: { state: BannerState | null; onDone: () => void }) {
  useEffect(() => {
    if (!state) return;
    const ms = state.kind === "warn" ? 9000 : 6000;
    const t = setTimeout(onDone, ms);
    return () => clearTimeout(t);
  }, [state, onDone]);

  if (!state) return null;
  return (
    <div className={"banner" + (state.kind === "warn" ? " is-warn" : "")} role="alert">
      {state.msg}
    </div>
  );
}
