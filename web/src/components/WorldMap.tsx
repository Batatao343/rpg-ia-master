import { useEffect, useState } from "react";
import * as api from "../api";
import type { MapLocation, MapOverlays, QuestMarker, WorldMapData } from "../types";

// Mapa do mundo com fog of war: nós conhecidos (visited) aparecem nomeados;
// os demais ficam como "???" (posição insinuada, identidade oculta). Só exibição.
// Etapa B: locais dominados por fações ganham selo; perigo pode ser elevado por ascensão.
// Fase 3.3: locais com quest ativa ganham selo de objetivo.
// Fase 3.4: badge de controle recém-mudado + ícone de ameaça regional + banner de looming_threat.
const CONTROL_CHANGE_RECENCY = 10; // turnos

export function WorldMap({
  visited,
  currentId,
  controlled = {},
  dangerOverrides = {},
  markers = [],
  overlays,
  currentTurn = 0,
  blockedRoutes = [],
  onTravel,
}: {
  visited: string[];
  currentId: string;
  controlled?: Record<string, string>;
  dangerOverrides?: Record<string, number>;
  markers?: QuestMarker[];
  overlays?: MapOverlays;
  currentTurn?: number;
  blockedRoutes?: Array<{ a: string; b: string }>; // Fase 6.1
  onTravel?: (location: MapLocation) => void;
}) {
  const [map, setMap] = useState<WorldMapData | null>(null);

  useEffect(() => {
    api.getMap().then(setMap).catch(() => setMap(null));
  }, []);

  if (!map) return null;

  const seen = new Set(visited);
  const byId = new Map(map.locations.map((l) => [l.id, l]));
  const questTargets = new Set(markers.map((m) => m.location_id));
  const recentControlLocs = new Set(
    (overlays?.control_changes ?? [])
      .filter((c) => currentTurn - c.turn <= CONTROL_CHANGE_RECENCY)
      .map((c) => c.location_id)
  );
  const threatRegions = new Set((overlays?.threats ?? []).map((t) => t.region_id));
  const threatHintByRegion = new Map((overlays?.threats ?? []).map((t) => [t.region_id, t.hint]));

  // Arestas únicas entre locais conectados (a<b para deduplicar).
  const edges: Array<[MapLocation, MapLocation]> = [];
  for (const loc of map.locations) {
    for (const cid of loc.connections) {
      const other = byId.get(cid);
      if (other && loc.id < other.id) edges.push([loc, other]);
    }
  }

  return (
    <div>
      {overlays?.looming_threat && (
        <p className="worldmap__banner">⚠ {overlays.looming_threat}</p>
      )}
      <div className="worldmap">
      <svg className="worldmap__edges" viewBox="0 0 100 100" preserveAspectRatio="none">
        {edges.map(([a, b], i) => {
          const blocked = blockedRoutes.some(
            (r) => (r.a === a.id && r.b === b.id) || (r.a === b.id && r.b === a.id)
          );
          return (
            <line
              key={i}
              className={"worldmap__edge" + (blocked ? " is-blocked" : "")}
              x1={a.coords.x}
              y1={a.coords.y}
              x2={b.coords.x}
              y2={b.coords.y}
            />
          );
        })}
      </svg>

      {map.locations.map((loc) => {
        const known = seen.has(loc.id);
        const isCurrent = loc.id === currentId;
        const danger = dangerOverrides[loc.id] ?? loc.danger; // ascensão pode ter elevado o perigo
        const ruler = controlled[loc.id]; // dominado por uma facção (nome)?
        const hasQuest = questTargets.has(loc.id); // Fase 3.3: alvo de quest ativa?
        const isContested = recentControlLocs.has(loc.id); // Fase 3.4: controle mudou há pouco
        const threatHint = threatRegions.has(loc.region_id) ? threatHintByRegion.get(loc.region_id) : null;
        const cls =
          "worldmap__node" +
          (isCurrent ? " is-current" : "") +
          (known ? "" : " is-fog") +
          (ruler ? " is-controlled" : "") +
          (hasQuest ? " is-quest-target" : "") +
          (isContested ? " is-contested" : "") +
          (threatHint ? " is-threatened" : "");
        const title = known
          ? `${loc.name} · perigo ${danger}`
            + (ruler ? ` · sob domínio de ${ruler}` : "")
            + (hasQuest ? " · objetivo de missão" : "")
            + (isContested ? " · controle mudou recentemente" : "")
            + (threatHint ? ` · ameaça: ${threatHint}` : "")
            + `\n${loc.lore_seed}`
          : "Região inexplorada";
        return (
          <button
            type="button"
            key={loc.id}
            className={cls}
            data-danger={danger}
            style={{ left: loc.coords.x + "%", top: loc.coords.y + "%" }}
            title={title}
            aria-label={known ? `${loc.name}${isCurrent ? " (local atual)" : ""}` : "Região inexplorada"}
            disabled={!known || isCurrent || !onTravel}
            onClick={() => onTravel?.(loc)}
          >
            <span className="worldmap__dot" />
            <span className="worldmap__label">
              {ruler ? "☗ " : ""}
              {hasQuest ? "◆ " : ""}
              {threatHint ? "⚠ " : ""}
              {known ? loc.name : "???"}
            </span>
          </button>
        );
      })}
      </div>
    </div>
  );
}
