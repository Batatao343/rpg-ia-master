import { pct, prettyItem } from "../lib";
import type { CombatBlock, Condition, GameResponse, QuestBlock } from "../types";
import { WorldMap } from "./WorldMap";

export function Hud({ data, open }: { data: GameResponse | null; open: boolean }) {
  const p = data?.player_stats;
  const sub = [p?.class_name, p?.race].filter(Boolean).join(" · ") || "—";
  const hpLow = p ? pct(p.hp, p.max_hp) <= 30 : false;

  return (
    <aside className={"hud" + (open ? " is-open" : "")} aria-label="Ficha do personagem">
      <div className="hud__id">
        <p className="hud__name">{p?.name || "—"}</p>
        <p className="hud__sub muted">{sub}</p>
      </div>

      <div className="bars">
        <Bar kind="hp" label="Vida" cur={p?.hp ?? 0} max={p?.max_hp ?? 0} low={hpLow} />
        <Bar kind="mana" label="Mana" cur={p?.mana ?? 0} max={p?.max_mana ?? 0} />
        <Bar kind="stamina" label="Vigor" cur={p?.stamina ?? 0} max={p?.max_stamina ?? 0} />
      </div>

      <div className="stats">
        <div className="stat"><span className="muted">Nível</span><b>{p?.level ?? 1}</b></div>
        <div className="stat"><span className="muted">XP</span><b>{p?.xp ?? 0}</b></div>
        <div className="stat"><span className="muted">Ouro</span><b>{p?.gold ?? 0}</b></div>
        <div className="stat"><span className="muted">Defesa</span><b>{p?.defense ?? 0}</b></div>
      </div>

      {data?.combat && <Combat c={data.combat} />}
      {data?.quest && <Quest q={data.quest} />}

      <div className="mapblock">
        <p className="hud__label">Mapa</p>
        <WorldMap visited={data?.world.visited ?? []} currentId={data?.world.location_id ?? ""} />
      </div>

      <div className="invblock">
        <p className="hud__label">Inventário</p>
        <ul className="inv">
          {(data?.inventory ?? []).length === 0 ? (
            <li className="empty">Vazio</li>
          ) : (
            data!.inventory.map((it, i) => <li key={i}>{prettyItem(it)}</li>)
          )}
        </ul>
      </div>

      <details className="summary">
        <summary>Resumo da história</summary>
        <p className="muted">{data?.narrative_summary || "A aventura começa."}</p>
      </details>
    </aside>
  );
}

function Bar({
  kind,
  label,
  cur,
  max,
  low,
}: {
  kind: "hp" | "mana" | "stamina";
  label: string;
  cur: number;
  max: number;
  low?: boolean;
}) {
  return (
    <div className={"bar" + (low ? " is-low" : "")} data-kind={kind}>
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

function Combat({ c }: { c: CombatBlock }) {
  if (!c.active || !c.enemies.length) return null;
  const cds = Object.entries(c.cooldowns || {});
  return (
    <div className="combatblock">
      <p className="hud__label">
        Combate <span className="muted">{c.round ? `· Round ${c.round}` : ""}</span>
      </p>

      <ul className="enemies">
        {c.enemies.map((e, i) => (
          <li key={i} className="enemy">
            <div className="enemy__top">
              <span>{e.name}</span>
              <span className="muted">{`${e.hp}/${e.max_hp}`}</span>
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

function Quest({ q }: { q: QuestBlock }) {
  const beats = q.beats || [];
  if (!q.objective && !beats.length) return null;
  const done = beats.filter((b) => b.status === "done").length;
  const total = q.total || beats.length;
  const progress = total ? ` (${Math.min(done, total)}/${total})` : "";
  return (
    <div className="questblock">
      <p className="hud__label">Objetivo</p>
      <p className="quest__obj">{(q.objective || "Avance a trama.") + progress}</p>
      <ol className="quest__beats">
        {beats.map((b, i) => {
          const isDone = b.status === "done";
          const isCurrent = !isDone && i === (q.current_step ?? 0);
          return (
            <li
              key={i}
              className={"quest__beat" + (isDone ? " is-done" : isCurrent ? " is-current" : "")}
            >
              {b.description || ""}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
