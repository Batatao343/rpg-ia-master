// SPEC-324: atalhos globais do workspace. Tabela única + `matchShortcut` pura (sem DOM, testável).
// Ctrl/⌘+dígito troca de aba do navegador e nunca chega à página; por isso Alt+dígito
// (Windows/Linux) e Ctrl+Option+dígito (macOS, onde Option+dígito gera caractere).
import { CONTEXT_TABS, TAB_LABELS, type ContextTab } from "./workspaceModel";

export type Platform = "mac" | "other";

export type ShortcutId =
  | "composer" | "back" | "forward" | "split" | "help"
  | `tab:${ContextTab}`;

/** Recorte do KeyboardEvent que o matcher lê (assim os testes passam objetos simples). */
export interface KeyLike {
  key: string;
  code?: string;
  altKey?: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
}

interface ShortcutDef {
  id: ShortcutId;
  /** Tecla "física" (KeyboardEvent.code) ou, p/ ?, o `key`. */
  code: string;
  /** Rótulo da tecla final, p/ exibição. */
  glyph: string;
  /** Usa o modificador da plataforma (Alt / Ctrl+Option). Falso = Alt em qualquer SO. */
  platformMod: boolean;
  /** Dispara com o foco num campo de texto? */
  inText: boolean;
  label: string;
}

const DIGITS = ["2", "3", "4", "5", "6"] as const;

export const SHORTCUTS: readonly ShortcutDef[] = [
  { id: "composer", code: "Digit1", glyph: "1", platformMod: true, inText: true, label: "Focar o campo de ação (Crônica)" },
  ...CONTEXT_TABS.map((tab, i): ShortcutDef => ({
    id: `tab:${tab}`, code: `Digit${DIGITS[i]}`, glyph: DIGITS[i], platformMod: true, inText: false,
    label: `Abrir ${TAB_LABELS[tab]}`,
  })),
  { id: "back", code: "ArrowLeft", glyph: "←", platformMod: false, inText: false, label: "Aba anterior do painel" },
  { id: "forward", code: "ArrowRight", glyph: "→", platformMod: false, inText: false, label: "Próxima aba do painel" },
  { id: "split", code: "Backslash", glyph: "\\", platformMod: true, inText: false, label: "Alternar lado a lado" },
  { id: "help", code: "?", glyph: "?", platformMod: false, inText: false, label: "Mostrar esta folha de atalhos" },
];

export function detectPlatform(): Platform {
  if (typeof navigator === "undefined") return "other";
  const hint = (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform
    ?? navigator.platform ?? "";
  return /mac|iphone|ipad/i.test(hint) ? "mac" : "other";
}

function modifiersOk(def: ShortcutDef, e: KeyLike, platform: Platform): boolean {
  if (def.id === "help") return !e.altKey && !e.ctrlKey && !e.metaKey;
  if (e.metaKey || e.shiftKey) return false;
  if (def.platformMod && platform === "mac") return !!e.altKey && !!e.ctrlKey;
  return !!e.altKey && !e.ctrlKey; // Ctrl+Alt no Windows é AltGr: não é atalho
}

/** Devolve o atalho acionado pelo evento, ou null. `typing` = foco em input/textarea/select. */
export function matchShortcut(e: KeyLike, platform: Platform, typing = false): ShortcutId | null {
  for (const def of SHORTCUTS) {
    const hit = def.id === "help" ? e.key === "?" : e.code === def.code;
    if (!hit || !modifiersOk(def, e, platform)) continue;
    if (typing && !def.inText) return null;
    return def.id;
  }
  return null;
}

/** Texto p/ exibir/`title` ("Alt+2", "Ctrl+Option+2", "?"). */
export function shortcutKeys(id: ShortcutId, platform: Platform): string {
  const def = SHORTCUTS.find((s) => s.id === id);
  if (!def) return "";
  if (def.id === "help") return def.glyph;
  const mod = def.platformMod && platform === "mac" ? "Ctrl+Option" : "Alt";
  return `${mod}+${def.glyph}`;
}

/** Valor de `aria-keyshortcuts` (nomes de tecla da WAI-ARIA: Alt, Control). */
export function ariaShortcut(id: ShortcutId, platform: Platform): string {
  const def = SHORTCUTS.find((s) => s.id === id);
  if (!def) return "";
  if (def.id === "help") return "Shift+/";
  const key = def.code === "Backslash" ? "\\" : def.glyph === "←" ? "ArrowLeft" : def.glyph === "→" ? "ArrowRight" : def.glyph;
  return `${def.platformMod && platform === "mac" ? "Control+Alt" : "Alt"}+${key}`;
}

export function titleWithShortcut(text: string, id: ShortcutId, platform: Platform): string {
  return `${text} (${shortcutKeys(id, platform)})`;
}
