import { useEffect, useRef } from "react";

// Brasas/poeira subindo, leves, atrás do conteúdo. Desligado em reduced-motion.
export function EmberField() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let w = 0, h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    type P = { x: number; y: number; r: number; vy: number; vx: number; a: number; tw: number };
    let parts: P[] = [];

    function resize() {
      w = canvas!.clientWidth; h = canvas!.clientHeight;
      canvas!.width = w * dpr; canvas!.height = h * dpr;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.round((w * h) / 42000); // densidade modesta
      parts = Array.from({ length: count }, () => spawn(true));
    }
    function spawn(anywhere: boolean): P {
      return {
        x: Math.random() * w,
        y: anywhere ? Math.random() * h : h + 8,
        r: 0.6 + Math.random() * 1.6,
        vy: 0.15 + Math.random() * 0.5,
        vx: (Math.random() - 0.5) * 0.25,
        a: 0.12 + Math.random() * 0.35,
        tw: Math.random() * Math.PI * 2,
      };
    }

    function frame() {
      ctx!.clearRect(0, 0, w, h);
      for (const p of parts) {
        p.y -= p.vy;
        p.x += p.vx;
        p.tw += 0.05;
        if (p.y < -8) Object.assign(p, spawn(false));
        const flick = 0.65 + Math.sin(p.tw) * 0.35;
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx!.fillStyle = `oklch(0.78 0.13 70 / ${(p.a * flick).toFixed(3)})`;
        ctx!.shadowBlur = 6;
        ctx!.shadowColor = "oklch(0.72 0.12 70 / 0.6)";
        ctx!.fill();
      }
      ctx!.shadowBlur = 0;
      raf = requestAnimationFrame(frame);
    }

    resize();
    window.addEventListener("resize", resize);
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className="ember-canvas" aria-hidden />;
}
