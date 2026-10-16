import type { Condition } from "../types";

export interface Participant {
  id: string;
  name: string;
  role: "player" | "enemy" | "ally";
  vit?: number;
  max?: number;
  esquiva?: number | null;
  protecao?: number | null;
  conditions: Condition[];
  intel: string[];
  concealment?: string;
  posture?: string;
  engagedNames: string[];
}

export type AimMark = { valid: boolean; reason?: string } | undefined;

/** SPEC-205 R11: participante da arena. Vira botão só enquanto há mira ativa. */
export function TargetChip({ p, aim, onPick }: {
  p: Participant;
  aim: AimMark;
  onPick: (id: string) => void;
}) {
  const pct = p.vit != null && p.max ? Math.max(0, Math.min(100, Math.round((p.vit / p.max) * 100))) : null;
  const body = (
    <>
      <span className="tchip__top">
        <strong>{p.name}</strong>
        {p.vit != null && p.max != null && <span className="tchip__vit">{`${p.vit}/${p.max}`}</span>}
      </span>
      {pct !== null && <span className="tchip__bar" aria-hidden="true"><span style={{ width: pct + "%" }} /></span>}
      <span className="tchip__meta">
        {p.role === "enemy" && (p.esquiva != null ? `Esquiva ${p.esquiva}` : "Esquiva ?")}
        {p.role === "enemy" && p.protecao != null ? ` · Proteção ${p.protecao}` : ""}
        {p.concealment && p.concealment !== "visivel" ? ` · ${p.concealment}` : ""}
        {p.posture && p.posture !== "neutro" ? ` · ${p.posture}` : ""}
      </span>
      {p.engagedNames.length > 0 && <span className="tchip__meta">{`Engajado: ${p.engagedNames.join(", ")}`}</span>}
      {p.conditions.length > 0 && (
        <span className="tchip__tags">{p.conditions.map((c, i) => <em key={i}>{c.name}</em>)}</span>
      )}
      {p.intel.length > 0 && <span className="tchip__meta">{`Revelado: ${p.intel.join(", ")}`}</span>}
    </>
  );
  const cls = `tchip tchip--${p.role}${aim ? (aim.valid ? " is-valid" : " is-invalid") : ""}`;
  if (!aim) return <div className={cls} data-participant={p.id}>{body}</div>;
  const label = aim.valid
    ? `Alvo: ${p.name}${p.vit != null ? `, Vitalidade ${p.vit} de ${p.max}` : ""}`
    : `${p.name}: alvo inválido${aim.reason ? ` — ${aim.reason}` : ""}`;
  return (
    <button type="button" className={cls} data-target={p.id} data-aim-safe aria-label={label}
      aria-disabled={!aim.valid || undefined} title={aim.valid ? undefined : aim.reason}
      onClick={() => { if (aim.valid) onPick(p.id); }}>
      {body}
    </button>
  );
}
