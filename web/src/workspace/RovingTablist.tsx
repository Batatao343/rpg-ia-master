import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { Selectable } from "../design/primitives";

export interface TabItem<T extends string> {
  id: T;
  label: ReactNode;
  className?: string;
}

/** SPEC-204 R4 / SPEC-201 A06 (M19): tablist com foco roving (←/→/Home/End),
 *  `tabIndex=-1` nas inativas e ativação ao mover o foco. */
export function RovingTablist<T extends string>({ items, selected, onSelect, label, idPrefix, className, tabClassName, controlsActiveOnly }: {
  items: TabItem<T>[];
  selected: T;
  onSelect: (id: T) => void;
  label: string;
  idPrefix: string;
  className?: string;
  tabClassName?: string;
  /** Painéis inativos não existem no DOM: só a aba ativa aponta aria-controls. */
  controlsActiveOnly?: boolean;
}) {
  const refs = useRef(new Map<T, HTMLButtonElement>());

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const index = items.findIndex((item) => item.id === selected);
    let next = -1;
    if (event.key === "ArrowRight") next = (index + 1) % items.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + items.length) % items.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = items.length - 1;
    if (next < 0) return;
    event.preventDefault();
    const id = items[next].id;
    onSelect(id);
    refs.current.get(id)?.focus();
  }

  return (
    // eslint-disable-next-line jsx-a11y/interactive-supports-focus -- foco roving: o tablist delega o foco aos botões role=tab (tabIndex 0/-1)
    <div role="tablist" aria-label={label} className={className} onKeyDown={onKeyDown}>
      {items.map((item) => {
        const active = item.id === selected;
        return (
          <button
            key={item.id}
            ref={(node) => { if (node) refs.current.set(item.id, node); else refs.current.delete(item.id); }}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${item.id}`}
            aria-selected={active}
            aria-controls={active || !controlsActiveOnly ? `${idPrefix}-panel-${item.id}` : undefined}
            tabIndex={active ? 0 : -1}
            className={[tabClassName, active ? "is-active" : "", item.className].filter(Boolean).join(" ")}
            onClick={() => onSelect(item.id)}
          >
            <Selectable selected={active} layoutId={`${idPrefix}-indicator`}>{item.label}</Selectable>
          </button>
        );
      })}
    </div>
  );
}
