// SPEC-345 R9: rótulo do chip de combate. No celular: `R{n}` visível + nome acessível por extenso.
export function fightChipLabel(round: number, mobile: boolean): { visible: string; sr: string } {
  if (!mobile) return { visible: "em combate", sr: "" };
  return { visible: `R${round}`, sr: `Em combate, rodada ${round}` };
}
