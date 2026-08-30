# Session Log — 2026-08-24: Sector Focus Verdict Layer (v1)

Spec: `.sisyphus/plans/sector-focus-verdict.md` (gitignored working doc)

## What Was Built
Prescriptive answer to "which sector do I hunt this week?" — the decision layer
that was missing between raw sector numbers and the screener.

### Backend
- `backend/app/domain/sector_focus/service.py` — pure scoring core:
  FOCUS score = weekly-RS percentile rank (40%) + flow_strength_1w (25%) +
  momentum (20%) + volume confirmation (15%) + improvement bonus (+10 gained
  rank / +5 holding top-3).
  Guards: absolute-vs-SPY gate (rank normalization alone crowns least-fallen
  sectors in downtrends); regime caps (broad_market_weakness ⇒ no-hunt);
  missing signals renormalize weights or degrade to WATCH — never fabricate.
  snapshot_id = sha1 over rounded metrics+regime+version.
- `backend/app/api/routers/sector_focus.py` — GET /api/v1/sectors/focus,
  sharing the rotation router's cached data + SPY helper (own TTL).
- `sector_rotation.py`: extracted `_build_sector_performances()` so rotation
  and focus endpoints emit byte-identical numbers from one cache.

### Tests
`backend/tests/test_sector_focus.py` — 20 synthetic no-network cases:
percentile ties, renormalization, insufficient-components ⇒ None, SPY-gate
conservatism, bearish no-hunt, cap demotion ("slots are full"), avoid-list
plain-language requirement, missing-signal degradation, snapshot stability &
sensitivity, prev-week rank window semantics. **20/20 passing.**

Bug caught during test authoring: reasons were generated before tier promotion,
so FOCUS entries never received the "#N of 11" headline reason (verdict was
still FOCUS_CANDIDATE at build time). Reasons now built after final tiers.

### Frontend
- `SectorFocusCard` (full on /sector-rotation, compact embed in Morning Brief)
  via shared react-query cache — both surfaces render ONE snapshot.
- CTA: "Hunt swing candidates in X" → `/screener?sector=<ETF name>&focus=1`.
- ScreenerPage resolves ETF-family names to TV industry pills via keyword map
  (exact-match filter would otherwise clear itself).
- Horizon labels: heatmap header now says "(today = noise · this week = signal)".

## Verification
- pytest 20/20 · tsc --noEmit clean · container restarted healthy
- Live probe /api/v1/sectors/focus: regime=mixed, FOCUS Health Care 93.0 +
  Materials 77.1, AVOID Technology 27.0 — coherent with independent web
  research earlier this session (HC leadership, tech weakness)
- Playwright on /sector-rotation: card renders, hunt CTA present, avoid strip
  present, horizon label visible

## Decisions Taken (spec open questions, defaults adopted)
- Q1 breadth/participation: deferred to v2 (needs constituent OHLCV).
- Q2 AVOID warning banner inside screener: v1.5 follow-up (not built here).
- Q3 cadence: compute-on-demand w/ ~5-min cache; UI states weekly horizon is
  the decision lens instead of stamping a fake Friday refresh time.

## Commits
26e926f feat(api) · 2a7c8a0 test(sector-focus) · 0b6d136 feat(web)
