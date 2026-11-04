import { createContext, useContext } from "react";
import type { RewardSender } from "../cardRewards";

/** Ações de jogo que o `App` entrega às abas (SPEC-383 R2). O valor padrão (`{}`) mantém componentes
 *  renderizados fora do app sem esses botões, como quando a prop faltava. */
export type GameActions = {
  onEquip?: (pick: { item_id?: string; unequip_slot?: string }) => void;
  onPrepareCards?: (prepared: string[]) => Promise<string | null>;
  onCardReward?: RewardSender;
  /** SPEC-352 R12: pedir o retrato pago de um inimigo (id da instância, preço mostrado em Estilhas). */
  onGeneratePortrait?: (enemyId: string, priceShards: number, priceMilli?: string) => void;
};

export const GameActionsContext = createContext<GameActions>({});
export const GameActionsProvider = GameActionsContext.Provider;
export const useGameActionsContext = (): GameActions => useContext(GameActionsContext);
