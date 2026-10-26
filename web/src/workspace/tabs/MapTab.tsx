import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import * as api from "../../api";
import { VisualArtwork } from "../../components/VisualArtwork";
import { WorldMap } from "../../components/WorldMap";
import type { GameResponse, MapNodeView, MapTravelOption, MapView } from "../../types";
import { nextNodeIndex, periodsLabel, placeLabels } from "./mapModel";
import "./map.css";
import { Icon, type IconName } from "../../design/icons";

const STATE_TEXT: Record<MapNodeView["state"], string> = {
  atual: "local atual",
  visitado: "visitado",
  adjacente: "ainda não visitado",
  bloqueado: "rota bloqueada",
};
const STATE_ICON: Record<MapNodeView["state"], IconName> = { atual: "pin", visitado: "visited", adjacente: "adjacent", bloqueado: "blocked" };

/** SPEC-210: aba Mapa. Dados SÓ da view do servidor (visitados + adjacentes); viajar é
 *  uma ação de chat comum (`Viajo para <nome>`), nunca mutação local. */
export function MapTab({ data, busy, blocked, open, onAction }: {
  data: GameResponse | null;
  busy: boolean;
  blocked: boolean;
  open: boolean;
  onAction: (text: string) => void;
}) {
  const gameId = data?.game_id;
  const turn = data?.world.turn_count ?? 0;
  const [view, setView] = useState<MapView | null>(null);
  const [failed, setFailed] = useState(false);
  const [stale, setStale] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const viewGame = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!gameId || !open) return;
    let alive = true;
    // Troca de save: nunca mostrar o mapa do jogo anterior.
    if (viewGame.current !== gameId) { setView(null); setSelected(null); setFailed(false); }
    viewGame.current = gameId;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    setLoading(true);
    api.getGameMap(gameId)
      .then((v) => { if (alive) { setView(v); setStale(false); setFailed(false); } })
      .catch(() => { if (alive) { setStale(true); setFailed(true); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [gameId, turn, open]);

  if (!gameId) return <p className="combat-empty">Sem campanha ativa.</p>;
  if (!view) {
    if (failed) {
      // R12: backend sem a view -> fog do cliente sobre o legado filtrado por jogo.
      return (
        <WorldMap
          gameId={gameId}
          visited={data?.world.visited ?? []}
          currentId={data?.world.location_id ?? ""}
          controlled={data?.world.controlled ?? {}}
          dangerOverrides={data?.world.danger_overrides ?? {}}
          markers={data?.quest.markers ?? []}
          overlays={data?.world.map_overlays}
          currentTurn={turn}
          blockedRoutes={data?.world.blocked_routes ?? []}
          onTravel={(location) => onAction(`Viajo para ${location.name}`)}
        />
      );
    }
    return <p className="combat-empty" aria-live="polite">Consultando o mapa da jornada…</p>;
  }
  return <MapBody view={view} stale={stale} loading={loading} busy={busy} blocked={blocked}
    selected={selected} onSelect={setSelected} onAction={onAction} />;
}

function MapBody({ view, stale, loading, busy, blocked, selected, onSelect, onAction }: {
  view: MapView; stale: boolean; loading: boolean; busy: boolean; blocked: boolean;
  selected: string | null; onSelect: (id: string) => void; onAction: (text: string) => void;
}) {
  const byId = new Map(view.nodes.map((n) => [n.id, n]));
  const sel = byId.get(selected ?? "") ?? byId.get(view.anchor_id) ?? view.nodes[0];
  const opt = view.travel_options.find((o) => o.location_id === sel?.id);
  const refs = useRef(new Map<string, HTMLButtonElement>());
  const canvasRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 640, h: 380 });
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const measure = () => { const r = el.getBoundingClientRect(); if (r.width > 0) setSize((s) => (Math.abs(s.w - r.width) < 1 && Math.abs(s.h - r.height) < 1 ? s : { w: r.width, h: r.height })); };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  // Anti-colisão de rótulos: atual/selecionado/missão primeiro; o que não cabe esconde o rótulo (o nome fica no aria-label/title).
  const sides = useMemo(() => placeLabels(view.nodes.map((n) => ({
    id: n.id, x: n.coords.x, y: n.coords.y, chars: n.name.length,
    priority: (n.id === sel?.id ? 100 : 0) + (n.state === "atual" ? 50 : 0) + (n.quest_target ? 20 : 0) + (n.threatened ? 10 : 0)
      + (n.state === "visitado" ? 5 : 0),
  })), size), [view.nodes, sel?.id, size]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const id = (event.target as HTMLElement).dataset.nodeId;
    if (!id) return;
    const i = view.nodes.findIndex((n) => n.id === id);
    const j = nextNodeIndex(view.nodes.map((n) => n.coords), i, event.key);
    if (j >= 0) { event.preventDefault(); refs.current.get(view.nodes[j].id)?.focus(); }
  }

  return (
    <div className="maptab" data-map-version={view.map_version}>
      <p className="maptab__status" aria-live="polite">
        {stale ? "Mapa desatualizado: mostrando o último estado conhecido." : loading ? "Atualizando…" : ""}
      </p>
      {view.looming_threat && <p className="worldmap__banner"><Icon name="warning" /> {view.looming_threat}</p>}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- atalho de teclado delegado: só reage a teclas que borbulham de controles focáveis internos */}
      <div className="worldmap maptab__canvas" ref={canvasRef} role="group" aria-label="Mapa da jornada" onKeyDown={onKeyDown}>
        <svg className="worldmap__edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {view.edges.map((e) => {
            const a = byId.get(e.a); const b = byId.get(e.b);
            if (!a || !b) return null;
            return <line key={e.a + e.b} className={"worldmap__edge" + (e.blocked ? " is-blocked" : "")}
              x1={a.coords.x} y1={a.coords.y} x2={b.coords.x} y2={b.coords.y} />;
          })}
        </svg>
        {view.nodes.map((n) => {
          const cost = view.travel_options.find((o) => o.location_id === n.id);
          const cls = "worldmap__node maptab__node is-" + n.state
            + (n.id === sel?.id ? " is-selected" : "")
            + (n.ruler ? " is-controlled" : "") + (n.quest_target ? " is-quest-target" : "")
            + (n.contested ? " is-contested" : "") + (n.threatened ? " is-threatened" : "")
            + (n.state === "atual" ? " is-current" : "") + " label-" + (sides[n.id] ?? "below");
          return (
            <button type="button" key={n.id} className={cls} data-node-id={n.id} data-danger={n.danger}
              data-effect="map.marker" data-effect-state={n.state === "atual" ? "current" : "travelable"}
              style={{ left: n.coords.x + "%", top: n.coords.y + "%" }}
              ref={(el) => { if (el) refs.current.set(n.id, el); else refs.current.delete(n.id); }}
              aria-pressed={n.id === sel?.id} title={n.name}
              aria-label={`${n.name}, ${STATE_TEXT[n.state]}${cost ? `, ${periodsLabel(cost.periods)}` : ""}`
                + (n.quest_target ? ", objetivo de missão" : "") + (n.ruler ? `, sob domínio de ${n.ruler}` : "")
                + (n.danger !== undefined ? `, perigo ${n.danger}` : "")}
              onClick={() => onSelect(n.id)}>
              <span className="worldmap__dot" />
              <span className="worldmap__label">
                <Icon name={n.threatened ? "warning" : n.ruler ? "ruler" : n.quest_target ? "quest" : STATE_ICON[n.state]} />{" "}{n.name}
              </span>
            </button>
          );
        })}
      </div>
      {sel && <MapDetail node={sel} option={opt} view={view} busy={busy} blocked={blocked} onAction={onAction} />}
    </div>
  );
}

