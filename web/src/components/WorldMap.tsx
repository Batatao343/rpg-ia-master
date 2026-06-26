import { useEffect, useState } from "react";
import * as api from "../api";
import type { MapLocation, WorldMapData } from "../types";

// Mapa do mundo com fog of war: nós conhecidos (visited) aparecem nomeados;
// os demais ficam como "???" (posição insinuada, identidade oculta). Só exibição.
// Etapa B: locais dominados por fações ganham selo; perigo pode ser elevado por ascensão.
export function WorldMap({
  visited,
  currentId,
  controlled = {},
  dangerOverrides = {},
}: {
  visited: string[];
  currentId: string;
  controlled?: Record<string, string>;
  dangerOverrides?: Record<string, number>;
}) {
  const [map, setMap] = useState<WorldMapData | null>(null);

  useEffect(() => {
    api.getMap().then(setMap).catch(() => setMap(null));
  }, []);

  if (!map) return null;

  const seen = new Set(visited);
  const byId = new Map(map.locations.map((l) => [l.id, l]));

  // Arestas únicas entre locais conectados (a<b para deduplicar).
  const edges: Array<[MapLocation, MapLocation]> = [];
  for (const loc of map.locations) {
    for (const cid of loc.connections) {
      const other = byId.get(cid);
      if (other && loc.id < other.id) edges.push([loc, other]);
    }
  }

  return (
    <div className="worldmap">
      <svg className="worldmap__edges" viewBox="0 0 100 100" preserveAspectRatio="none">
        {edges.map(([a, b], i) => (
          <line
            key={i}
            className="worldmap__edge"
            x1={a.coords.x}
            y1={a.coords.y}
            x2={b.coords.x}
            y2={b.coords.y}
          />
        ))}
      </svg>

      {map.locations.map((loc) => {
        const known = seen.has(loc.id);
        const isCurrent = loc.id === currentId;
        const danger = dangerOverrides[loc.id] ?? loc.danger; // ascensão pode ter elevado o perigo
        const ruler = controlled[loc.id]; // dominado por uma facção?
        const cls =
          "worldmap__node" +
          (isCurrent ? " is-current" : "") +
          (known ? "" : " is-fog") +
          (ruler ? " is-controlled" : "");
        const title = known
          ? `${loc.name} · perigo ${danger}${ruler ? " · sob domínio" : ""}\n${loc.lore_seed}`
          : "Região inexplorada";
        return (
          <div
            key={loc.id}
            className={cls}
            data-danger={danger}
            style={{ left: loc.coords.x + "%", top: loc.coords.y + "%" }}
            title={title}
          >
            <span className="worldmap__dot" />
            <span className="worldmap__label">
              {ruler ? "☗ " : ""}
              {known ? loc.name : "???"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
