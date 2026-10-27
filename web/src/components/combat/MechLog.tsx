/** SPEC-334 R6 + SPEC-342 R23: log mecânico da última rodada, separado da narração (livro).
 *  Cada linha: o ator (trecho antes do 1º " · ") em rótulo e o resto em números tabulares. */
export function MechLog({ lines, round }: { lines: string[]; round: number }) {
  if (!lines.length) return null;
  return (
    <details className="mech-log">
      <summary>Os dados da rodada {round}</summary>
      <ol>
        {lines.map((l, i) => {
          const at = l.indexOf(" · ");
          return at < 0 ? <li key={i}>{l}</li> : (
            <li key={i}><span className="mech-log__who">{l.slice(0, at)}</span><span className="mech-log__rest"> · {l.slice(at + 3)}</span></li>
          );
        })}
      </ol>
    </details>
  );
}
