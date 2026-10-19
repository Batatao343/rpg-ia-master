import { useEffect, useRef, useState } from "react";
import { getDossiers } from "../../api";
import type { DossiersPayload } from "../../types";
import { NO_ARRIVALS } from "../../design/primitives";
import { dossierIds } from "../../dossiers";

/** SPEC-211: dossiês do Codex/Bestiário. Falha => `payload=null` e o chamador cai para
 *  `GET /game/codex` (formato antigo), sem erro bloqueante (§3.4). Refaz a leitura a cada turno. */
export function useDossiers(gameId: string | null | undefined, turnCount: number | undefined, open: boolean) {
  const [state, setState] = useState<{ gameId: string; payload: DossiersPayload } | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  // codex.entry.reveal (M24): ids que chegaram DEPOIS da primeira leitura deste jogo (dado já autorizado).
  const [arrivals, setArrivals] = useState<ReadonlySet<string>>(NO_ARRIVALS);
  const known = useRef<{ gameId: string; ids: Set<string> } | null>(null);
  useEffect(() => {
    if (!open || !gameId) return;
    let active = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    setLoading(true);
    getDossiers(gameId)
      .then((payload) => {
        if (!active) return;
        // Forma inesperada (servidor antigo, proxy, mock) => trata como indisponível (§3.4).
        if (!payload || !payload.sections || !Array.isArray(payload.bestiary)) throw new Error("dossiers shape");
        const ids = dossierIds(payload);
        const prev = known.current?.gameId === gameId ? known.current.ids : null;
        setArrivals(prev ? new Set([...ids].filter((id) => !prev.has(id))) : NO_ARRIVALS);
        known.current = { gameId, ids };
        setState({ gameId, payload });
        setFailed(false);
      })
      .catch(() => { if (active) { setState(null); setFailed(true); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open, gameId, turnCount]);
  // Troca de save nunca mostra dossiê do jogo anterior.
  const payload = state && state.gameId === gameId ? state.payload : null;
  return { payload, loading, failed, arrivals };
}
