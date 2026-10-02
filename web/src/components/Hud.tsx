import { useEffect, useRef, useState } from "react";
import { GeneratedPortrait } from './GeneratedPortrait';
import { mdLite, pct, prettyItem } from "../lib";
import { searchChronicle } from "../api";
import type { ChronicleChapter, ChronicleSearchHit, CombatBlock, Condition, FactionView, GameResponse, NpcView } from "../types";
import { CodexTab } from "./CodexTab";
import { QuestsTab } from "./QuestsTab";
import { WorldMap } from "./WorldMap";
import { Medallion } from "./ornaments";
import { SceneZones } from "./SceneZones";
import { WoundTrack } from "./WoundTrack";

type Tab = "ficha" | "combate" | "personagens" | "mapa" | "faccoes" | "missoes" | "cronica" | "codex";

type EquipFn = (pick: { item_id?: string; unequip_slot?: string }) => void;

export function Hud({ data, open, onEquip, busy, onTravel, onClose }: {
  data: GameResponse | null; open: boolean; onEquip?: EquipFn; busy?: boolean;
  onTravel?: (locationName: string) => void;
  onClose?: () => void;
}) {
  const p = data?.player_stats;
  const sub = [p?.class_name, p?.race].filter(Boolean).join(" · ") || "—";
  const fighting = !!data?.combat?.active;

  const [tab, setTab] = useState<Tab>("ficha");

  // auto-troca: entra na luta → Combate; sai da luta → Ficha.
  const wasFighting = useRef(false);
  useEffect(() => {
    if (fighting && !wasFighting.current) setTab("combate");
    if (!fighting && wasFighting.current) setTab("ficha");
    wasFighting.current = fighting;
  }, [fighting]);

  // ênfase de dano: queda de Vitalidade do herói entre turnos.
  const prevVitality = useRef<number | null>(null);
  const [vitalityHit, setVitalityHit] = useState(0);
  useEffect(() => {
    const vitality = p?.vitalidade;
    if (vitality == null) return;
    if (prevVitality.current != null && vitality < prevVitality.current) {
      setVitalityHit((n) => n + 1);
    }
    prevVitality.current = vitality;
  }, [p?.vitalidade]);

  const tabs: Array<[Tab, string]> = [
    ["ficha", "Ficha"],
    ["combate", "Combate"],
    ["personagens", "Pessoas"],
    ["mapa", "Mapa"],
    ["faccoes", "Fações"],
    ["missoes", "Missões"],
    ["cronica", "Crônica"],
    ["codex", "Codex"],
  ];

  return (
    <aside className={"hud" + (open ? " is-open" : "")} aria-label="Ficha do personagem">
      <div className="hud__head">
        <span className="hud__medallion"><Medallion size={36} /></span>
        <div className="hud__id">
          <p className="hud__name">{p?.name || "—"}</p>
          <p className="hud__sub">{sub}</p>
        </div>
        {onClose && <button type="button" className="hud__close iconbtn"
          aria-label="Fechar ficha" onClick={onClose}>×</button>}
      </div>

      <nav className="tabs" role="tablist">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            className={
              "tab" +
              (tab === id ? " is-active" : "") +
              (id === "combate" ? " is-combat" + (fighting ? " has-fight" : "") : "")
            }
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="tabpanel" role="tabpanel" tabIndex={0}>
        {tab === 'ficha' && data?.portrait_generation_id && <GeneratedPortrait
          key={`${data.game_id}:${data.portrait_generation_id}`}
          gameId={data.game_id} generationId={data.portrait_generation_id} />}
        {tab === "ficha" && <FichaTab data={data} hpHitKey={vitalityHit} onEquip={onEquip} busy={busy} />}
        {tab === "combate" && <CombatTab c={data?.combat} hitKey={vitalityHit} party={data?.party ?? []} />}
        {tab === "personagens" && <PeopleTab npcs={data?.npcs ?? []} />}
        {tab === "mapa" && (
          <div>
            <p className="hud__label">Mapa do mundo</p>
            <WorldMap
              visited={data?.world.visited ?? []}
              currentId={data?.world.location_id ?? ""}
              controlled={data?.world.controlled ?? {}}
              dangerOverrides={data?.world.danger_overrides ?? {}}
              markers={data?.quest.markers ?? []}
              overlays={data?.world.map_overlays}
              currentTurn={data?.world.turn_count ?? 0}
              blockedRoutes={data?.world.blocked_routes ?? []}
              onTravel={(location) => onTravel?.(location.name)}
            />
          </div>
        )}
        {tab === "faccoes" && <FactionsTab factions={data?.factions ?? []} />}
        {tab === "missoes" && <QuestsTab quest={data?.quest} />}
        {tab === "cronica" && (
          <ChronicleTab chapters={data?.chronicle ?? []} gameId={data?.game_id} />
        )}
        {tab === "codex" && (
          <CodexTab gameId={data?.game_id} turnCount={data?.world.turn_count} open={tab === "codex"} />
        )}
      </div>
    </aside>
  );
}

