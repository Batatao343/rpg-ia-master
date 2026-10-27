import type { KeyboardEvent } from "react";
import type { CombatBlock, EncounterView, OmenView, PartyMember } from "../types";
import { ChaseTrack } from "../components/SceneZones";
import { TargetChip, type AimMark, type Participant } from "./TargetChip";

const normName = (value: string) => value.trim().toLowerCase();

export function buildParticipants(combat: CombatBlock, party: PartyMember[]): Array<Participant & { zoneId: string }> {
  const view = combat.encounter_view as Partial<EncounterView> | undefined;
  const labels = new Map((view?.participants ?? []).map((p) => [p.participant_id, p.species_label]));
  const pos = new Map(combat.scene.positions.map((p) => [p.participant_id, p]));
  const out: Array<Participant & { zoneId: string }> = [];
  const player = pos.get("player");
  out.push({
    id: "player", name: player?.participant_name || "Você", role: "player",
    vit: combat.wounds.vitality, max: combat.wounds.max_vitality,
    conditions: combat.player_conditions, intel: [],
    concealment: player?.concealment, posture: player?.posture,
    engagedNames: player?.engaged_names ?? [], zoneId: player?.zone_id ?? "",
  });
  for (const enemy of combat.enemies) {
    const p = pos.get(enemy.id);
    out.push({
      id: enemy.id, name: enemy.name, role: "enemy",
      vit: enemy.vitalidade, max: enemy.max_vitalidade, esquiva: enemy.esquiva, protecao: enemy.protecao,
      conditions: enemy.conditions,
      intel: [...enemy.revealed_cards.map((c) => c.name), ...enemy.revealed_resistances],
      concealment: p?.concealment, posture: p?.posture,
      engagedNames: p?.engaged_names ?? [], zoneId: p?.zone_id ?? "",
    });
  }
  // SPEC-342 B-3: homônimos precisam de nomes distintos (o log e o presságio usam "Bandido 1/2").
  const enemies = out.filter((p) => p.role === "enemy");
  for (const e of enemies) {
    const label = labels.get(e.id);
    const clash = enemies.filter((o) => (labels.get(o.id) || o.name) === (label || e.name)).length > 1;
    e.name = clash ? e.name : label || e.name;
  }
  const seen = new Map<string, number>();
  for (const e of enemies) {
    const n = (seen.get(e.name) ?? 0) + 1;
    seen.set(e.name, n);
  }
  for (const [name, total] of seen) {
    if (total < 2) continue;
    let i = 0;
    for (const e of enemies) if (e.name === name) e.name = `${name} ${++i}`;
  }
  const known = new Set(out.map((p) => p.id));
  for (const [id, p] of pos) {
    if (known.has(id)) continue;
    const member = party.find((m) => normName(m.name) === normName(p.participant_name));
    out.push({
      id, name: p.participant_name, role: "ally",
      vit: member?.vitalidade, max: member?.max_vitalidade,
      conditions: [], intel: [], concealment: p.concealment, posture: p.posture,
      engagedNames: p.engaged_names, zoneId: p.zone_id,
    });
  }
  return out;
}

/** SPEC-205 R11: arena por zonas com participantes clicáveis (evolução de SceneZones). */
export function Arena({ combat, party, aim, onPick, omens }: {
  combat: CombatBlock;
  party: PartyMember[];
  /** id → marca de validade, só durante a mira. */
  aim?: Record<string, AimMark>;
  onPick: (id: string) => void;
  /** SPEC-342 R8: id do inimigo → presságio. Só o modo Baralho passa isto; sem ele a Arena fica idêntica. */
  omens?: Record<string, OmenView>;
}) {
  const people = buildParticipants(combat, party);
  const zones = combat.scene.zones;
  const known = new Set(zones.map((z) => z.id));
  const loose = people.filter((p) => !known.has(p.zoneId));
  const groups = [
    ...zones.map((z) => ({ id: z.id, name: z.name, members: people.filter((p) => p.zoneId === z.id) })),
    ...(loose.length ? [{ id: "__campo", name: zones.length ? "Campo" : "Campo de batalha", members: loose }] : []),
  ];
  const turnOrder = (combat.order ?? []).map((slot) => slot.name).join(" → ");

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft" && event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const chips = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("button[data-target]:not([aria-disabled])"));
    const at = chips.indexOf(document.activeElement as HTMLElement);
    if (at < 0 || chips.length < 2) return;
    event.preventDefault();
    const step = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1;
    chips[(at + step + chips.length) % chips.length].focus();
  }

  return (
    <section className="arena" aria-label="Arena de combate" data-aim-safe>
      {turnOrder && <p className="arena__turn">{`Rodada ${combat.round} · iniciativa: ${turnOrder}`}</p>}
      <div className="arena__zones" role="toolbar" aria-label="Alvos do combate" tabIndex={-1} onKeyDown={onKeyDown}>
        {groups.map((g) => (
          <article key={g.id} className="arena__zone" aria-label={`Zona: ${g.name}`}>
            <h3>{g.name}</h3>
            <div className="arena__members">
              {g.members.map((p) => (
                <TargetChip key={p.id} p={p} aim={aim ? (aim[p.id] ?? { valid: false }) : undefined}
                  onPick={onPick} omen={omens?.[p.id]} />
              ))}
            </div>
          </article>
        ))}
      </div>
      <ChaseTrack chase={combat.chase} />
    </section>
  );
}
