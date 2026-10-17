// SPEC-211: helpers puros dos dossiês (testados em Node). Sem React, sem rede.
// `version` vem do servidor (= last_updated_turn); o cliente NUNCA a calcula (R1/R8).

export type DossierMarker = "new" | "updated" | null;

/** id -> última `version` vista pelo viewer (preferência de visualização, §3.3). */
export type SeenMap = Record<string, number>;

export interface Versioned { id: string; version: number }

/** "Novo" = id ausente da última visita; "Atualizado" = versão maior. */
export function markerFor(item: Versioned, seen: SeenMap): DossierMarker {
  const prev = seen[item.id];
  if (prev === undefined) return "new";
  return item.version > prev ? "updated" : null;
}

export const MARKER_LABEL: Record<Exclude<DossierMarker, null>, string> = {
  new: "Novo",
  updated: "Atualizado",
};

/** Contagem agregada SÓ de dossiês já visíveis (nunca de categorias bloqueadas). */
export function markedCount(items: Versioned[], seen: SeenMap): number {
  return items.reduce((n, item) => n + (markerFor(item, seen) ? 1 : 0), 0);
}

export function seenKey(gameId: string, tab: string): string {
  return `rpg.dossier.seen.${gameId}.${tab}`;
}

export function openKey(gameId: string, tab: string): string {
  return `rpg.dossier.open.${gameId}.${tab}`;
}

interface StorageLike {
  get(key: string): string | null;
  set(key: string, value: string): unknown;
}

/** Lê o mapa com try/catch; qualquer falha => vazio (tudo "novo", render correto). */
export function loadSeen(store: StorageLike, gameId: string, tab: string): SeenMap {
  try {
    const raw = store.get(seenKey(gameId, tab));
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const out: SeenMap = {};
    for (const [id, version] of Object.entries(parsed)) {
      if (typeof version === "number" && Number.isFinite(version)) out[id] = version;
    }
    return out;
  } catch {
    return {};
  }
}

export function saveSeen(store: StorageLike, gameId: string, tab: string, seen: SeenMap): void {
  try { store.set(seenKey(gameId, tab), JSON.stringify(seen)); } catch { /* conveniência */ }
}

/** Marca um dossiê como visto na versão atual (nunca regride a versão). */
export function withSeen(seen: SeenMap, item: Versioned): SeenMap {
  const prev = seen[item.id];
  return prev !== undefined && prev >= item.version ? seen : { ...seen, [item.id]: item.version };
}

/** Projeção atrasada (SPEC-213): `version` do payload < turno atual => "atualizando…". */
export function isProjectionBehind(payload: { generated_at_turn: number }, currentTurn: number | undefined): boolean {
  return typeof currentTurn === "number" && payload.generated_at_turn < currentTurn;
}

/** Ids (`dos:<id>`) de todos os dossiês do payload, p/ detectar chegadas entre leituras. */
export function dossierIds(payload: {
  sections: { npcs: Versioned[]; locations: Versioned[]; factions: Versioned[]; secrets: Versioned[] };
  bestiary: Versioned[];
}): Set<string> {
  const out = new Set<string>();
  const { npcs, locations, factions, secrets } = payload.sections;
  for (const item of [...npcs, ...locations, ...factions, ...secrets, ...payload.bestiary]) out.add(`dos:${item.id}`);
  return out;
}
