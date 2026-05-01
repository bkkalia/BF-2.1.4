# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false
"""Isolated hero visual module for scraping page (decorative only)."""

from __future__ import annotations

import reflex as rx


class ScrapingHeroVisualState(rx.State):
    """UI-only state for hero visuals (kept separate from scraping logic)."""

    visual_enabled: bool = True
    visual_hidden: bool = False
    visual_mode: str = "Matrix Rain"
    show_fullscreen_intro: bool = True

    @rx.var
    def mode_options(self) -> list[str]:
        return ["Matrix Rain", "World Map Pulse"]

    def set_visual_enabled(self, value: bool):
        self.visual_enabled = bool(value)

    def set_visual_hidden(self, value: bool):
        self.visual_hidden = bool(value)

    def set_visual_mode(self, value: str):
        allowed = {"Matrix Rain", "World Map Pulse"}
        self.visual_mode = value if value in allowed else "Matrix Rain"

    def close_fullscreen_intro(self):
        self.show_fullscreen_intro = False

    def open_fullscreen_intro(self):
        self.show_fullscreen_intro = True


def _matrix_canvas(height: str = "180px") -> rx.Component:
    return rx.box(
                rx.el.canvas(
                        id="hero-matrix-canvas",
                        width="500",
                        height="200",
                    style={"width": "100%", "height": height, "display": "block"},
                ),
                rx.script(
            """
                        (() => {
                            const KEY = '__heroMatrixRuntime';

                            if (window[KEY] && typeof window[KEY].stop === 'function') {
                                try { window[KEY].stop(); } catch (_) {}
                            }

                            let canvas = null;
                            let ctx = null;
                            let timer = null;
                            let reflowTimer = null;
                            let observer = null;
                            let w = 0;
                            let h = 0;
                            let cols = 0;
                            let ypos = [];

                            const getCanvas = () => document.getElementById('hero-matrix-canvas');

                            const resize = (force = false) => {
                                if (!canvas || !ctx) return;
                                const rect = canvas.getBoundingClientRect();
                                const parent = canvas.parentElement;
                                const nextW = Math.max(1, Math.floor((parent ? parent.clientWidth : 0) || rect.width || window.innerWidth || 1));
                                const nextH = Math.max(1, Math.floor((parent ? parent.clientHeight : 0) || rect.height || 180));
                                if (!force && nextW === w && nextH === h) return;

                                canvas.width = nextW;
                                canvas.height = nextH;
                                w = nextW;
                                h = nextH;
                                cols = Math.floor(w / 20) + 1;
                                ypos = Array(cols).fill(0);

                                ctx.fillStyle = '#000';
                                ctx.fillRect(0, 0, w, h);
                            };

                            const draw = () => {
                                if (!canvas || !canvas.isConnected || !ctx) return;
                                resize(false);

                                ctx.fillStyle = '#0001';
                                ctx.fillRect(0, 0, w, h);

                                ctx.fillStyle = '#0f0';
                                ctx.font = '15pt monospace';

                                ypos.forEach((y, ind) => {
                                    const text = String.fromCharCode((Math.random() * 128) | 0);
                                    const x = ind * 20;
                                    ctx.fillText(text, x, y);
                                    if (y > 100 + Math.random() * 10000) ypos[ind] = 0;
                                    else ypos[ind] = y + 20;
                                });
                            };

                            const bind = (target) => {
                                if (!target) return;
                                if (canvas === target && timer) return;

                                canvas = target;
                                ctx = canvas.getContext('2d');
                                if (!ctx) return;

                                resize(true);
                                if (timer) clearInterval(timer);
                                timer = setInterval(draw, 50);
                                draw();
                            };

                            bind(getCanvas());

                            observer = new MutationObserver(() => {
                                const latest = getCanvas();
                                if (latest && latest !== canvas) bind(latest);
                            });
                            observer.observe(document.body, { childList: true, subtree: true });

                            const onResize = () => resize(true);
                            window.addEventListener('resize', onResize);
                            reflowTimer = setInterval(() => resize(false), 300);

                            window[KEY] = {
                                stop: () => {
                                    if (timer) clearInterval(timer);
                                    timer = null;
                                    if (reflowTimer) clearInterval(reflowTimer);
                                    reflowTimer = null;
                                    if (observer) observer.disconnect();
                                    observer = null;
                                    window.removeEventListener('resize', onResize);
                                },
                            };
                        })();
            """
        ),
        width="100%",
        height=height,
        border="1px solid",
        border_color="green.7",
        border_radius="10px",
        overflow="hidden",
                background="black",
    )


