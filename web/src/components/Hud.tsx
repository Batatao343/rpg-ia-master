import { useEffect, useRef, useState } from "react";
import { mdLite, pct, prettyItem } from "../lib";
import type { CombatBlock, Condition, FactionView, GameResponse, NpcView } from "../types";
import { WorldMap } from "./WorldMap";
import { Medallion } from "./ornaments";

type Tab = "ficha" | "combate" | "personagens" | "mapa" | "faccoes" | "cronica";

export function Hud({ data, open }: { data: GameResponse | null; open: boolean }) {
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

  // ênfase de dano: queda de HP do herói entre turnos.
  const prevHp = useRef<number | null>(null);
  const [hpHit, setHpHit] = useState(0);
  useEffect(() => {
    const hp = p?.hp;
    if (hp == null) return;
    if (prevHp.current != null && hp < prevHp.current) setHpHit((n) => n + 1);
    prevHp.current = hp;
  }, [p?.hp]);

  const tabs: Array<[Tab, string]> = [
    ["ficha", "Ficha"],
    ["combate", "Combate"],
    ["personagens", "Pessoas"],
    ["mapa", "Mapa"],
    ["faccoes", "Fações"],
    ["cronica", "Crônica"],
  ];

  return (
    <aside className={"hud" + (open ? " is-open" : "")} aria-label="Ficha do personagem">
      <div className="hud__head">
        <span className="hud__medallion"><Medallion size={36} /></span>
        <div className="hud__id">
          <p className="hud__name">{p?.name || "—"}</p>
          <p className="hud__sub">{sub}</p>
        </div>
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

      <div className="tabpanel" role="tabpanel">
        {tab === "ficha" && <FichaTab data={data} hpHitKey={hpHit} />}
        {tab === "combate" && <CombatTab c={data?.combat} hitKey={hpHit} />}
        {tab === "personagens" && <PeopleTab npcs={data?.npcs ?? []} />}
        {tab === "mapa" && (
          <div>
            <p className="hud__label">Mapa do mundo</p>
            <WorldMap visited={data?.world.visited ?? []} currentId={data?.world.location_id ?? ""} />
          </div>
        )}
        {tab === "faccoes" && <FactionsTab factions={data?.factions ?? []} />}
        {tab === "cronica" && <ChronicleTab entries={data?.chronicle ?? []} />}
      </div>
    </aside>
  );
}

function FichaTab({ data, hpHitKey }: { data: GameResponse | null; hpHitKey: number }) {
  const p = data?.player_stats;
  const hpLow = p ? pct(p.hp, p.max_hp) <= 30 : false;
  const abilities = p?.abilities ?? [];
  return (
    <>
      <div className="bars">
        <Bar kind="hp" label="Vida" cur={p?.hp ?? 0} max={p?.max_hp ?? 0} low={hpLow} hitKey={hpHitKey} />
        <Bar kind="mana" label="Mana" cur={p?.mana ?? 0} max={p?.max_mana ?? 0} />
        <Bar kind="stamina" label="Vigor" cur={p?.stamina ?? 0} max={p?.max_stamina ?? 0} />
      </div>

      <div className="stats">
        <div className="stat"><span>Nível</span><b>{p?.level ?? 1}</b></div>
        <div className="stat"><span>XP</span><b>{p?.xp ?? 0}</b></div>
        <div className="stat"><span>Ouro</span><b>{p?.gold ?? 0}</b></div>
        <div className="stat"><span>Defesa</span><b>{p?.defense ?? 0}</b></div>
      </div>

      <div>
        <p className="hud__label">Habilidades</p>
        <ul className="abilities">
          {abilities.length === 0 ? (
            <li className="empty">Nenhuma habilidade conhecida</li>
          ) : (
            abilities.map((a, i) => <li key={i}>{a}</li>)
          )}
        </ul>
      </div>

      <div>
        <p className="hud__label">Inventário</p>
        <ul className="inv">
          {(data?.inventory ?? []).length === 0 ? (
            <li className="empty">Vazio</li>
          ) : (
            data!.inventory.map((it, i) => <li key={i}>{prettyItem(it)}</li>)
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
      <p className="hud__label">Poderes do mundo ({factions.length})</p>
      <ul className="factions">
        {factions.map((f) => {
          const prog = Math.max(0, Math.min(100, f.progress ?? 0));
          return (
            <li key={f.id} className={"faction faction--" + f.disposition + (f.completed ? " is-done" : "")}>
              <div className="faction__top">
                <span className="faction__name">{f.name}</span>
                <span className={"faction__disp faction__disp--" + f.disposition}>
                  {dispLabel[f.disposition] ?? f.disposition}
                </span>
              </div>
              <p className="faction__goal">{f.goal}</p>
              <div className="faction__track" title={`${prog}% rumo ao objetivo`}>
                <div className="faction__fill" style={{ width: prog + "%" }} />
              </div>
              <p className="faction__meta">
                {f.completed ? "Objetivo cumprido" : `${prog}% · ${f.region}`}
                {f.reputation ? ` · reputação ${f.reputation > 0 ? "+" : ""}${f.reputation}` : ""}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ChronicleTab({ entries }: { entries: string[] }) {
  if (!entries.length) {
    return (
      <div>
        <p className="hud__label">Crônica</p>
        <p className="combat-empty">Nenhum feito digno de canção — ainda.</p>
      </div>
    );
  }
  // mais recente primeiro
  const ordered = entries.slice().reverse();
  return (
    <div>
      <p className="hud__label">Crônica da jornada</p>
      <ol className="chronicle">
        {ordered.map((text, i) => (
          <li key={i} className="chron">
            <span className="chron__mark" aria-hidden>❧</span>
            <p className="chron__text" dangerouslySetInnerHTML={{ __html: mdLite(text) }} />
          </li>
        ))}
      </ol>
    </div>
  );
}

function CombatTab({ c, hitKey }: { c: CombatBlock | undefined; hitKey: number }) {
  if (!c || !c.active || !c.enemies.length) {
    return <p className="combat-empty">Nenhuma ameaça à vista. O aço descansa.</p>;
  }
  const cds = Object.entries(c.cooldowns || {});
  return <Combat c={c} hitKey={hitKey} cds={cds} />;
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

      <ul className="enemies">
        {c.enemies.map((e, i) => (
          <li key={i} className="enemy">
            <div className="enemy__top">
              <span>{e.name}</span>
              <span>{`${e.hp}/${e.max_hp}`}</span>
            </div>
            <div className="enemy__track">
              <div className="enemy__fill" style={{ width: pct(e.hp, e.max_hp) + "%" }} />
            </div>
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
  kind: "hp" | "mana" | "stamina"; label: string; cur: number; max: number; low?: boolean; hitKey?: number;
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
