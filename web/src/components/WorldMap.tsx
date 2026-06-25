import { useEffect, useState } from "react";
import * as api from "../api";
import type { MapLocation, WorldMapData } from "../types";

// Mapa do mundo com fog of war: nós conhecidos (visited) aparecem nomeados;
// os demais ficam como "???" (posição insinuada, identidade oculta). Só exibição.
export function WorldMap({ visited, currentId }: { visited: string[]; currentId: string }) {
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
        const cls =
          "worldmap__node" + (isCurrent ? " is-current" : "") + (known ? "" : " is-fog");
        const title = known ? `${loc.name} · perigo ${loc.danger}\n${loc.lore_seed}` : "Região inexplorada";
        return (
          <div
            key={loc.id}
            className={cls}
            data-danger={loc.danger}
            style={{ left: loc.coords.x + "%", top: loc.coords.y + "%" }}
            title={title}
          >
            <span className="worldmap__dot" />
            <span className="worldmap__label">{known ? loc.name : "???"}</span>
          </div>
        );
      })}
    </div>
  );
}
