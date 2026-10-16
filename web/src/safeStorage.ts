// SPEC-235 R6: localStorage that never throws. Blocked/denied/quota storage falls
// back to an in-memory Map for the lifetime of the tab.
const memory = new Map<string, string>();

function store(): Storage | null {
  try { return typeof localStorage === 'undefined' ? null : localStorage; } catch { return null; }
}

export const safeStorage = {
  get(key: string): string | null {
    try { const v = store()?.getItem(key); if (v != null) return v; } catch { /* blocked */ }
    return memory.get(key) ?? null;
  },
  /** Returns true when the value reached durable storage; false when kept in memory only. */
  set(key: string, value: string): boolean {
    try {
      const s = store();
      if (s) { s.setItem(key, value); memory.delete(key); return true; }
    } catch { /* blocked or quota */ }
    memory.set(key, value);
    return false;
  },
  remove(key: string): void {
    memory.delete(key);
    try { store()?.removeItem(key); } catch { /* blocked */ }
  },
  keys(): string[] {
    const out = new Set<string>(memory.keys());
    try {
      const s = store();
      if (s) for (let i = 0; i < s.length; i++) { const k = s.key(i); if (k) out.add(k); }
    } catch { /* blocked */ }
    return [...out];
  },
};
