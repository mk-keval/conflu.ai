import sys
sys.path.insert(0, '.')

from backend.app.infrastructure.screener.configs import load_screen_template

# Check all available templates
templates = ['trend-follower', 'high-conviction-stack', 'bull-flag-continuation', 
             'statistical-mean-reversion', 'institutional-swing-quality', 
             'trend-leader', 'quality-trend-fundamentals', 'volatility-expansion',
             '52week-breakout', 'breakdown', 'mean-reversion', 'short-squeeze',
             'volume-trend-accumulation']

for name in templates:
    try:
        template = load_screen_template(name)
        print(f"\n=== {name} ===")
        print(f"Description: {template.description[:80]}")
        print(f"Filters ({len(template.filters)}):")
        fundamental_count = 0
        technical_count = 0
        for f in template.filters:
            is_fundamental = f.category == 'fundamental'
            if is_fundamental:
                fundamental_count += 1
            else:
                technical_count += 1
            print(f"  - {f.category}.{f.indicator} {f.operator} {f.params}")
        print(f"  Fundamental: {fundamental_count}, Technical: {technical_count}")
    except Exception as e:
        print(f"\n=== {name} === ERROR: {e}")