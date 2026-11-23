// SPEC-427 I2: trava SÍNCRONA do turno em voo. O `busy` do closure de `handleAction` e o `busy` do DOM atrasam em
// relação ao commit do `state` (o efeito da fila e um Enter manual passam pelos dois); esta trava vale no mesmo tick.
let holder = 0;

/** Há um turno em voo (ou prestes a voar) neste tick. */
export function turnLocked(): boolean { return holder !== 0; }
/** O turno `token` assume a trava (chamado de forma síncrona, antes de qualquer `await`). */
export function lockTurn(token: number): void { holder = token; }
/** Solta a trava: sem argumento solta sempre; com `token` só se o turno ainda for o dono. */
export function unlockTurn(token?: number): void { if (token === undefined || holder === token) holder = 0; }
