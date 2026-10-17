import { Component, useLayoutEffect, useRef, type ErrorInfo, type KeyboardEvent, type ReactNode } from "react";
import type { ActionOptions, GameResponse } from "../types";
import { ChronicleTab, FactionsTab, PeopleTab, type EquipFn } from "../components/Hud";
import { CodexCategory, CodexTab, DossierCategory, type CodexSection } from "../components/CodexTab";
import { WorldMap } from "../components/WorldMap";
import { RovingTablist } from "./RovingTablist";
import { CONTEXT_TABS, TAB_LABELS, type ContextTab } from "./workspaceModel";
import { PersonagemTab } from "./tabs/PersonagemTab";
import { CombateTab } from "./tabs/CombateTab";
import { BestiarioTab } from "./tabs/BestiarioTab";

const LAB_EMPTY = "Laboratório de combate: sem campanha, este registro fica vazio.";

class PanelBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { /* o chat segue intacto */ }
  render() {
    return this.state.failed
      ? <p className="combat-empty" role="alert">Este painel falhou ao carregar. O chat continua disponível.</p>
      : this.props.children;
  }
}

export interface ContextSurfaceProps {
  data: GameResponse | null;
  active: boolean;
  tab: ContextTab;
  visited: ReadonlySet<ContextTab>;
  busy: boolean;
  blocked: boolean;
  hitKey: number;
  combatEnded: boolean;
  reactionCardId?: string;
  codexSection?: string;
  onCodexSection: (id: string) => void;
  onReaction: (cardId?: string) => void;
  onSelectTab: (tab: ContextTab) => void;
  onClose: () => void;
  onEscape: () => void;
  onAction: (text: string, options?: ActionOptions) => void;
  onEquip?: EquipFn;
  onPrepareCards?: (prepared: string[]) => Promise<string | null>;
  onOpenLevelUp?: () => void;
}

/** SPEC-204: UM painel de contexto com cinco abas. Abas já visitadas ficam montadas
 *  (ocultas) para preservar estado e scroll interno (R7). */
export function ContextSurface(props: ContextSurfaceProps) {
  const { data, active, tab, visited, onSelectTab, onClose, onEscape } = props;
  const fighting = !!data?.combat?.active;
  const scrolls = useRef(new Map<ContextTab, number>());
  const panels = useRef(new Map<ContextTab, HTMLDivElement>());

  useLayoutEffect(() => {
    const panel = panels.current.get(tab);
    if (panel && active) panel.scrollTop = scrolls.current.get(tab) ?? 0;
  }, [tab, active]);

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    const target = event.target as HTMLElement;
    if (target.closest("dialog, [role='dialog']")) return;
    event.preventDefault();
    onEscape();
  }

  return (
    <section className="ws-ctx" aria-label="Painel de contexto" hidden={!active} onKeyDown={onKeyDown}>
      <div className="ws-ctx__head">
        <RovingTablist<ContextTab>
          items={CONTEXT_TABS.map((id) => ({
            id, label: TAB_LABELS[id],
            className: id === "combate" ? "is-combat" + (fighting ? " has-fight" : "") : undefined,
          }))}
          selected={tab} onSelect={onSelectTab} label="Abas do painel" idPrefix="ws"
          className="tabs ws-tabs" tabClassName="tab" />
        <button type="button" className="iconbtn ws-ctx__close" aria-label="Fechar ficha" onClick={onClose}>×</button>
      </div>
      {CONTEXT_TABS.map((id) => (
        <div key={id} role="tabpanel" id={`ws-panel-${id}`} aria-labelledby={`ws-tab-${id}`}
          className="tabpanel ws-panel" tabIndex={0} hidden={id !== tab}
          ref={(node) => { if (node) panels.current.set(id, node); else panels.current.delete(id); }}
          onScroll={(event) => {
            if (id === tab && active) scrolls.current.set(id, event.currentTarget.scrollTop);
          }}>
          {visited.has(id) && <PanelBoundary>{renderTab(id, props)}</PanelBoundary>}
        </div>
      ))}
    </section>
  );
}

