import { useEffect, useRef } from "react";

// Brasas/poeira subindo, leves, atrás do conteúdo. Desligado em reduced-motion.
export function EmberField() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    // ember.pause (M25, R9/R10): reage a preferência de movimento, aba oculta e kill switch.
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
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
      const count = Math.min(40, Math.round((w * h) / 60000)); // densidade modesta + teto (R9)
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

    // R9: não anima atrás do chat durante o combate (a leitura/mira tem prioridade).
    const inCombat = () => !!document.querySelector(".play.is-combat");
    const canRun = () => !mq.matches && document.visibilityState !== "hidden"
      && document.documentElement.dataset.effects !== "off" && !inCombat();
    let lastDraw = 0;
    let poll = 0;
    function frame(now: number) {
      if (now - lastDraw < 33) { raf = requestAnimationFrame(frame); return; } // ~30 fps
      lastDraw = now;
      if (!canRun()) { raf = 0; ctx!.clearRect(0, 0, w, h); poll = window.setTimeout(sync, 500); return; }
      canvas!.dataset.frames = String((Number(canvas!.dataset.frames) || 0) + 1);
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
        ctx!.fill();
      }
      raf = requestAnimationFrame(frame);
    }

    function sync() {
      clearTimeout(poll);
      if (canRun()) { if (!raf) raf = requestAnimationFrame(frame); }
      else { cancelAnimationFrame(raf); raf = 0; ctx!.clearRect(0, 0, w, h); poll = window.setTimeout(sync, 500); }
    }

    resize();
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", sync);
    mq.addEventListener?.("change", sync);
    canvas.dataset.effect = "ember.pause";
    sync();
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(poll);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", sync);
      mq.removeEventListener?.("change", sync);
    };
  }, []);

  return <canvas ref={ref} className="ember-canvas" aria-hidden />;
}