function MapDetail({ node, option, view, busy, blocked, onAction }: {
  node: MapNodeView; option?: MapTravelOption; view: MapView; busy: boolean; blocked: boolean;
  onAction: (text: string) => void;
}) {
  const known = node.lore_seed !== undefined;
  const gate = view.travel_gate;
  let reason = "";
  // Dentro de interior a âncora é o pai e a saída (custo 0) é uma travel_option real.
  if (node.state === "atual" && !option) reason = "Você já está aqui.";
  else if (!option) reason = node.reason || "Sem rota direta daqui.";
  else if (option.blocked || !option.reachable) reason = option.reason || "Rota bloqueada.";
  else if (gate.blocked) reason = gate.reason;
  else if (busy || blocked) reason = "Aguarde o turno atual terminar.";
  const canTravel = !reason && !!option;
  return (
    <section className="maptab__detail" aria-label={`Detalhe de ${node.name}`}>
      {known && node.art && (
        <VisualArtwork asset={node.art.asset} name={node.name} variant="card" expandable={false}
          caption={node.art.scope === "regional" ? "Arte da região" : node.art.scope === "placeholder" ? "Sem arte" : undefined} />
      )}
      <h3 className="maptab__name">{node.name}</h3>
      <p className="maptab__meta">
        <Icon name={STATE_ICON[node.state]} />{" "}{STATE_TEXT[node.state]}
        {known && node.danger !== undefined && <> · perigo {node.danger}</>}
        {option && <> · {periodsLabel(option.periods)}</>}
      </p>
      {node.ruler && <p className="maptab__meta"><Icon name="ruler" /> Sob domínio de {node.ruler}</p>}
      {node.quest_target && <p className="maptab__meta"><Icon name="quest" /> Objetivo de missão</p>}
      {node.threatened && <p className="maptab__meta"><Icon name="warning" /> Ameaça: {node.threat_hint}</p>}
      {node.contested && <p className="maptab__meta">Controle mudou recentemente</p>}
      {known ? <p className="maptab__lore">{node.lore_seed}</p>
        : <p className="maptab__lore">Região inexplorada. Só se sabe o nome na estrada.</p>}
      {node.state === "atual" && view.interiors.here.length > 0 && (
        <div>
          <h3 className="hud__label hud__label--sub">Locais daqui</h3>
          <ul className="maptab__list">{view.interiors.here.map((i) => <li key={i.id}>{i.name}</li>)}</ul>
        </div>
      )}
      {view.interiors.exit_to && node.id === view.anchor_id && (
        <p className="maptab__meta">Saída: {view.interiors.exit_to.name}</p>
      )}
      <button type="button" className="btn btn--primary maptab__travel" disabled={!canTravel}
        aria-describedby={reason ? "maptab-travel-reason" : undefined}
        onClick={() => option && onAction(`Viajo para ${option.name}`)}>
        Viajar{option ? ` · ${periodsLabel(option.periods)}` : ""}
      </button>
      {reason && <p id="maptab-travel-reason" className="maptab__reason">{reason}</p>}
    </section>
  );
}
