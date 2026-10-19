// SPEC-261: build id do bundle (injetado pelo Vite em `define`). Sem define (testes/dev isolado) => "dev".
declare const __RPG_BUILD__: string | undefined;

export const BUILD_ID: string = typeof __RPG_BUILD__ === 'string' && __RPG_BUILD__ ? __RPG_BUILD__ : 'dev';

/** Parte curta (sha de 7 chars ou "dev") para mostrar ao usuario em relatos. */
export function buildShort(): string {
  return BUILD_ID.split('+')[0] || 'dev';
}
