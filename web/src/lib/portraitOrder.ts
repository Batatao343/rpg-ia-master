// SPEC-352 R12: regras puras do pedido de retrato pago de inimigo (testáveis sem DOM).

/** O "Gerar" inline já foi o consentimento: confirma direto só se a cotação real NÃO passa do preço mostrado. */
export function withinShownPrice(creditsMilli: string, shownShards: number): boolean {
  try {
    return BigInt(creditsMilli) <= BigInt(Math.max(0, Math.floor(shownShards))) * 1000n;
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
