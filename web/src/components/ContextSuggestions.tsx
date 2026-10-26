import { useMemo } from "react";
import type { GameResponse } from "../types";
import { suggestionsFor } from "../contextSuggestions";

/** SPEC-323 R10: um toque PREENCHE o campo (não envia); o texto final passa pelo router normal. */
export function ContextSuggestions({ data, disabled, onPick }: {
  data: GameResponse | null; disabled: boolean; onPick: (text: string) => void;
}) {
  const items = useMemo(() => suggestionsFor(data), [data]);
  if (disabled || items.length === 0) return null;
  return (
    <div className="suggestions" role="group" aria-label="Sugestões de ação">
      {items.map(s => (
        <button key={s.id} type="button" className="placechip" onClick={() => onPick(s.text)}>{s.label}</button>
      ))}
    </div>
  );
}
