// SPEC-364 R19: formatação única de Estilhas (milli → texto) com o plural certo.

/** milli (string|number) → "1.234,5" em Estilhas (sem rótulo). */
export const shards = (milli: string | number | bigint): string => {
  const value = BigInt(milli);
  const whole = new Intl.NumberFormat("pt-BR").format(value / 1000n);
  const fraction = (value % 1000n).toString().padStart(3, "0").replace(/0+$/, "");
  return fraction ? `${whole},${fraction}` : whole;
};

/** "1 Estilha" só para exatamente 1000 milli; qualquer outro valor (inclusive fração) é "N Estilhas". */
export const estilhasLabel = (milli: string | number): string => {
  const value = BigInt(milli);
  return `${shards(value)} ${value === 1000n ? "Estilha" : "Estilhas"}`;
};
