import type { CardRewardRequest } from "./api";
import type { ForjaView, LojaOferta } from "./types";

/** SPEC-333: resultado de uma ação de espólio/forja (mensagem pt-BR já pronta para o leitor de tela). */
export interface RewardOutcome { ok: boolean; message: string }
export type RewardSender = (request: CardRewardRequest) => Promise<RewardOutcome>;

export const RARITY_LABEL: Record<string, string> = {
  comum: "Comum", incomum: "Incomum", rara: "Rara", abissal: "Abissal",
};

export const refuseLabel = (gold: number) => `Deixar o espólio (+${gold} de ouro)`;

/** `why` = por que a via está fechada (texto do servidor, SPEC-347 R7); `null` quando aberta. */
export interface ForgeChoice { via: "descanso" | "templo"; label: string; enabled: boolean; why?: string | null }

/** Vias de "Esquecer": o servidor diz quais valem (descanso longo gasto / templo + ouro). */
export function forgetChoices(forja: ForjaView): ForgeChoice[] {
  return [
    { via: "descanso", label: "Esquecer (descanso)", enabled: forja.permitido && forja.esquecer.descanso,
      why: forja.esquecer.motivos?.descanso ?? null },
    { via: "templo", label: `Esquecer no templo (${forja.esquecer.ouro} de ouro)`,
      enabled: forja.permitido && forja.esquecer.templo, why: forja.esquecer.motivos?.templo ?? null },
  ];
}

/** Via de "Purgar" Cicatriz: Médico de Campo ou templo, ambos por ouro. */
export function purgeChoices(forja: ForjaView): Array<{ via: "templo" | "medico"; label: string; enabled: boolean; why?: string | null }> {
  return [
    { via: "medico", label: `Tratar com o Médico (${forja.purgar.ouro} de ouro)`,
      enabled: forja.permitido && forja.purgar.medico, why: forja.purgar.motivos?.medico ?? null },
    { via: "templo", label: `Purgar no templo (${forja.purgar.ouro} de ouro)`,
      enabled: forja.permitido && forja.purgar.templo, why: forja.purgar.motivos?.templo ?? null },
  ];
}

/** A Forja só aparece quando há algo para o jogador fazer ou entender (nunca uma aba vazia). */
export function forgeHasContent(forja: ForjaView | undefined | null): forja is ForjaView {
  return !!forja && (forja.baralho.length > 0 || forja.cicatrizes.length > 0);
}

/** SPEC-357 R14: rótulo do destino previsto da Carta comprada (vem do servidor). */
export const DESTINO_LABEL: Record<string, string> = {
  baralho: "vai para o Baralho",
  acervo: "só para o Acervo",
  preparadas: "vai para as Preparadas",
};

/** SPEC-363 R32: texto do destino previsto; "Baralho cheio" só quando o motivo é esse. */
export const ACERVO_MOTIVO_LABEL: Record<string, string> = {
  baralho_cheio: "só para o Acervo — Baralho cheio",
  limite_de_copias: "só para o Acervo — limite de cópias no Baralho",
  preparadas_cheias: "só para o Acervo — Preparadas cheias",
  passiva_permanente: "só para o Acervo — sempre ativa: não ocupa Preparação",
  sem_baralho: "só para o Acervo — o Baralho se forma no primeiro combate",
};

export function destinoLabel(destino: string, motivo?: string | null): string {
  if (destino === "acervo") return (motivo && ACERVO_MOTIVO_LABEL[motivo]) || "só para o Acervo";
  return DESTINO_LABEL[destino] ?? destino;
}

/** SPEC-363 R33: cabeçalho do Acervo. Com `baralho` fala de Baralho; sem ele, "Preparação N/M" como antes. */
export function acervoHeader(
  baralho: { total: number; maximo: number } | undefined | null,
  prepared: number,
  slots: number,
): { title: string; count: string; updated: (n: number) => string } {
  if (baralho) {
    return {
      title: "Baralho",
      count: `${baralho.total}/${baralho.maximo}`,
      updated: () => `Baralho atualizado: ${baralho.total} de ${baralho.maximo}.`,
    };
  }
  return {
    title: "Preparação",
    count: `${prepared}/${slots || "—"}`,
    updated: (n) => `Preparação atualizada: ${n} de ${slots}.`,
  };
}

/** Estado do botão "Comprar": desabilitado com o texto de `bloqueio` do servidor. */
export function shopOfferState(oferta: LojaOferta): { enabled: boolean; label: string } {
  if (oferta.conhecida) return { enabled: false, label: oferta.bloqueio || "Você já conhece essa Carta." };
  if (oferta.bloqueio) return { enabled: false, label: oferta.bloqueio };
  return { enabled: true, label: `Comprar por ${oferta.preco} de ouro` };
}
