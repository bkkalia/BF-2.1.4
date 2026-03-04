import reflex as rx


config = rx.Config(
	app_name="dashboard_app",
	state_auto_setters=False,
	frontend_port=3000,
	backend_port=8600,
	disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
