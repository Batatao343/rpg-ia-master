/** SPEC-334 R6: log mecânico colapsável, uma linha por evento, separado da narração (livro). */
export function MechLog({ lines }: { lines: string[] }) {
  if (!lines.length) return null;
  return (
    <details className="mech-log">
      <summary>Números da rodada ({lines.length})</summary>
      <ol>{lines.map((l, i) => <li key={i}>{l}</li>)}</ol>
    </details>
  );
}
