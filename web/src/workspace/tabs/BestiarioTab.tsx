import { CreatureList, usePlayerCodex } from "../../components/CodexTab";
import { ArrivalsProvider } from "../../design/primitives";

/** SPEC-204 R5: Bestiário com os mesmos dados do Codex (`getCodex`, categoria creatures). */
export function BestiarioTab({ gameId, turnCount, open, unavailable }: {
  gameId: string | null | undefined; turnCount: number | undefined; open: boolean; unavailable?: string;
}) {
  const { codex, loading, arrivals } = usePlayerCodex(gameId, turnCount, open && !unavailable);
  return (
    <div>
      <p className="hud__label">Bestiário</p>
      {unavailable ? <p className="combat-empty">{unavailable}</p>
        : loading && !codex ? <p className="combat-empty">Consultando os registros da jornada…</p>
        : <ArrivalsProvider value={arrivals}><CreatureList creatures={codex?.creatures ?? []} /></ArrivalsProvider>}
    </div>
  );
}