function renderTab(id: ContextTab, props: ContextSurfaceProps): ReactNode {
  const { data, active, tab, busy, blocked, hitKey } = props;
  const simulation = !!data?.combat_simulation?.enabled;
  const open = active && tab === id;
  switch (id) {
    case "personagem":
      return <PersonagemTab data={data} hitKey={hitKey} onEquip={props.onEquip} busy={busy} />;
    case "combate":
      return <CombateTab data={data} busy={busy} blocked={blocked} hitKey={hitKey} ended={props.combatEnded}
        reactionCardId={props.reactionCardId} onReaction={props.onReaction} onAction={props.onAction}
        onPrepareCards={props.onPrepareCards} onOpenLevelUp={props.onOpenLevelUp} />;
    case "bestiario":
      return <BestiarioTab gameId={data?.game_id} turnCount={data?.world.turn_count} open={open}
        unavailable={simulation ? LAB_EMPTY : undefined} />;
    case "mapa":
      if (simulation) return <div><p className="hud__label">Mapa do mundo</p><p className="combat-empty">{LAB_EMPTY}</p></div>;
      return (
        <div>
          <p className="hud__label">Mapa do mundo</p>
          <WorldMap
            visited={data?.world.visited ?? []}
            currentId={data?.world.location_id ?? ""}
            controlled={data?.world.controlled ?? {}}
            dangerOverrides={data?.world.danger_overrides ?? {}}
            markers={data?.quest.markers ?? []}
            overlays={data?.world.map_overlays}
            currentTurn={data?.world.turn_count ?? 0}
            blockedRoutes={data?.world.blocked_routes ?? []}
            onTravel={(location) => props.onAction(`Viajo para ${location.name}`)}
          />
        </div>
      );
    case "codex": {
      const sections: CodexSection[] = [
        { id: "pessoas", label: "Pessoas", before: "characters",
          // Sem dossiê de NPC (endpoint indisponível ou nenhum NPC visível ainda) mantém a lista do HUD;
          // o servidor já filtra NPC oculto de `data.npcs` (`_npcs_block`).
          render: (_codex, dossiers) => dossiers && dossiers.sections.npcs.length > 0 && data?.game_id ? (
            <DossierCategory dossiers={dossiers} gameId={data.game_id} category="characters"
              turnCount={data.world.turn_count} />
          ) : <PeopleTab npcs={data?.npcs ?? []} /> },
        { id: "faccoes", label: "Fações", before: "secrets",
          render: (codex, dossiers) => (
            <>
              <FactionsTab factions={data?.factions ?? []} />
              {dossiers && data?.game_id && dossiers.sections.factions.length > 0 && (
                <div>
                  <p className="hud__label hud__label--sub">Dossiês do Codex</p>
                  <DossierCategory dossiers={dossiers} gameId={data.game_id} category="factions"
                    turnCount={data.world.turn_count} />
                </div>
              )}
              {!dossiers && codex && codex.factions.length > 0 && (
                <div>
                  <p className="hud__label hud__label--sub">Registros do Codex</p>
                  <CodexCategory codex={codex} category="factions" />
                </div>
              )}
            </>
          ) },
        { id: "cronica", label: "Crônica",
          render: () => <ChronicleTab chapters={data?.chronicle ?? []} gameId={data?.game_id}
                                projectionStatus={data?.projections?.chronicle?.status} /> },
      ];
      return <CodexTab gameId={data?.game_id} turnCount={data?.world.turn_count} open={open}
        excludeCategories={["creatures", "factions"]} sections={sections}
        section={props.codexSection} onSection={props.onCodexSection}
        unavailable={simulation ? LAB_EMPTY : undefined} />;
    }
  }
}
