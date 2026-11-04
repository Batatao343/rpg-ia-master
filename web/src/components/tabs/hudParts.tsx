import { useEffect, useRef, useState } from "react";
import { pct } from "../../lib";
import type { Condition } from "../../types";
import type { IconName } from "../../design/icons";

/** SPEC-323 R2: ícone do slot do inventário, só com a família da SPEC-322 (sem arte nova por item). */
export function itemIcon(it: { unique?: boolean; slot: string | null }): IconName {
  if (it.unique) return "unique";
  const slot = (it.slot ?? "").toLowerCase();
  if (/arma|weapon|mao|mão|main/.test(slot)) return "card-active";
  if (/armadura|armor|escudo|shield|off|corpo|body/.test(slot)) return "card-reaction";
  return "prepared";
}

export type EquipFn = (pick: { item_id?: string; unequip_slot?: string }) => void;

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

export function Bar({
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
export function AbyssChip({ tier, charge }: { tier?: string; charge: number }) {
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

export function CondChips({ conds }: { conds: Condition[] }) {
  return (
    <div className="conds__row">
      {conds.map((cd, i) => (
        <span key={i} className={"cond-chip" + (cd.dot > 0 ? " is-dot" : "")}>
          {`${cd.label ?? cd.name}${cd.dot > 0 ? ` ${cd.dot}/t` : ""} (${cd.duration})`}
        </span>
      ))}
    </div>
  );
}
