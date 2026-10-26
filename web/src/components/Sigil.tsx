/**
 * Sigilo de Valoria (SPEC-323 R8): o Abismo (fenda vertical no anel) cercado pelos Cinco Sinos
 * (cinco badaladas em pentágono). Desenho original; herda `currentColor` (casa com a paleta).
 */
const BELLS = Array.from({ length: 5 }, (_, i) => {
  const a = -Math.PI / 2 + (i / 5) * Math.PI * 2;
  return { x: 20 + Math.cos(a) * 14, y: 20 + Math.sin(a) * 14 };
});

export function Sigil({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden>
      <circle cx="20" cy="20" r="18.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="20" cy="20" r="10" stroke="currentColor" strokeWidth="0.7" opacity="0.55" />
      {BELLS.map((b, i) => (
        <circle key={i} cx={b.x} cy={b.y} r="1.7" fill="currentColor" opacity="0.85" />
      ))}
      <path
        d="M20 9.5 L22.6 20 L20 30.5 L17.4 20 Z"
        stroke="currentColor"
        strokeWidth="1.1"
        fill="currentColor"
        fillOpacity="0.14"
        strokeLinejoin="round"
      />
    </svg>
  );
}
