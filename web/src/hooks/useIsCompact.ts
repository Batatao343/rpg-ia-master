import { useEffect, useState } from "react";
import { MOBILE_MAX_VIEWPORT } from "../workspace/mobileSurface";

/** `true` abaixo do breakpoint mobile (SPEC-216: < 900 px) — mesma regra do Workspace. */
export function useIsCompact(): boolean {
  const [compact, setCompact] = useState(() => typeof window !== "undefined" && window.innerWidth < MOBILE_MAX_VIEWPORT);
  useEffect(() => {
    const update = () => setCompact(window.innerWidth < MOBILE_MAX_VIEWPORT);
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return compact;
}
