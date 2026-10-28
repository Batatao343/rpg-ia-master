import { useEffect, useRef, useState } from "react";
import { mdLite, pct, prettyItem } from "../lib";
import { searchChronicle } from "../api";
import type { ChronicleChapter, ChronicleSearchHit, CombatBlock, Condition, FactionView, GameResponse, NewsItem, NpcView } from "../types";
import { newsLabel, orderNews } from "../heardNews";
import { SceneZones } from "./SceneZones";
import { WoundTrack } from "./WoundTrack";
import { Icon, type IconName } from "../design/icons";

/** SPEC-323 R2: ícone do slot do inventário, só com a família da SPEC-322 (sem arte nova por item). */
export function itemIcon(it: { unique?: boolean; slot: string | null }): IconName {
  if (it.unique) return "unique";
  const slot = (it.slot ?? "").toLowerCase();
  if (/arma|weapon|mao|mão|main/.test(slot)) return "card-active";
  if (/armadura|armor|escudo|shield|off|corpo|body/.test(slot)) return "card-reaction";
  return "prepared";
}

export type EquipFn = (pick: { item_id?: string; unequip_slot?: string }) => void;

/* SPEC-204: o antigo <aside class="hud"> com tablist própria e auto-troca por
   combate deixou de existir. Este módulo agora só exporta os painéis, montados
   pelas abas do workspace (web/src/workspace/). */

/** Ênfase de dano: incrementa quando a Vitalidade do herói cai entre turnos. */
export function useVitalityHit(vitality: number | undefined): number {
  const prevVitality = useRef<number | null>(null);
  const [vitalityHit, setVitalityHit] = useState(0);
  useEffect(() => {
    if (vitality == null) return;
    if (prevVitality.current != null && vitality < prevVitality.current) {
      setVitalityHit((n) => n + 1);
    }
    prevVitality.current = vitality;
  }, [vitality]);
  return vitalityHit;
}

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

const ATTITUDE_LABEL: Record<string, string> = {
  hostil: "Hostil", desconfiado: "Desconfiado", neutro: "Neutro", amistoso: "Amistoso", leal: "Leal",
};

