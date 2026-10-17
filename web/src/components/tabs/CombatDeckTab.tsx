import { useMemo, useState, type KeyboardEvent } from "react";
import type { CardView, PlayerStats } from "../../types";
import { DeckCard } from "./DeckCard";
import "./tabs.css";

type TypeFilter = "todas" | "ativa" | "reacao" | "passiva";
const TYPE_FILTERS: Array<[TypeFilter, string]> = [
  ["todas", "Todas"], ["ativa", "Ações"], ["reacao", "Reações"], ["passiva", "Passivas"],
];

/** Mover o foco entre as cartas com as setas (Enter/Espaço preparam — botão nativo). */
function arrowNav(event: KeyboardEvent<HTMLElement>) {
  if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) return;
  const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("[data-deck-card]"));
  const at = items.indexOf(document.activeElement as HTMLElement);
  if (at < 0) return;
  event.preventDefault();
  const step = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1;
  items[(at + step + items.length) % items.length]?.focus();
}

const isPreparable = (c: CardView) => c.type === "ativa" || c.type === "reacao";

/** SPEC-209 R1–R7: deck fora de encontro. Estado canônico = `player_stats`; o cliente guarda só
 *  filtro, mensagem e a lista otimista da preparação (revertida se o servidor recusar). */
export function CombatDeckTab({ stats, busy = false, onPrepare, onOpenLevelUp }: {
  stats: PlayerStats | undefined;
  /** Turno em andamento: o estado canônico pode estar atrasado (R13 "atualizando…"). */
  busy?: boolean;
  onPrepare?: (prepared: string[]) => Promise<string | null>;
  onOpenLevelUp?: () => void;
}) {
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("todas");
  const [sub, setSub] = useState("");
  const [optimistic, setOptimistic] = useState<string[] | null>(null);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const cards = useMemo(() => stats?.cards ?? [], [stats?.cards]);
  const slots = stats?.prepared_slots ?? 0;
  const reorg = stats?.can_reorganize;
  const pending = (stats?.pending_choices?.length ?? 0) > 0;
  const evolvable = new Set(stats?.evolvable_card_ids ?? []);

  const preparedIds = optimistic ?? cards.filter((c) => c.prepared).map((c) => c.id);
  const view = (card: CardView): CardView => (optimistic ? { ...card, prepared: optimistic.includes(card.id) } : card);
  const subclasses = Array.from(new Set(cards.map((c) => c.subclass).filter(Boolean)));
  const matches = (c: CardView) => (typeFilter === "todas" || c.type === typeFilter) && (!sub || c.subclass === sub);

  function blockedFor(card: CardView): string | undefined {
    if (!onPrepare || !reorg) return "somente leitura";
    if (!reorg.allowed) return reorg.reason || "indisponível agora";
    if (busy) return "aguarde a ação em andamento";
    if (saving) return "salvando…";
    if (!card.prepared && preparedIds.length >= slots) return `limite de ${slots} Cartas preparadas`;
    return undefined;
  }

  async function toggle(card: CardView) {
    if (!onPrepare || busy || saving) return;
    const next = preparedIds.includes(card.id) ? preparedIds.filter((id) => id !== card.id) : [...preparedIds, card.id];
    setOptimistic(next);
    setMessage("");
    setSaving(true);
    const error = await onPrepare(next);
    setSaving(false);
    setOptimistic(null); // o estado canônico chegou (ou a mudança foi recusada): volta ao servidor
    setMessage(error ? `Não foi possível preparar: ${error}` : `Preparação atualizada: ${next.length} de ${slots}.`);
  }

  if (!stats) return <p className="combat-empty">Carregando o Acervo…</p>;

  const all = cards.map(view);
  const prepared = all.filter((c) => c.prepared && isPreparable(c));
  const collection = all.filter(matches);
  const permanent: CardView[] = [
    ...cards.filter((c) => c.type === "passiva" || c.type === "virtude"),
    ...(stats.virtue_cards ?? []).map((v): CardView => ({
      id: `virtue:${v.card_id}`, name: v.name, type: v.type || "virtude", description: v.description,
      effect_kind: "", target_kind: "self",
      subclass: v.virtude ? `Virtude ${v.virtude} · estágio ${v.effective_stage}` : "",
      prepared: false, cost: 0, frequency: "livre", spent: false, ready: false, has_rupture: false,
      rupture_ready: false, trigger: "", evolved: null,
    })),
  ];

  return (
    <section className="deck" onKeyDown={arrowNav} aria-label="Acervo e preparação de Cartas">
      <header className="deck__head">
        <h2 className="hud__label">Preparação <span className="muted">{preparedIds.length}/{slots || "—"}</span>
          {(saving || busy) && <span className="deck__sync"> · atualizando…</span>}</h2>
        {/* região viva sempre montada: erro/aplicação anunciados sem role=status */}
        <p className="deck__msg" aria-live="polite">{message}</p>
        {!reorg ? (
          <p className="deck__note">Acervo em modo de leitura: este servidor não permite reorganizar.</p>
        ) : !reorg.allowed ? (
          <p className="deck__note">Reorganização indisponível: {reorg.reason}</p>
        ) : null}
        {pending && onOpenLevelUp && (
          <button type="button" className="deck__levelup" onClick={onOpenLevelUp}>Escolha de nível pendente — abrir</button>
        )}
      </header>

      {cards.length === 0 ? (
        <p className="combat-empty">Nenhuma Carta conhecida ainda. Cartas chegam com os níveis.</p>
      ) : (
        <>
          <ul className="deck__list" aria-label="Cartas preparadas">
            {prepared.length === 0 && <li className="combat-empty">Nada preparado. Escolha Cartas do Acervo abaixo.</li>}
            {prepared.map((card) => (
              <DeckCard key={card.id} card={card} preparable blockedReason={blockedFor(card)}
                evolvable={evolvable.has(card.id) && pending} onEvolve={onOpenLevelUp} onToggle={toggle} />
            ))}
          </ul>

          <h2 className="hud__label">Acervo ({cards.length})</h2>
          <div className="deck__filters" role="group" aria-label="Filtrar Acervo">
            {TYPE_FILTERS.map(([id, label]) => (
              <button key={id} type="button" className="deck__filter" aria-pressed={typeFilter === id}
                onClick={() => setTypeFilter(id)}>{label}</button>
            ))}
            {subclasses.length > 1 && (
              <label className="deck__sub">
                <span className="sr-only">Subclasse</span>
                <select value={sub} onChange={(e) => setSub(e.target.value)} aria-label="Filtrar por subclasse">
                  <option value="">Todas as subclasses</option>
                  {subclasses.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
            )}
          </div>
          <ul className="deck__list" aria-label="Acervo">
            {collection.length === 0 && <li className="combat-empty">Nenhuma Carta neste filtro.</li>}
            {collection.map((card) => (
              <DeckCard key={card.id} card={card} preparable={isPreparable(card)}
                blockedReason={isPreparable(card) ? blockedFor(card) : undefined}
                evolvable={evolvable.has(card.id) && pending} onEvolve={onOpenLevelUp} onToggle={toggle} />
            ))}
          </ul>

          {permanent.length > 0 && (
            <>
              <h2 className="hud__label">Passivas e Reações</h2>
              <ul className="deck__list" aria-label="Passivas e Virtudes">
                {permanent.map((card) => <DeckCard key={card.id} card={card} preparable={false} />)}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}
