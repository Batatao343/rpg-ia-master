import { pct, prettyItem } from "../../lib";
import type { GameResponse } from "../../types";
import { Icon } from "../../design/icons";
import { itemIcon, Bar, AbyssChip, type EquipFn } from "./hudParts";

export function FichaTab({ data, hpHitKey, onEquip, busy }: {
  data: GameResponse | null; hpHitKey: number; onEquip?: EquipFn; busy?: boolean;
}) {
  const p = data?.player_stats;
  const vitalityLow = p ? pct(p.vitalidade, p.max_vitalidade) <= 30 : false;
  const cards = p?.cards ?? [];
  return (
    <>
      <div className="bars">
        <Bar kind="hp" label="Vitalidade" cur={p?.vitalidade ?? 0} max={p?.max_vitalidade ?? 0}
             low={vitalityLow} hitKey={hpHitKey} />
        {/* spec refatoracao-sistema-classes: Entropia é o pool das 5 Posturas (SPEC-265: sem barras legadas). */}
        <Bar kind="entropy" label="Entropia" cur={p?.entropy ?? 0} max={p?.max_entropy ?? 0} />
      </div>
      {(p?.max_entropy ?? 0) > 0 && <AbyssChip tier={p?.abyss_tier} charge={p?.abyss_charge ?? 0} />}

      <div className="stats">
        <div className="stat"><span>Nível</span><b>{p?.level ?? 1}/20</b></div>
        <div className="stat">
          <span>XP</span>
          <b>{p?.xp ?? 0}{p?.xp_next_level != null ? ` / ${p.xp_next_level}` : ""}</b>
        </div>
        <div className="stat"><span>Ouro</span><b>{p?.gold ?? 0}</b></div>
        <div className="stat"><span>Defesa</span><b>{p?.defense ?? 0}</b></div>
        {Object.entries(p?.virtudes ?? {}).map(([virtue, value]) => (
          <div className="stat" key={virtue}>
            <span>{prettyItem(virtue)}</span><b>{value}</b>
          </div>
        ))}
      </div>

      {(p?.pending_choices?.length ?? 0) > 0 && (
        <p className="lvlup-hint"><Icon name="levelup" /> Escolha de nível pendente — botão “Nível!” no topo.</p>
      )}

      <div>
        <h3 className="hud__label">Acervo de Cartas</h3>
        <ul className="abilities">
          {cards.length === 0 ? (
            <li className="empty">Nenhuma Carta conhecida</li>
          ) : (
            cards.map((card) => (
              <li key={card.id}>
                {card.name}
                {card.subclass ? ` · ${card.subclass}` : null}
                {card.prepared ? <span className="ability__branch"> <Icon name="prepared" /> preparada</span> : null}
                <span className="ability__kind"> · {card.type}</span>
              </li>
            ))
          )}
        </ul>
      </div>

      <div>
        <h3 className="hud__label">Inventário</h3>
        <ul className="inv">
          {(data?.inventory ?? []).length === 0 ? (
            <li className="empty">Vazio</li>
          ) : (
            data!.inventory.map((it, i) => (
              <li key={`${it.id}-${i}`} className={"inv__item" + (it.equipped ? " is-equipped" : "")}
                  aria-current={it.equipped ? "true" : undefined}>
                <span className={"inv__label" + (it.unique ? " inv__unique" : "")}>
                  <span className="inv__icon"><Icon name={itemIcon(it)} label={it.unique ? "Único" : undefined} /></span>
                  {it.name}
                  {it.qty > 1 ? ` ×${it.qty}` : ""}
                  {it.equipped ? <em className="inv__tag"> equipado</em> : null}
                </span>
                {onEquip && it.slot && !it.equipped && it.id !== "item_desconhecido" && (
                  <button className="inv__equip" disabled={busy}
                          onClick={() => onEquip({ item_id: it.id })}>
                    equipar
                  </button>
                )}
                {onEquip && it.equipped && it.slot && (
                  <button className="inv__equip" disabled={busy}
                          onClick={() => onEquip({ unequip_slot: it.slot! })}>
                    tirar
                  </button>
                )}
              </li>
            ))
          )}
        </ul>
      </div>
    </>
  );
}
