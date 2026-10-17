// SPEC-208 R10: kill switch dos efeitos (diagnóstico/suporte). Puro e testável.
export function effectsKilled(search: string, stored: string | null): boolean {
  try {
    const q = new URLSearchParams(search).get("effects");
    if (q === "off") return true;
    if (q === "on") return false;
  } catch { /* ignora */ }
  return stored === "off";
}

/** Lê ambiente e marca <html data-effects="off"> (tokens.css zera animações). Idempotente. */
export function applyKillSwitch(): boolean {
  if (typeof document === "undefined") return false;
  let stored: string | null = null;
  try { stored = window.localStorage.getItem("rpg.effects"); } catch { /* storage bloqueado */ }
  const off = effectsKilled(window.location.search, stored);
  if (off) document.documentElement.dataset.effects = "off";
  else delete document.documentElement.dataset.effects;
  return off;
}
