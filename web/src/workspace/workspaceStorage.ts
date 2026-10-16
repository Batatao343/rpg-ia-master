// SPEC-204 R9: layout por owner+save. Nunca grava rascunho nem histórico.
import { safeStorage } from "../safeStorage";
import { DEFAULT_WORKSPACE, isContextTab, type WorkspaceState } from "./workspaceModel";

const PREFIX = "valoria:workspace:v1:";
const key = (owner: string, game: string) => PREFIX + owner + ":" + game;

export function loadWorkspace(owner: string, game: string): WorkspaceState | null {
  try {
    const raw = safeStorage.get(key(owner, game));
    if (!raw) return null;
    const row = JSON.parse(raw);
    if (!row || row.version !== 1) return null;
    if (!["chat", "split", "context"].includes(row.mode)) return null;
    if (typeof row.ratio !== "number" || !Number.isFinite(row.ratio) || row.ratio <= 0 || row.ratio >= 1) return null;
    if (!isContextTab(row.tab)) return null;
    if (row.lastSolo !== "chat" && row.lastSolo !== "context") return null;
    return { ...DEFAULT_WORKSPACE, mode: row.mode, ratio: row.ratio, tab: row.tab,
      lastSolo: row.lastSolo, history: [row.tab], cursor: 0 };
  } catch {
    return null;
  }
}

export function saveWorkspace(owner: string, game: string, s: WorkspaceState): void {
  try {
    safeStorage.set(key(owner, game), JSON.stringify({
      version: 1, mode: s.mode, ratio: s.ratio, tab: s.tab, lastSolo: s.lastSolo,
    }));
  } catch { /* storage indisponível: layout segue só em memória */ }
}

export function clearWorkspaceOwner(owner: string): void {
  try {
    safeStorage.keys().filter(k => k.startsWith(PREFIX + owner + ":")).forEach(k => safeStorage.remove(k));
  } catch { /* storage indisponível */ }
}
