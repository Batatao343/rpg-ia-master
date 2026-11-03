// SPEC-352 R12: regras puras do pedido de retrato pago de inimigo (testáveis sem DOM).

/** O "Gerar" inline já foi o consentimento: confirma direto só se a cotação real NÃO passa do preço mostrado. */
export function withinShownPrice(creditsMilli: string, shownShards: number, shownMilli?: string): boolean {
  try {
    // SPEC-364 R20: com o teto exato (milli) a regra é em milli; sem ele, a de hoje (inteiro × 1000).
    const ceiling = shownMilli ? BigInt(shownMilli) : BigInt(Math.max(0, Math.floor(shownShards))) * 1000n;
    return BigInt(creditsMilli) <= ceiling;
  } catch {
    return false;
  }
}

export interface PortraitBanner { msg: string; kind: "info" | "warn" }

/** Mensagem do aviso para a falha de cotação/confirmação do retrato (nada é cobrado em nenhum destes casos). */
export function portraitErrorBanner(status: number | undefined, code: string | undefined, fallback: string): PortraitBanner {
  if (status === 409 && (code === "creature_portrait_in_progress" || code === "creature_portrait_exists")) {
    return { msg: "Outro jogador já está gerando este retrato. Ele aparece em breve, sem custo.", kind: "info" };
  }
  if (status === 409 && code === "creature_portrait_curated") {
    return { msg: "Este retrato já existe no bestiário.", kind: "info" };
  }
  if (status === 409 && code === "creature_portrait_not_offered") {
    return { msg: "Esta criatura não tem retrato disponível para geração.", kind: "info" };
  }
  if (status === 402) return { msg: "Estilhas insuficientes.", kind: "warn" };
  if (status === 503) return { msg: "Geração de imagem indisponível agora.", kind: "warn" };
  return { msg: fallback, kind: "warn" };
}

/** SPEC-363 R4: a cotação recusou (503) — esconde a oferta DAQUELE inimigo até o próximo estado do servidor. */
export function shouldHidePortraitOffer(status: number | undefined, code: string | undefined): boolean {
  if (status === 409 && code === "creature_portrait_not_offered") return true; // SPEC-367 R11
  return status === 503 && (code === "image_generation_disabled" || code === "image_pricing_unavailable" || code === undefined);
}

interface WithEnemies { combat?: { enemies?: Array<{ id: string; retrato?: { gerar?: unknown } | null }> } | null }

/** Devolve o estado sem `retrato.gerar` do inimigo (imutável; mesmo objeto se nada muda). */
export function withoutPortraitOffer<T extends WithEnemies>(data: T, enemyId: string): T {
  const enemies = data.combat?.enemies;
  if (!enemies || !enemies.some((e) => e.id === enemyId && e.retrato?.gerar)) return data;
  return {
    ...data,
    combat: {
      ...data.combat,
      enemies: enemies.map((e) => (e.id === enemyId && e.retrato ? { ...e, retrato: { ...e.retrato, gerar: null } } : e)),
    },
  };
}

interface PendingEnemy { id: string; name?: string; retrato?: { estado?: string; gerar?: { escopo?: string } | null } | null }
interface WithPendingEnemies { combat?: { enemies?: PendingEnemy[] } | null }

const baseName = (name: string | undefined) => (name ?? "").replace(/\s+\d+$/, "").trim().toLowerCase();

function pendingHit(data: WithPendingEnemies, enemyId: string): ((e: PendingEnemy) => boolean) | null {
  const clicked = data.combat?.enemies?.find((e) => e.id === enemyId);
  if (!clicked) return null;
  const sameType = (e: PendingEnemy) =>
    clicked.retrato?.gerar?.escopo === "tipo" && e.retrato?.gerar?.escopo === "tipo" && baseName(e.name) === baseName(clicked.name);
  return (e) => !!e.retrato?.gerar && (e.id === enemyId || sameType(e));
}

/** SPEC-387 R8: o `retrato` ANTERIOR (por id) dos inimigos que `withPortraitPending` vai trocar. */
export function snapshotPortraits(data: WithPendingEnemies, enemyId: string): Record<string, unknown> {
  const hit = pendingHit(data, enemyId);
  const out: Record<string, unknown> = {};
  for (const e of data.combat?.enemies ?? []) if (hit?.(e)) out[e.id] = e.retrato;
  return out;
}

/** SPEC-387 R8: erro/cancelamento — devolve o `retrato` guardado dos inimigos ainda "gerando" por este pedido.
 *  Imutável; o mesmo objeto quando nada muda (inimigo sumiu ou o servidor já trouxe outro estado). */
export function withPortraitRestored<T extends WithPendingEnemies>(data: T, _enemyId: string, snapshot: Record<string, unknown>): T {
  const enemies = data.combat?.enemies;
  if (!enemies || !enemies.some((e) => e.id in snapshot && e.retrato?.estado === "gerando" && !e.retrato?.gerar)) return data;
  return {
    ...data,
    combat: {
      ...data.combat,
      enemies: enemies.map((e) => (e.id in snapshot && e.retrato?.estado === "gerando" && !e.retrato?.gerar
        ? { ...e, retrato: snapshot[e.id] as PendingEnemy["retrato"] } : e)),
    },
  };
}

/** SPEC-367 R4: a confirmação deu certo — o inimigo clicado (e os de mesmo tipo, escopo "tipo") passam a
 *  "gerando" e perdem a oferta. Imutável; devolve o mesmo objeto quando nada muda. */
export function withPortraitPending<T extends WithPendingEnemies>(data: T, enemyId: string): T {
  const enemies = data.combat?.enemies;
  const hit = pendingHit(data, enemyId);
  if (!enemies || !hit || !enemies.some(hit)) return data;
  return {
    ...data,
    combat: {
      ...data.combat,
      enemies: enemies.map((e) => (hit(e) && e.retrato ? { ...e, retrato: { ...e.retrato, estado: "gerando", gerar: null } } : e)),
    },
  };
}
