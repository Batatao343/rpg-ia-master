import type { IconName } from "../design/icons";

/** SPEC-347 D-347-H: marcador do inimigo sem imagem = ícone da família (só ícones que já existem na 322). */
export const FAMILY_ICON: Record<string, IconName> = {
  predador: "combat", predador_apice: "unique", bruto: "combat", covarde_oportunista: "exit",
  conjurador: "card-virtue", morto_vivo_implacavel: "death", guardiao: "card-reaction", tatico: "ruler",
  lider_matilha: "quest", emboscador: "dark", abissal: "abyss", desconhecida: "dark",
};

export const familyIcon = (familia: string, icone?: string): IconName =>
  (icone as IconName | undefined) ?? FAMILY_ICON[familia] ?? "dark";
