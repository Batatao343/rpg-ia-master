// SPEC-363 R16: o tabuleiro fecha no MESMO render em que a resposta traz a morte ou o fim do combate.
export interface BoardStateView {
  death_pending?: boolean;
  game_over?: boolean;
  combat?: { active?: boolean } | null;
}

/** `true` = mão, "Encerrar a rodada" e "Fugir" desabilitados (sem janela de alguns segundos). */
export function boardClosed(data: BoardStateView | null | undefined, blocked = false): boolean {
  if (blocked) return true;
  if (!data) return false;
  if (data.death_pending || data.game_over) return true;
  return data.combat?.active === false;
}