def _fullscreen_matrix_intro() -> rx.Component:
    return rx.box(
        rx.script(
            """
            (() => {
              if (window.__heroEscBound) return;
              window.__heroEscBound = true;
              window.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') {
                  const btn = document.getElementById('hero-intro-close-btn');
                  if (btn) btn.click();
                }
              });
            })();
            """
        ),
        rx.box(
            rx.hstack(
                rx.button(
                    "✕",
                    id="hero-intro-close-btn",
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                    on_click=ScrapingHeroVisualState.close_fullscreen_intro,
                ),
                rx.button(
                    "Esc",
                    size="1",
                    variant="soft",
                    color_scheme="gray",
                    on_click=ScrapingHeroVisualState.close_fullscreen_intro,
                ),
                spacing="2",
            ),
            position="absolute",
            top="12px",
            right="14px",
            z_index="1600",
        ),
        _matrix_canvas("100vh"),
        position="fixed",
        inset="0",
        width="100vw",
        height="100vh",
        z_index="1500",
        background="black",
        padding="8px",
    )


def _world_map_visual() -> rx.Component:
    points = [
        ("USA", "20%", "36%", "0s"),
        ("EU", "44%", "30%", "0.25s"),
        ("India", "61%", "47%", "0.5s"),
        ("SEA", "73%", "54%", "0.75s"),
        ("Australia", "84%", "72%", "1.0s"),
    ]
    links = [
        ("24%", "38%", "44%", "32%", "0s"),
        ("44%", "32%", "61%", "47%", "0.4s"),
        ("61%", "47%", "73%", "54%", "0.8s"),
        ("73%", "54%", "84%", "72%", "1.2s"),
        ("20%", "36%", "61%", "47%", "1.5s"),
    ]
    link_components = [
        rx.box(
            position="absolute",
            left=link[0],
            top=link[1],
            width=f"calc({link[2]} - {link[0]})",
            height="2px",
            background="linear-gradient(90deg, rgba(96,190,255,0), rgba(133,228,255,0.95), rgba(96,190,255,0))",
            style={"animation": f"heroLinkGlow 2.6s ease-in-out infinite {link[4]}"},
        )
        for link in links
    ]
    point_components = [
        rx.box(
            rx.box(
                width="10px",
                height="10px",
                border_radius="9999px",
                background="orange.9",
                box_shadow="0 0 14px rgba(255,166,0,0.85)",
            ),
            rx.box(
                width="10px",
                height="10px",
                border_radius="9999px",
                border="2px solid rgba(255,166,0,0.7)",
                position="absolute",
                top="0",
                left="0",
                style={"animation": f"heroPulseRing 1.8s ease-out infinite {point[3]}"},
            ),
            rx.text(point[0], size="1", color="blue.11", margin_top="0.4rem", weight="medium"),
            position="absolute",
            left=point[1],
            top=point[2],
        )
        for point in points
    ]

    return rx.box(
        rx.el.style(
            """
            @keyframes heroPulseRing {
              0% { transform: scale(0.4); opacity: 0.85; }
              100% { transform: scale(2.1); opacity: 0; }
            }

            @keyframes heroSweep {
              0% { transform: translateX(-120%); opacity: 0; }
              16% { opacity: 0.35; }
              52% { opacity: 0.18; }
              100% { transform: translateX(120%); opacity: 0; }
            }

            @keyframes heroLinkGlow {
              0%, 100% { opacity: 0.2; }
              50% { opacity: 0.9; }
            }
            """
        ),
        rx.box(
            rx.box(
                position="absolute",
                inset="0",
                background=(
                    "radial-gradient(circle at 20% 35%, rgba(95,180,255,0.20), transparent 42%),"
                    "radial-gradient(circle at 74% 58%, rgba(92,230,255,0.18), transparent 40%)"
                ),
                pointer_events="none",
            ),
            *link_components,
            rx.box(
                position="absolute",
                top="0",
                left="-30%",
                width="30%",
                height="100%",
                background="linear-gradient(90deg, rgba(120,220,255,0), rgba(120,220,255,0.30), rgba(120,220,255,0))",
                style={"animation": "heroSweep 3.8s linear infinite"},
                pointer_events="none",
            ),
            *point_components,
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
    return rx.box(
        rx.cond(
            ScrapingHeroVisualState.show_fullscreen_intro
            & ScrapingHeroVisualState.visual_enabled
            & ~ScrapingHeroVisualState.visual_hidden
            & (ScrapingHeroVisualState.visual_mode == "Matrix Rain"),
            _fullscreen_matrix_intro(),
            rx.fragment(),
        ),
        rx.card(
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
                rx.cond(
                    ScrapingHeroVisualState.visual_mode == "Matrix Rain",
                    rx.button(
                        "Fullscreen",
                        size="1",
                        variant="soft",
                        color_scheme="gray",
                        on_click=ScrapingHeroVisualState.open_fullscreen_intro,
                    ),
                    rx.fragment(),
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
                        _matrix_canvas("180px"),
                        _world_map_visual(),
                    ),
                ),
            ),
            spacing="3",
            width="100%",
        ),
        size="2",
        width="100%",
        ),
        width="100%",
    )