export function PeopleTab({ npcs }: { npcs: NpcView[] }) {
  if (!npcs.length) {
    return (
      <div>
        <h3 className="hud__label">Personagens</h3>
        <p className="combat-empty">Converse com quem cruzar seu caminho: os conhecidos aparecem aqui, com o que lembram de você.</p>
      </div>
    );
  }
  return (
    <div>
      <h3 className="hud__label">Conhecidos ({npcs.length})</h3>
      <ul className="people">
        {npcs.map((n, i) => {
          return (
            <li key={i} className="person">
              <div className="person__top">
                <span className="person__name">{n.name}</span>
                <span className={"person__rel person__rel--" + n.attitude_label}>
                  {ATTITUDE_LABEL[n.attitude_label] ?? n.attitude_label}
                </span>
              </div>
              <p className="person__meta">{[n.role, n.location].filter(Boolean).join(" · ") || "—"}</p>
              {n.last_memory && <p className="person__mem">“{n.last_memory}”</p>}
              {(n.recent_changes ?? []).slice(-3).map((c, j) => (
                <p key={j} className="person__change">{c.text}</p>
              ))}
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

export function FactionsTab({ factions }: { factions: FactionView[] }) {
  if (!factions.length) {
    return (
      <div>
        <h3 className="hud__label">Fações</h3>
        <p className="combat-empty">Os poderes deste mundo ainda se movem nas sombras.</p>
      </div>
    );
  }
  const standingLabel: Record<string, string> = { hostil: "Hostil", desconfiado: "Desconfiada", neutro: "Neutra", amistoso: "Amistosa", aliado: "Aliada" };
  return (
    <div>
      <h3 className="hud__label">Poderes que você conhece ({factions.length})</h3>
      <ul className="factions">
        {factions.map((f) => {
          const hasProg = f.progress !== null && f.progress !== undefined;
          const prog = Math.max(0, Math.min(100, f.progress ?? 0));
          const recent = (f.recent_changes ?? []).slice(-3).reverse();
          return (
            <li key={f.id} className={"faction faction--" + f.standing_label + (f.completed ? " is-done" : "")}>
              <div className="faction__top">
                <span className="faction__name">{f.name}</span>
                <span className={"faction__disp faction__disp--" + f.standing_label}>
                  {standingLabel[f.standing_label] ?? f.standing_label}
                </span>
              </div>
              {f.knows_goal ? (
                <p className="faction__goal">{f.goal}</p>
              ) : (
                <p className="faction__goal faction__goal--unknown">Plano desconhecido — descubra com quem sabe.</p>
              )}
              {hasProg ? (
                <div className="faction__track" title={`${prog}% rumo ao objetivo (intel${f.intel_stale ? " antiga" : ""})`}>
                  <div className="faction__fill" style={{ transform: `scaleX(${prog / 100})` }} />
                </div>
              ) : null}
              <p className="faction__meta">
                {f.completed ? "Objetivo cumprido" : hasProg ? `${prog}% · ${f.region}` : f.region}
                {f.intel_stale ? " · intel pode estar desatualizada" : ""}
              </p>
              <div className={"faction__stability " + (STABILITY_CLASS[f.stability_label] ?? "")}>
                <span className="faction__stability-label">{f.stability_label}</span>
              </div>
              {f.membership && (
                <p className="faction__membership" data-testid="faction-membership">
                  {f.membership.rank_name ? `${f.membership.rank_name} · ` : ""}
                  {f.membership.standing_label}
                  {f.membership.perks.length > 0 ? ` · ${f.membership.perks.join(", ")}` : ""}
                </p>
              )}
              {recent.length > 0 && (
                <p className="faction__history">
                  {recent.map((h, i) => (
                    <span key={i}>
                      {h.text}
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

/** SPEC-296 R8: rumores que o herói percebeu em viagem/descanso. */
export function HeardNews({ news }: { news: NewsItem[] | undefined }) {
  const items = orderNews(news);
  return (
    <div className="heard-news">
      <h3 className="hud__label">Ouvi dizer</h3>
      {items.length === 0 ? (
        <p className="combat-empty">Converse com alguém numa taverna ou numa estrada movimentada para ouvir boatos.</p>
      ) : (
        <ul className="heard-news__list">
          {items.map((n, i) => (
            <li key={`${n.turn}-${i}`} className="heard-news__item">
              <small className="muted">
                {newsLabel(n)}
                {n.kind === "boato" ? <span className="heard-news__seal"> · boato</span> : null}
              </small>
              <p>{n.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** SPEC-213 R13: selo discreto do status da projeção da crônica (sem rede extra). */
function ProjectionSeal({ status }: { status?: string }) {
  const label = status === "pending" || status === "stale" ? "atualizando…"
    : status === "failed" ? "não atualizado" : "";
  return (
    <span className="projection-seal muted" aria-live="polite" data-status={status ?? "completed"}>
      {label}
    </span>
  );
}

export function ChronicleTab({ chapters, gameId, projectionStatus }: {
  chapters: ChronicleChapter[]; gameId?: string; projectionStatus?: string;
}) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<ChronicleSearchHit[]>([]);
  const [searchMode, setSearchMode] = useState<string>("");
  useEffect(() => {
    const normalized = query.trim();
    if (!gameId || normalized.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
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
        <h3 className="hud__label">Crônica <ProjectionSeal status={projectionStatus} /></h3>
        <p className="combat-empty">A crônica se escreve sozinha: explore, lute ou escolha um lado e o primeiro feito entra aqui.</p>
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
        <h3 className="hud__label">Crônica da jornada <ProjectionSeal status={projectionStatus} /></h3>
        {gameId && (
          <a className="iconbtn" href={"/game/chronicle/export?game_id=" + encodeURIComponent(gameId)}
             download title="Baixar a crônica como .txt">
            <Icon name="download" /> .txt
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
            <p className="combat-empty">A crônica se escreve sozinha: explore, lute ou escolha um lado e o primeiro feito entra aqui.</p>
          ) : (
            <details open={!cap.digest} className="chron-raw">
              <summary>{cap.digest ? "Ver registros originais" : "Registros"}</summary>
              <ol className="chronicle">
                {cap.entries.slice().reverse().map((e, i) => (
                  <li key={e.entry_id ?? e.event_id ?? i} className={e.kind === "milestone" ? "chron chron--milestone" : "chron"}>
                    <span className="chron__mark" aria-hidden><Icon name={e.kind === "milestone" ? "combat" : "chronicle"} /></span>
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

export function PartyBars({ party }: { party: import("../types").PartyMember[] }) {
  const shown = party;
  if (!shown.length) return null;
  return (
    <div className="partyblock">
      <h3 className="hud__label hud__label--sub">Companheiros</h3>
      <ul className="party">
        {shown.map((m, i) => (
          <li key={`${m.name}-${i}`} className={"party__member" + (m.status === "morto" ? " is-dead" : "") + (!m.active ? " is-waiting" : "")}>
            <div className="party__top">
              <span>{m.name}{!m.active && m.status !== "morto" ? " (esperando)" : ""}{m.status === "morto" ? " †" : ""}</span>
              <span>{`${m.vitalidade}/${m.max_vitalidade}`}</span>
            </div>
            {m.approval_label && (
              <div className="party__mood">
                {m.approval_label}{m.bond_label ? ` · ${m.bond_label}` : ""}
              </div>
            )}
            <div className="party__track">
              <div className="party__fill"
                   style={{ transform: `scaleX(${pct(m.vitalidade, m.max_vitalidade) / 100})` }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CombatTab({ c, hitKey, party, arena, deck }: {
  c: CombatBlock | undefined; hitKey: number; party: import("../types").PartyMember[];
  /** SPEC-347 R5.4: modo Baralho — a faixa de cena já mostra a rodada (sem repetir no cabeçalho). */
  deck?: boolean;
  /** SPEC-205: a Arena (aba Combate) já mostra zonas e inimigos — evita duplicar. */
  arena?: boolean;
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
      <Combat c={c} hitKey={hitKey} cds={cds} arena={arena} deck={deck} />
      <PartyBars party={party} />
    </div>
  );
}

function Combat({ c, hitKey, cds, arena, deck }: { c: CombatBlock; hitKey: number; cds: [string, number][]; arena?: boolean; deck?: boolean }) {
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
      <h3 className="hud__label">
        Combate{c.round && !deck ? <span className="muted"> · Rodada {c.round}</span> : null}
      </h3>

      <WoundTrack wounds={c.wounds} />
      {!arena && <SceneZones scene={c.scene} chase={c.chase} />}

      {!arena && <ul className="enemies">
        {c.enemies.map((e, i) => (
          <li key={`${e.name}-${i}`} className="enemy">
            <div className="enemy__top">
              <span>{e.name}</span>
              <span>{`${e.vitalidade}/${e.max_vitalidade}`}</span>
            </div>
            <div className="enemy__track">
              <div className="enemy__fill"
                   style={{ transform: `scaleX(${pct(e.vitalidade, e.max_vitalidade) / 100})` }} />
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
      </ul>}

      {c.order.length > 0 && !arena && (
        <>
          <h3 className="hud__label hud__label--sub">Iniciativa</h3>
          <ol className="initiative">
            {c.order.map((o, i) => (
              <li key={i} className={"init " + (o.side === "hero" ? "init--hero" : "init--enemy")}>
                {o.name}
              </li>
            ))}
          </ol>
        </>
      )}

      {c.player_conditions.length > 0 && (
        <>
          <h3 className="hud__label hud__label--sub">Suas condições</h3>
          <CondChips conds={c.player_conditions} />
        </>
      )}

      {cds.length > 0 && (
        <>
          <h3 className="hud__label hud__label--sub">Recarga</h3>
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
  kind: "hp" | "entropy"; label: string; cur: number; max: number; low?: boolean; hitKey?: number;
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
        <div className="bar__fill" style={{ transform: `scaleX(${pct(cur, max) / 100})` }} />
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
