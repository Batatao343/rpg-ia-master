import type { ArtOffer } from "./types";

/** Uma oferta por NPC (mesmo `subject_id`, ou o mesmo `label` quando o servidor não manda o id);
 *  cenas e NPCs sem identificação seguem como vieram. Mantém a primeira de cada NPC. */
export function dedupeOffers(offers: readonly ArtOffer[]): ArtOffer[] {
  const seen = new Set<string>();
  return offers.filter((offer) => {
    const key = offer.type === "npc" ? (offer.subject_id || offer.label) : undefined;
    if (!key) return true;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
