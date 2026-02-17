import reflex as rx


config = rx.Config(
	app_name="dashboard_app",
	state_auto_setters=False,
	disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
