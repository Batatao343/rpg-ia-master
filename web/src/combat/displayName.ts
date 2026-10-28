// SPEC-354 R9: o front nunca mostra um id cru ("npc_ketil") onde cabe um nome exibível.
import type { GameResponse, PartyMember } from "../types";

const ID_RE = /^[a-z][a-z0-9]*(_[a-z0-9]+)+$/;
const PREFIX_RE = /^(npc|enemy|ally|bst|party|companion)_/;
const norm = (s: string) => s.trim().toLowerCase();

/** Parece um id técnico (snake_case) ou é igual ao próprio `participant_id`. */
export function looksLikeId(text: string, id?: string): boolean {
  const t = text.trim();
  if (!t) return false;
  return ID_RE.test(t) || (id != null && id !== "" && t === id && /_/.test(t));
}

/** "npc_ketil" → "Ketil"; "enemy_goblin_2" → "Goblin 2" (último recurso). */
export function humanizeId(id: string): string {
  const base = id.trim().replace(PREFIX_RE, "").replace(/_r\d+$/, "");
  const words = base.split("_").filter(Boolean).map((w) => (/^\d+$/.test(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)));
  return words.join(" ") || id;
}

interface Ctx { party?: PartyMember[]; npcs?: GameResponse["npcs"]; labels?: Map<string, string> }

/** Nome exibível: `raw` quando é um nome de verdade; senão o grupo, os NPCs conhecidos, o rótulo da espécie e,
 *  por fim, o id humanizado. */
export function displayName(raw: string | null | undefined, id: string, ctx: Ctx = {}): string {
  const text = (raw ?? "").trim();
  if (text && !looksLikeId(text, id)) return text;
  const guess = norm(humanizeId(id).replace(/\s+\d+$/, ""));
  const hit = (name: string) => { const n = norm(name); return n === guess || n.startsWith(guess + " ") || n.split(/\s+/)[0] === guess; };
  const member = ctx.party?.find((m) => hit(m.name));
  if (member) return member.name;
  const npc = ctx.npcs?.find((n) => hit(n.name));
  if (npc) return npc.name;
  const label = ctx.labels?.get(id);
  if (label && !looksLikeId(label, id)) return label;
  return humanizeId(id);
}
