import type { CardRewardRequest } from "./api";
import type { ForjaView } from "./types";

/** SPEC-333: resultado de uma ação de espólio/forja (mensagem pt-BR já pronta para o leitor de tela). */
export interface RewardOutcome { ok: boolean; message: string }
export type RewardSender = (request: CardRewardRequest) => Promise<RewardOutcome>;

export const RARITY_LABEL: Record<string, string> = {
  comum: "Comum", incomum: "Incomum", rara: "Rara", abissal: "Abissal",
};

export const refuseLabel = (gold: number) => `Deixar o espólio (+${gold} de ouro)`;

export interface ForgeChoice { via: "descanso" | "templo"; label: string; enabled: boolean }

/** Vias de "Esquecer": o servidor diz quais valem (descanso longo gasto / templo + ouro). */
export function forgetChoices(forja: ForjaView): ForgeChoice[] {
  return [
    { via: "descanso", label: "Esquecer (descanso)", enabled: forja.permitido && forja.esquecer.descanso },
    { via: "templo", label: `Esquecer no templo (${forja.esquecer.ouro} de ouro)`,
      enabled: forja.permitido && forja.esquecer.templo },
  ];
}

/** Via de "Purgar" Cicatriz: Médico de Campo ou templo, ambos por ouro. */
export function purgeChoices(forja: ForjaView): Array<{ via: "templo" | "medico"; label: string; enabled: boolean }> {
  return [
    { via: "medico", label: `Tratar com o Médico (${forja.purgar.ouro} de ouro)`,
      enabled: forja.permitido && forja.purgar.medico },
    { via: "templo", label: `Purgar no templo (${forja.purgar.ouro} de ouro)`,
      enabled: forja.permitido && forja.purgar.templo },
  ];
}

/** A Forja só aparece quando há algo para o jogador fazer ou entender (nunca uma aba vazia). */
export function forgeHasContent(forja: ForjaView | undefined | null): forja is ForjaView {
  return !!forja && (forja.baralho.length > 0 || forja.cicatrizes.length > 0);
}
