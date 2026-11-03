import type { CreatureSaber } from "../types";

const SINAL_LABEL: Record<string, string> = { rastro: "Rastro", resto: "Restos", som: "Som", cheiro: "Cheiro", marca: "Marca" };

/** SPEC-371 R15: o que o jogador leu, viu e aprendeu sobre a criatura (só com `RPG_FAUNA_SABER=on`). */
export function FaunaSaber({ saber }: { saber: CreatureSaber }) {
  const { sinais_vistos: sinais, telegrafos_vistos: telegrafos, contra_jogo: contra, contra_jogo_motivo: motivo } = saber;
  return (
    <>
      {sinais && sinais.length > 0 && (
        <div data-saber="sinais">
          <p className="codex-entry__meta">Rastros lidos</p>
          {sinais.map((s) => (
            <p key={s.tipo} className="codex-entry__body">
              {SINAL_LABEL[s.tipo] ?? s.tipo}: <em>{s.texto}</em>
            </p>
          ))}
        </div>
      )}
      {telegrafos && telegrafos.length > 0 && (
        <div data-saber="telegrafos">
          <p className="codex-entry__meta">Presságios testemunhados</p>
          {telegrafos.map((t) => <p key={t} className="codex-entry__body">{t}</p>)}
        </div>
      )}
      {contra && (
        <div data-saber="contra-jogo">
          <p className="codex-entry__meta">Como se luta</p>
          <p className="codex-entry__body">{contra}</p>
          {motivo && <p className="codex-entry__meta">{motivo}</p>}
        </div>
      )}
    </>
  );
}
