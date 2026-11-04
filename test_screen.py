import sys
sys.path.insert(0, '.')

from backend.app.infrastructure.screener.configs import load_screen_template

# Load trend-follower template
template = load_screen_template('trend-follower')
print(f"Screen: {template.name}")
print(f"Description: {template.description}")
print(f"Asset classes: {template.asset_classes}")
print(f"Timeframes: {template.timeframes}")
print(f"\nFilters ({len(template.filters)}):")
for f in template.filters:
    print(f"  - {f.category}.{f.indicator} {f.operator} {f.params} (timeframe: {f.timeframe})")