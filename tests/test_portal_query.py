from tender_dashboard_reflex.tender_dashboard_reflex import db

stats = db.get_portal_statistics(0)
print(f'Found {len(stats)} portals')
for p in stats[:5]:
    print(f'{p["portal_name"]}: {p["total_tenders"]} tenders (live: {p["live_tenders"]}, expired: {p["expired_tenders"]})')
