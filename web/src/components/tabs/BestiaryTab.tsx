import { CreatureList, usePlayerCodex } from "../CodexTab";
import { ArrivalsProvider } from "../../design/primitives";
import type { CreatureDossier } from "../../types";
import { isProjectionBehind } from "../../dossiers";
import { DossierBrowser } from "./DossierBrowser";
import { useDossiers } from "./useDossiers";

const TIER_ROMAN: Record<number, string> = { 1: "I", 2: "II", 3: "III", 4: "IV" };

/** SPEC-211 R6: Bestiário como dossiês por criatura (tiers 1–4 do servidor). Se o endpoint novo
 *  falhar, cai para o Codex antigo (`CreatureList`) sem erro bloqueante. */
export function BestiaryTab({ gameId, turnCount, open, unavailable }: {
  gameId: string | null | undefined; turnCount: number | undefined; open: boolean; unavailable?: string;
}) {
  const live = open && !unavailable;
  const { payload, loading, failed, arrivals } = useDossiers(gameId, turnCount, live);
  const legacy = usePlayerCodex(gameId, turnCount, live && failed);
  return (
    <div>
      <h3 className="hud__label">Bestiário</h3>
      {unavailable ? <p className="combat-empty">{unavailable}</p>
        : payload && gameId ? (
          <ArrivalsProvider value={arrivals}>
            <DossierBrowser<CreatureDossier>
              gameId={gameId} tabId="bestiary" items={payload.bestiary}
              empty="Nenhuma criatura registrada ainda."
              behind={isProjectionBehind(payload, turnCount)}
              subtitle={(c) => `${c.tier_name}${c.regions?.length ? ` · ${c.regions.join(", ")}` : ""}`}
              lead={(c) => <span className="dossier-seal" title={c.tier_name} aria-hidden="true">{TIER_ROMAN[c.tier]}</span>} />
          </ArrivalsProvider>
        ) : failed ? (
          <ArrivalsProvider value={legacy.arrivals}><CreatureList creatures={legacy.codex?.creatures ?? []} /></ArrivalsProvider>
        ) : loading ? <p className="combat-empty">Consultando os registros da jornada…</p>
        : <p className="combat-empty">Nenhuma criatura registrada ainda.</p>}
    </div>
  );
}
