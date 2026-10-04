"use client";

import { useEffect, useRef } from "react";

/**
 * A quiet, fixed-position starfield for the dark "mission control" theme —
 * small twinkling dots plus a couple of slow-drifting "satellites". Pure
 * canvas, no external image/asset. No-ops (and stays invisible) in light
 * mode via the data-theme attribute check.
 */
export function Starfield() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let width = 0;
    let height = 0;
    let stars: { x: number; y: number; r: number; phase: number; speed: number }[] = [];

    interface ShootingStar {
      x: number;
      y: number;
      vx: number;
      vy: number;
      life: number; // 0..1, counts down
    }
    let shootingStars: ShootingStar[] = [];
    let nextShootingStarAt = 4 + Math.random() * 8;

    function resize() {
      const c = canvasRef.current;
      if (!c) return;
      width = window.innerWidth;
      height = window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      c.width = width * dpr;
      c.height = height * dpr;
      c.style.width = `${width}px`;
      c.style.height = `${height}px`;
      ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);

      const count = Math.round((width * height) / 9000);
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        r: Math.random() * 1.3 + 0.3,
        phase: Math.random() * Math.PI * 2,
        speed: 0.4 + Math.random() * 0.8,
      }));
    }

    function isDark() {
      return document.documentElement.getAttribute("data-theme") !== "light";
    }

    let t = 0;
    const dt = 0.016;
    function frame() {
      raf = requestAnimationFrame(frame);
      if (!ctx) return;
      ctx.clearRect(0, 0, width, height);
      if (!isDark()) return;
      t += dt;

      for (const s of stars) {
        const twinkle = 0.55 + 0.45 * Math.sin(t * s.speed + s.phase);
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(200, 220, 255, ${twinkle * 0.85})`;
        ctx.fill();
      }

      // Occasional shooting star — a rare, subtle flourish, not a loop of
      // distracting motion. One at a time, random interval between them.
      nextShootingStarAt -= dt;
      if (nextShootingStarAt <= 0 && shootingStars.length === 0) {
        const startX = Math.random() * width * 0.6 + width * 0.1;
        const angle = (Math.PI / 5) + Math.random() * (Math.PI / 8);
        const speed = 900 + Math.random() * 400;
        shootingStars.push({
          x: startX,
          y: -20,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          life: 1,
        });
        nextShootingStarAt = 9 + Math.random() * 14;
      }

      shootingStars = shootingStars.filter((star) => star.life > 0);
      for (const star of shootingStars) {
        const prevX = star.x;
        const prevY = star.y;
        star.x += star.vx * dt;
        star.y += star.vy * dt;
        star.life -= dt * 1.1;
        if (star.x > width + 40 || star.y > height + 40) {
          star.life = 0;
          continue;
        }
        const grad = ctx.createLinearGradient(prevX, prevY, star.x, star.y);
        grad.addColorStop(0, "rgba(200, 220, 255, 0)");
        grad.addColorStop(1, `rgba(220, 235, 255, ${Math.max(star.life, 0)})`);
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(prevX, prevY);
        ctx.lineTo(star.x, star.y);
        ctx.stroke();
      }
    }

    resize();
    frame();
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <div className="starfield-host">
      <canvas ref={canvasRef} />
    </div>
  );
}
