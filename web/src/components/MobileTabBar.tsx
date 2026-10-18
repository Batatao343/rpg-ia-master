import { SURFACES, SURFACE_LABELS, type Surface } from "../workspace/mobileSurface";

/** SPEC-216 R2: barra inferior com Chat + 5 abas; alvos >= 44px; `aria-current` só no ativo. */
export function MobileTabBar({ surface, fighting, hidden, onSelect }: {
  surface: Surface;
  fighting: boolean;
  /** Teclado virtual aberto: a barra sai da frente do composer. */
  hidden: boolean;
  onSelect: (surface: Surface) => void;
}) {
  return (
    <nav className="mtabbar" aria-label="Superfícies" hidden={hidden}>
      {SURFACES.map((id) => (
        <button key={id} type="button"
          className={"mtabbar__btn" + (id === "combate" && fighting ? " has-fight" : "")}
          aria-current={surface === id ? "page" : undefined}
          onClick={() => onSelect(id)}>
          {SURFACE_LABELS[id]}
          {id === "combate" && fighting && <span className="mtabbar__dot" aria-hidden="true" />}
        </button>
      ))}
    </nav>
  );
}
