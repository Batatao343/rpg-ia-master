import { useEffect, useState } from "react";
import * as api from "../api";
import type { MapLocation, MapOverlays, QuestMarker, WorldMapData } from "../types";
import { Icon, type IconName } from "../design/icons";

// Mapa do mundo com fog of war: nós conhecidos (visited) aparecem nomeados;
// os demais ficam como "?" (posição insinuada, identidade oculta). Só exibição.
// SPEC-323 R6: só são nomeados nós visitados, adjacentes ou alvo de missão; um ícone por estado.
// Etapa B: locais dominados por fações ganham selo; perigo pode ser elevado por ascensão.
// Fase 3.3: locais com quest ativa ganham selo de objetivo.
// Fase 3.4: badge de controle recém-mudado + ícone de ameaça regional + banner de looming_threat.
const CONTROL_CHANGE_RECENCY = 10; // turnos

/** Um ícone por estado (prioridade: ameaça > domínio > missão > atual > visitado > adjacente). */
function stateIcon(s: { isCurrent: boolean; known: boolean; ruler: boolean; quest: boolean; threat: boolean }): IconName {
  if (s.threat) return "warning";
  if (s.ruler) return "ruler";
  if (s.quest) return "quest";
  if (s.isCurrent) return "pin";
  return s.known ? "visited" : "adjacent";
}

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
  gameId,
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
  gameId?: string; // SPEC-210: fog server-side no fallback legado
}) {
  const [map, setMap] = useState<WorldMapData | null>(null);

  useEffect(() => {
    api.getMap(gameId).then(setMap).catch(() => setMap(null));
  }, [gameId]);

  if (!map) return null;

  const seen = new Set(visited);
  const byId = new Map(map.locations.map((l) => [l.id, l]));
  const questTargets = new Set(markers.map((m) => m.location_id));
  const adjacent = new Set<string>();
  for (const id of visited) for (const cid of byId.get(id)?.connections ?? []) adjacent.add(cid);
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
        <p className="worldmap__banner"><Icon name="warning" /> {overlays.looming_threat}</p>
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
        const named = known || adjacent.has(loc.id) || hasQuest;
        const isContested = recentControlLocs.has(loc.id); // Fase 3.4: controle mudou há pouco
        const threatHint = threatRegions.has(loc.region_id) ? threatHintByRegion.get(loc.region_id) : null;
        const cls =
          "worldmap__node" +
          (isCurrent ? " is-current" : "") +
          (known ? "" : " is-fog") +
          (named ? "" : " is-unnamed") +
          (ruler ? " is-controlled" : "") +
          (hasQuest ? " is-quest-target" : "") +
          (isContested ? " is-contested" : "") +
          (threatHint ? " is-threatened" : "");
        const state = isCurrent ? "local atual" : known ? "visitado" : "ainda não visitado";
        const label = `${loc.name}, ${state}`
          + (hasQuest ? ", objetivo de missão" : "") + (ruler ? `, sob domínio de ${ruler}` : "")
          + (known ? `, perigo ${danger}` : "")
          + (threatHint ? `, ameaça: ${threatHint}` : "");
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
            data-effect="map.marker"
            data-effect-state={isCurrent ? "current" : known ? "travelable" : "fog"}
            style={{ left: loc.coords.x + "%", top: loc.coords.y + "%" }}
            title={title}
            aria-label={named ? label : "Região inexplorada"}
            disabled={!known || isCurrent || !onTravel}
            onClick={() => onTravel?.(loc)}
          >
            <span className="worldmap__dot" />
            <span className="worldmap__label">
              {named ? <><Icon name={stateIcon({ isCurrent, known, ruler: !!ruler, quest: hasQuest, threat: !!threatHint })} />{" "}{loc.name}</> : "?"}
            </span>
          </button>
        );
      })}
      </div>
    </div>
  );
}
