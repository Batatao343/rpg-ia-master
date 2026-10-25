import { useEffect, useState } from "react";
import { REASSURE_MS, RETRY_MS } from "../turnWait";

export { REASSURE_MS, RETRY_MS };

/** SPEC-320 R3: ms decorridos desde o submit (1 tick/s); zera e para quando `busy=false`. */
export function useTurnClock(busy: boolean): number {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!busy) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- zera o relógio ao fim do turno
      setElapsed(0);
      return;
    }
    const t0 = Date.now();
    setElapsed(0);
    const id = setInterval(() => setElapsed(Date.now() - t0), 1000);
    return () => clearInterval(id);
  }, [busy]);
  return elapsed;
}
