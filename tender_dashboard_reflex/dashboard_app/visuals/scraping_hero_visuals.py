# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false
"""Isolated hero visual module for scraping page (decorative only)."""

from __future__ import annotations

import reflex as rx


class ScrapingHeroVisualState(rx.State):
    """UI-only state for hero visuals (kept separate from scraping logic)."""

    visual_enabled: bool = True
    visual_hidden: bool = False
    visual_mode: str = "Matrix Rain"

    @rx.var
    def mode_options(self) -> list[str]:
        return ["Data Stream Particles", "Matrix Rain", "World Map Pulse"]

    def set_visual_enabled(self, value: bool):
        self.visual_enabled = bool(value)

    def set_visual_hidden(self, value: bool):
        self.visual_hidden = bool(value)

    def set_visual_mode(self, value: str):
        allowed = {"Data Stream Particles", "Matrix Rain", "World Map Pulse"}
        self.visual_mode = value if value in allowed else "Matrix Rain"


def _matrix_canvas() -> rx.Component:
    return rx.box(
        rx.el.canvas(
            id="hero-matrix-canvas",
            width="1400",
            height="260",
            style={"width": "100%", "height": "180px", "display": "block"},
        ),
        rx.script(
            """
            (() => {
              const canvas = document.getElementById('hero-matrix-canvas');
              if (!canvas) return;
              const ctx = canvas.getContext('2d');
              if (!ctx) return;

              const dpr = window.devicePixelRatio || 1;
              const rect = canvas.getBoundingClientRect();
              canvas.width = Math.floor(rect.width * dpr);
              canvas.height = Math.floor(rect.height * dpr);
              ctx.scale(dpr, dpr);

              const width = rect.width;
              const height = rect.height;
              const fontSize = 14;
              const columns = Math.floor(width / fontSize);
              const drops = Array(columns).fill(0).map(() => Math.random() * -40);
              const chars = '01ABCDEFGHIJKLMNOPQRSTUVWXYZアイウエオカキクケコサシスセソ'.split('');

              const old = canvas._matrixAnim;
              if (old) cancelAnimationFrame(old);

              let rafId = 0;
              const draw = () => {
                ctx.fillStyle = 'rgba(4, 14, 14, 0.18)';
                ctx.fillRect(0, 0, width, height);

                ctx.fillStyle = '#66f7b2';
                ctx.font = `${fontSize}px monospace`;

                for (let i = 0; i < drops.length; i++) {
                  const text = chars[(Math.random() * chars.length) | 0];
                  const x = i * fontSize;
                  const y = drops[i] * fontSize;
                  ctx.fillText(text, x, y);

                  if (y > height && Math.random() > 0.975) drops[i] = 0;
                  drops[i] += 0.55;
                }

                rafId = requestAnimationFrame(draw);
                canvas._matrixAnim = rafId;
              };

              draw();
            })();
            """
        ),
        width="100%",
        min_height="180px",
        border="1px solid",
        border_color="green.7",
        border_radius="10px",
        overflow="hidden",
        background="linear-gradient(180deg, var(--green-2), var(--gray-1))",
    )


def _particle_canvas() -> rx.Component:
    return rx.box(
        rx.el.canvas(
            id="hero-particle-canvas",
            width="1400",
            height="260",
            style={"width": "100%", "height": "180px", "display": "block"},
        ),
        rx.script(
            """
            (() => {
              const canvas = document.getElementById('hero-particle-canvas');
              if (!canvas) return;
              const ctx = canvas.getContext('2d');
              if (!ctx) return;

              const dpr = window.devicePixelRatio || 1;
              const rect = canvas.getBoundingClientRect();
              canvas.width = Math.floor(rect.width * dpr);
              canvas.height = Math.floor(rect.height * dpr);
              ctx.scale(dpr, dpr);

              const width = rect.width;
              const height = rect.height;
              const particles = Array.from({ length: 48 }, (_, i) => ({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.45,
                vy: (Math.random() - 0.5) * 0.45,
                r: 1.5 + Math.random() * 2.8,
              }));

              const old = canvas._particleAnim;
              if (old) cancelAnimationFrame(old);

              let rafId = 0;
              const draw = () => {
                ctx.clearRect(0, 0, width, height);

                for (let i = 0; i < particles.length; i++) {
                  const p = particles[i];
                  p.x += p.vx;
                  p.y += p.vy;
                  if (p.x < 0 || p.x > width) p.vx *= -1;
                  if (p.y < 0 || p.y > height) p.vy *= -1;

                  ctx.beginPath();
                  ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                  ctx.fillStyle = 'rgba(52,211,255,0.80)';
                  ctx.fill();
                }

                for (let i = 0; i < particles.length; i++) {
                  for (let j = i + 1; j < particles.length; j++) {
                    const a = particles[i];
                    const b = particles[j];
                    const dx = a.x - b.x;
                    const dy = a.y - b.y;
                    const d = Math.sqrt(dx * dx + dy * dy);
                    if (d < 95) {
                      ctx.strokeStyle = `rgba(80,180,255,${(1 - d / 95) * 0.35})`;
                      ctx.lineWidth = 1;
                      ctx.beginPath();
                      ctx.moveTo(a.x, a.y);
                      ctx.lineTo(b.x, b.y);
                      ctx.stroke();
                    }
                  }
                }

                rafId = requestAnimationFrame(draw);
                canvas._particleAnim = rafId;
              };

              draw();
            })();
            """
        ),
        width="100%",
        min_height="180px",
        border="1px solid",
        border_color="cyan.7",
        border_radius="10px",
        overflow="hidden",
        background="radial-gradient(circle at 20% 20%, var(--cyan-3), var(--gray-1) 70%)",
    )


