import type { ChaseView, ConflictSceneView } from "../types";

const CHASE_LABEL: Record<string, string> = {
  pressionado: "Pressionado",
  afastado: "Afastado",
  quase_livre: "Quase livre",
  escapou: "Escapou",
  alcancado: "Alcançado",
};

export function SceneZones({ scene, chase }: { scene: ConflictSceneView; chase?: ChaseView }) {
  return (
    <section className="scene-zones" aria-label="Posições da cena">
      {scene.zones.map((zone) => {
        const positions = scene.positions.filter((position) => position.zone_id === zone.id);
        return (
          <article key={zone.id} className="scene-zone">
            <h4>{zone.name}</h4>
            {positions.length ? positions.map((position) => (
              <div key={position.participant_id} className={`scene-pos${position.participant_id === "player" ? " is-player" : ""}`}>
                <strong>{position.participant_name}</strong>
                <span>{position.distance} · {position.posture} · {position.concealment}</span>
                {position.engaged_names.length > 0 && <small>Engajado: {position.engaged_names.join(", ")}</small>}
              </div>
            )) : <p>Zona vazia</p>}
          </article>
        );
      })}
      {chase?.track && (
        <div className="chase-track" role="group" aria-label={`Perseguição: ${CHASE_LABEL[chase.track] ?? chase.track}`}>
          <p>Trilha de perseguição</p>
          <div>
            {(chase.steps ?? ["pressionado", "afastado", "quase_livre", "escapou"]).map((step) => (
              <span key={step} className={chase.track === step ? "is-current" : ""}>{CHASE_LABEL[step] ?? step}</span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