function FichaTab({ data, hpHitKey, onEquip, busy }: {
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
        {/* spec refatoracao-sistema-classes: Entropia é o pool das 5 Posturas.
            Saves antigos sem Entropia (mana/stamina) mantêm as barras legadas. */}
        {(p?.max_entropy ?? 0) > 0 ? (
          <Bar kind="entropy" label="Entropia" cur={p?.entropy ?? 0} max={p?.max_entropy ?? 0} />
        ) : (
          <>
            <Bar kind="mana" label="Mana" cur={p?.mana ?? 0} max={p?.max_mana ?? 0} />
            <Bar kind="stamina" label="Vigor" cur={p?.stamina ?? 0} max={p?.max_stamina ?? 0} />
          </>
        )}
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
        <p className="lvlup-hint">⬆ Escolha de nível pendente — botão “Nível!” no topo.</p>
      )}

      <div>
        <p className="hud__label">Acervo de Cartas</p>
        <ul className="abilities">
          {cards.length === 0 ? (
            <li className="empty">Nenhuma Carta conhecida</li>
          ) : (
            cards.map((card) => (
              <li key={card.id}>
                {card.name}
                {card.prepared ? <span className="ability__branch"> ◆ preparada</span> : null}
                <span className="ability__kind"> · {card.type}</span>
              </li>
            ))
          )}
        </ul>
      </div>

      <div>
        <p className="hud__label">Inventário</p>
        <ul className="inv">
          {(data?.inventory ?? []).length === 0 ? (
            <li className="empty">Vazio</li>
          ) : (
            data!.inventory.map((it, i) => (
              <li key={`${it.id}-${i}`} className={"inv__item" + (it.equipped ? " is-equipped" : "")}>
                <span className={it.unique ? "inv__unique" : undefined}>
                  {it.unique ? "◆ " : ""}
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

function PeopleTab({ npcs }: { npcs: NpcView[] }) {
  if (!npcs.length) {
    return (
      <div>
        <p className="hud__label">Personagens</p>
        <p className="combat-empty">Você ainda não conhece ninguém destas terras.</p>
      </div>
    );
  }
  return (
    <div>
      <p className="hud__label">Conhecidos ({npcs.length})</p>
      <ul className="people">
        {npcs.map((n, i) => {
          const rel = Math.max(0, Math.min(10, n.relationship ?? 5));
          return (
            <li key={i} className="person">
              <div className="person__top">
                <span className="person__name">{n.name}</span>
                <span className="person__rel" title={`Relação ${rel}/10`}>
                  {"♥".repeat(Math.round(rel / 2)).padEnd(5, "·")}
                </span>
              </div>
              <p className="person__meta">{[n.role, n.location].filter(Boolean).join(" · ") || "—"}</p>
              {n.last_memory && <p className="person__mem">“{n.last_memory}”</p>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const STABILITY_CLASS: Record<string, string> = {
  "estável": "is-stable", "instável": "is-unstable", "em colapso": "is-collapsing",
};

function ReputationSparkline({ history }: { history: FactionView["history"] }) {
  if (history.length < 2) return null;
  const W = 100, H = 24;
  const pts = history
    .map((h, i) => {
      const x = (i / (history.length - 1)) * W;
      const y = H - ((h.value + 100) / 200) * H;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="faction__spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden>
      <polyline points={pts} />
    </svg>
  );
}

function FactionsTab({ factions }: { factions: FactionView[] }) {
  if (!factions.length) {
    return (
      <div>
        <p className="hud__label">Fações</p>
        <p className="combat-empty">Os poderes deste mundo ainda se movem nas sombras.</p>
      </div>
    );
  }
  const dispLabel: Record<string, string> = { hostil: "Hostil", neutro: "Neutra", aliada: "Aliada", aliado: "Aliada" };
  return (
    <div>
      <p className="hud__label">Poderes que você conhece ({factions.length})</p>
      <ul className="factions">
        {factions.map((f) => {
          const hasProg = f.progress !== null && f.progress !== undefined;
          const prog = Math.max(0, Math.min(100, f.progress ?? 0));
          const recent = f.history.slice(-3).reverse();
          return (
            <li key={f.id} className={"faction faction--" + f.disposition + (f.completed ? " is-done" : "")}>
              <div className="faction__top">
                <span className="faction__name">{f.name}</span>
                <span className={"faction__disp faction__disp--" + f.disposition}>
                  {dispLabel[f.disposition] ?? f.disposition}
                </span>
              </div>
              {f.knows_goal ? (
                <p className="faction__goal">{f.goal}</p>
              ) : (
                <p className="faction__goal faction__goal--unknown">Plano desconhecido — descubra com quem sabe.</p>
              )}
              {hasProg ? (
                <div className="faction__track" title={`${prog}% rumo ao objetivo (intel${f.intel_stale ? " antiga" : ""})`}>
                  <div className="faction__fill" style={{ width: prog + "%" }} />
                </div>
              ) : null}
              <p className="faction__meta">
                {f.completed ? "Objetivo cumprido" : hasProg ? `${prog}% · ${f.region}` : f.region}
                {f.intel_stale ? " · intel pode estar desatualizada" : ""}
                {f.reputation ? ` · reputação ${f.reputation > 0 ? "+" : ""}${f.reputation}` : ""}
              </p>
              <div className={"faction__stability " + (STABILITY_CLASS[f.stability_label] ?? "")}>
                <ReputationSparkline history={f.history} />
                <span className="faction__stability-label">{f.stability_label}</span>
              </div>
              {recent.length > 0 && (
                <p className="faction__history">
                  {recent.map((h, i) => (
                    <span key={i}>
                      turno {h.turn}: {h.delta > 0 ? "+" : ""}{h.delta}
                      {i < recent.length - 1 ? " · " : ""}
                    </span>
                  ))}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ChronicleTab({ chapters, gameId }: { chapters: ChronicleChapter[]; gameId?: string }) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<ChronicleSearchHit[]>([]);
  const [searchMode, setSearchMode] = useState<string>("");
  useEffect(() => {
    const normalized = query.trim();
    if (!gameId || normalized.length < 2) {
      setHits([]);
      setSearchMode("");
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      searchChronicle({ game_id: gameId, query: normalized, top_k: 5 }, controller.signal)
        .then((result) => {
          setHits(result.hits);
          setSearchMode(result.mode === "lexical_fallback" ? "busca lexical" : "busca híbrida");
        })
        .catch((error) => {
          if (error?.name !== "AbortError") setSearchMode("filtro local");
        });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [gameId, query]);
  if (!chapters.length) {
    return (
      <div>
        <p className="hud__label">Crônica</p>
        <p className="combat-empty">Nenhum feito digno de canção — ainda.</p>
      </div>
    );
  }
  const q = query.trim().toLowerCase();
  const filtered = !q
    ? chapters
    : chapters
        .map((cap) => ({
          ...cap,
          entries: cap.entries.filter((e) => e.text.toLowerCase().includes(q)),
        }))
        .filter((cap) => cap.entries.length > 0 || cap.title.toLowerCase().includes(q));
  // capítulo mais recente primeiro; dentro do capítulo, entrada mais recente primeiro
  const ordered = filtered.slice().reverse();
  return (
    <div>
      <div className="chron-tools">
        <p className="hud__label">Crônica da jornada</p>
        {gameId && (
          <a className="iconbtn" href={"/game/chronicle/export?game_id=" + encodeURIComponent(gameId)}
             download title="Baixar a crônica como .txt">
            ⤓ .txt
          </a>
        )}
      </div>
      <input
        className="chron-search"
        type="search"
        placeholder="Buscar na crônica…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Buscar na crônica"
      />
      {searchMode && <p className="chron-search__mode">{searchMode}</p>}
      {hits.length > 0 && (
        <ul className="chron-results" aria-label="Resultados da busca">
          {hits.map((hit) => (
            <li key={`${hit.chapter_id}-${hit.entry_ids.join("-")}`}>
              <button onClick={() => document.getElementById(`chron-${hit.chapter_id}`)?.scrollIntoView({ behavior: "smooth" })}>
                <b>{hit.chapter_title}</b>
                <span>{hit.snippet}</span>
                <small>turnos {hit.from_turn}–{hit.to_turn} · {hit.match_kind}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
      {ordered.length === 0 && <p className="combat-empty">Nada encontrado.</p>}
      {ordered.map((cap, ci) => (
        <section key={cap.chapter_id ?? ci} id={`chron-${cap.chapter_id ?? ci}`} className="chron-chapter">
          <header className="chron-chapter__head">
            <h4 className="chron-chapter__title">{cap.title}</h4>
            <span className="chron-chapter__turn">desde o turno {cap.started_turn}</span>
          </header>
          {cap.digest && (
            <div className="chron-digest">
              <p>{cap.digest.summary}</p>
              <small>{cap.digest.covered_entry_count} entradas resumidas · turnos {cap.digest.from_turn ?? cap.started_turn}–{cap.digest.to_turn ?? cap.started_turn}</small>
            </div>
          )}
          {cap.entries.length === 0 ? (
            <p className="combat-empty">Nenhum feito digno de canção — ainda.</p>
          ) : (
            <details open={!cap.digest} className="chron-raw">
              <summary>{cap.digest ? "Ver registros originais" : "Registros"}</summary>
              <ol className="chronicle">
                {cap.entries.slice().reverse().map((e, i) => (
                  <li key={e.entry_id ?? e.event_id ?? i} className={e.kind === "milestone" ? "chron chron--milestone" : "chron"}>
                    <span className="chron__mark" aria-hidden>{e.kind === "milestone" ? "⚔" : "❧"}</span>
                    <p className="chron__text" dangerouslySetInnerHTML={{ __html: mdLite(e.text) }} />
                  </li>
                ))}
              </ol>
            </details>
          )}
        </section>
      ))}
    </div>
  );
}

function PartyBars({ party }: { party: import("../types").PartyMember[] }) {
  const shown = party;
  if (!shown.length) return null;
  return (
    <div className="partyblock">
      <p className="hud__label hud__label--sub">Companheiros</p>
      <ul className="party">
        {shown.map((m, i) => (
          <li key={`${m.name}-${i}`} className={"party__member" + (m.status === "morto" ? " is-dead" : "") + (!m.active ? " is-waiting" : "")}>
            <div className="party__top">
              <span>{m.name}{!m.active && m.status !== "morto" ? " (esperando)" : ""}{m.status === "morto" ? " †" : ""}</span>
              <span>{`${m.vitalidade}/${m.max_vitalidade}`}</span>
            </div>
            <div className="party__track">
              <div className="party__fill"
                   style={{ width: pct(m.vitalidade, m.max_vitalidade) + "%" }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CombatTab({ c, hitKey, party }: {
  c: CombatBlock | undefined; hitKey: number; party: import("../types").PartyMember[];
}) {
  if (!c || !c.active || !c.enemies.length) {
    return (
      <div>
        <p className="combat-empty">Nenhuma ameaça à vista. O aço descansa.</p>
        <PartyBars party={party} />
      </div>
    );
  }
  const cds = Object.entries(c.cooldowns || {});
  return (
    <div>
      <Combat c={c} hitKey={hitKey} cds={cds} />
      <PartyBars party={party} />
    </div>
  );
}

function Combat({ c, hitKey, cds }: { c: CombatBlock; hitKey: number; cds: [string, number][] }) {
  const ref = useRef<HTMLDivElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    const el = ref.current;
    if (!el) return;
    el.classList.remove("is-hit");
    void el.offsetWidth;
    el.classList.add("is-hit");
  }, [hitKey]);

  return (
    <div className="combatblock" ref={ref}>
      <p className="hud__label">
        Combate {c.round ? <span className="muted">· Round {c.round}</span> : null}
      </p>

      <WoundTrack wounds={c.wounds} />
      <SceneZones scene={c.scene} chase={c.chase} />

      <ul className="enemies">
        {c.enemies.map((e, i) => (
          <li key={`${e.name}-${i}`} className="enemy">
            <div className="enemy__top">
              <span>{e.name}</span>
              <span>{`${e.vitalidade}/${e.max_vitalidade}`}</span>
            </div>
            <div className="enemy__track">
              <div className="enemy__fill"
                   style={{ width: pct(e.vitalidade, e.max_vitalidade) + "%" }} />
            </div>
            <p className="enemy__public">
              {e.esquiva != null ? `Esquiva ${e.esquiva}` : "Esquiva desconhecida"}
              {e.protecao != null ? ` · Proteção ${e.protecao}` : ""}
            </p>
            {e.revealed_cards.length > 0 && (
              <p className="enemy__intel">Cartas vistas: {e.revealed_cards.map((card) => card.name).join(", ")}</p>
            )}
            {e.revealed_resistances.length > 0 && (
              <p className="enemy__intel">Resistências vistas: {e.revealed_resistances.join(", ")}</p>
            )}
            {e.conditions.length > 0 && <CondChips conds={e.conditions} />}
          </li>
        ))}
      </ul>

      {c.order.length > 0 && (
        <>
          <p className="hud__label hud__label--sub">Iniciativa</p>
          <ol className="initiative">
            {c.order.map((o, i) => (
              <li key={i} className={"init " + (o.side === "hero" ? "init--hero" : "init--enemy")}>
                {`${o.init} · ${o.name}`}
              </li>
            ))}
          </ol>
        </>
      )}

      {c.player_conditions.length > 0 && (
        <>
          <p className="hud__label hud__label--sub">Suas condições</p>
          <CondChips conds={c.player_conditions} />
        </>
      )}

      {cds.length > 0 && (
        <>
          <p className="hud__label hud__label--sub">Recarga</p>
          <div className="conds__row">
            {cds.map(([k, v]) => (
              <span key={k} className="cond-chip">{`${prettyItem(k)} (${v})`}</span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Bar({
  kind, label, cur, max, low, hitKey,
}: {
  kind: "hp" | "mana" | "stamina" | "entropy"; label: string; cur: number; max: number; low?: boolean; hitKey?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (hitKey == null) return;
    if (first.current) { first.current = false; return; }
    const el = ref.current;
    if (!el) return;
    el.classList.remove("is-hit");
    void el.offsetWidth;
    el.classList.add("is-hit");
  }, [hitKey]);

  return (
    <div className={"bar" + (low ? " is-low" : "")} data-kind={kind} ref={ref}>
      <div className="bar__top"><span>{label}</span><span>{`${cur}/${max}`}</span></div>
      <div className="bar__track">
        <div className="bar__fill" style={{ width: pct(cur, max) + "%" }} />
      </div>
    </div>
  );
}

// spec refatoracao-sistema-classes (R11): Carga do Abismo como chip por patamar.
// Médico (abyss.hidden) manda tier "?" — selo enigmático, sem número/patamar.
function AbyssChip({ tier, charge }: { tier?: string; charge: number }) {
  const t = tier ?? "nenhum";
  if (t === "nenhum") return null;
  const hidden = t === "?";
  const label = hidden
    ? "Carga do Abismo: algo se acumula…"
    : `Carga do Abismo: ${t}${charge ? ` (${charge})` : ""}`;
  return (
    <div className="abyss-chip" data-tier={t} title="Recurso de longo prazo: não cai no descanso.">
      <span className="abyss-chip__dot" /> {label}
    </div>
  );
}

function CondChips({ conds }: { conds: Condition[] }) {
  return (
    <div className="conds__row">
      {conds.map((cd, i) => (
        <span key={i} className={"cond-chip" + (cd.dot > 0 ? " is-dot" : "")}>
          {`${cd.name}${cd.dot > 0 ? ` ${cd.dot}/t` : ""} (${cd.duration})`}
        </span>
      ))}
    </div>
  );
}