def _world_map_visual() -> rx.Component:
    points = [
        ("USA", "22%", "36%"),
        ("EU", "47%", "30%"),
        ("India", "62%", "46%"),
        ("SEA", "71%", "54%"),
        ("Australia", "82%", "72%"),
    ]
    return rx.box(
        rx.el.style(
            """
            @keyframes heroPulseRing {
              0% { transform: scale(0.4); opacity: 0.85; }
              100% { transform: scale(2.1); opacity: 0; }
            }
            """
        ),
        rx.box(
            rx.foreach(
                points,
                lambda p: rx.box(
                    rx.box(
                        width="10px",
                        height="10px",
                        border_radius="9999px",
                        background="orange.9",
                        box_shadow="0 0 12px rgba(255,166,0,0.8)",
                    ),
                    rx.box(
                        width="10px",
                        height="10px",
                        border_radius="9999px",
                        border="2px solid rgba(255,166,0,0.7)",
                        position="absolute",
                        top="0",
                        left="0",
                        style={"animation": "heroPulseRing 1.8s ease-out infinite"},
                    ),
                    rx.text(p[0], size="1", color="blue.11", margin_top="0.4rem"),
                    position="absolute",
                    left=p[1],
                    top=p[2],
                ),
            ),
            width="100%",
            min_height="180px",
            position="relative",
            border="1px solid",
            border_color="blue.7",
            border_radius="10px",
            overflow="hidden",
            background="linear-gradient(160deg, var(--blue-2), var(--gray-2))",
        ),
        width="100%",
    )


def hero_visual_section() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("🎬 Scraper Hero Visual", size="4", weight="bold"),
                rx.spacer(),
                rx.select(
                    ScrapingHeroVisualState.mode_options,
                    value=ScrapingHeroVisualState.visual_mode,
                    on_change=ScrapingHeroVisualState.set_visual_mode,
                    size="2",
                    width="240px",
                ),
                spacing="2",
                width="100%",
                align="center",
            ),
            rx.hstack(
                rx.hstack(
                    rx.switch(
                        checked=ScrapingHeroVisualState.visual_enabled,
                        on_change=ScrapingHeroVisualState.set_visual_enabled,
                        size="2",
                    ),
                    rx.text("Visuals On", size="2", color="gray.11"),
                    spacing="2",
                    align="center",
                ),
                rx.hstack(
                    rx.switch(
                        checked=ScrapingHeroVisualState.visual_hidden,
                        on_change=ScrapingHeroVisualState.set_visual_hidden,
                        size="2",
                    ),
                    rx.text("Hide Hero", size="2", color="gray.11"),
                    spacing="2",
                    align="center",
                ),
                spacing="4",
                width="100%",
            ),
            rx.cond(
                ScrapingHeroVisualState.visual_hidden,
                rx.callout(rx.text("Hero visuals are hidden.", size="2"), color_scheme="gray", size="1"),
                rx.cond(
                    ~ScrapingHeroVisualState.visual_enabled,
                    rx.callout(rx.text("Hero visuals are turned off.", size="2"), color_scheme="gray", size="1"),
                    rx.cond(
                        ScrapingHeroVisualState.visual_mode == "Matrix Rain",
                        _matrix_canvas(),
                        rx.cond(
                            ScrapingHeroVisualState.visual_mode == "Data Stream Particles",
                            _particle_canvas(),
                            _world_map_visual(),
                        ),
                    ),
                ),
            ),
            spacing="3",
            width="100%",
        ),
        size="2",
        width="100%",
    )
