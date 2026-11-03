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
  if (status === 402) return { msg: "Estilhas insuficientes.", kind: "warn" };
  if (status === 503) return { msg: "Geração de imagem indisponível agora.", kind: "warn" };
  return { msg: fallback, kind: "warn" };
}

/** SPEC-363 R4: a cotação recusou (503) — esconde a oferta DAQUELE inimigo até o próximo estado do servidor. */
export function shouldHidePortraitOffer(status: number | undefined, code: string | undefined): boolean {
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

/** SPEC-367 R4: a confirmação deu certo — o inimigo clicado (e os de mesmo tipo, escopo "tipo") passam a
 *  "gerando" e perdem a oferta. Imutável; devolve o mesmo objeto quando nada muda. */
export function withPortraitPending<T extends WithPendingEnemies>(data: T, enemyId: string): T {
  const enemies = data.combat?.enemies;
  const clicked = enemies?.find((e) => e.id === enemyId);
  if (!enemies || !clicked) return data;
  const sameType = (e: PendingEnemy) =>
    clicked.retrato?.gerar?.escopo === "tipo" && e.retrato?.gerar?.escopo === "tipo" && baseName(e.name) === baseName(clicked.name);
  const hit = (e: PendingEnemy) => !!e.retrato?.gerar && (e.id === enemyId || sameType(e));
  if (!enemies.some(hit)) return data;
  return {
    ...data,
    combat: {
      ...data.combat,
      enemies: enemies.map((e) => (hit(e) && e.retrato ? { ...e, retrato: { ...e.retrato, estado: "gerando", gerar: null } } : e)),
    },
  };
}
