# Grid-Sentinel Dashboard

React + Vite + Tailwind + Recharts. Static site, no backend, fetches
`public/data/dashboard.json` at load time and renders everything client-side.

## Local development

```bash
npm install
npm run dev
```

`public/data/dashboard.json` is committed to the repo (rebuilt daily by CI),
so `npm run dev` works out of the box without running anything else first.

## Regenerating the data file

`public/data/dashboard.json` is generated from the main dataset by
`Pipeline/build_dashboard_data.py` (run from the repo root, needs `pandas`/`numpy`):

```bash
python Pipeline/build_dashboard_data.py
```

This is wired into `.github/workflows/daily_scrape.yml`, so it refreshes
automatically whenever new PSP data lands. You only need to run it by hand
if you're testing a change to the aggregation logic itself.

## Deploying to Vercel

1. [Import this repo on Vercel](https://vercel.com/new).
2. Set **Root Directory** to `dashboard`.
3. Framework preset should auto-detect as **Vite**: build command
   `npm run build`, output directory `dist`. No environment variables needed.
4. Deploy. Every push to `main` that touches `dashboard/` (or CI's daily data
   commit) triggers a new deployment automatically.

## Why this exists / what it shows

Six panels, each backed by a specific, already-verified piece of the project
(see the root `ROADMAP.md`'s Phase 4/6 sections for the underlying numbers):

- **Live Grid Status**: latest published NLDC daily figures.
- **Study 1 forecast**: next-day demand prediction vs. actual, from
  `ML/Study1/predict.py`'s daily CI output.
- **Study 2 risk timeline**: today's 96-slot violation/ramp-shock risk, from
  `ML/Study2/predict.py`'s daily CI output.
- **Historical Explorer**: full 2019-present demand/RES-share trend, plus
  the Era 1 (ramp vs. RES share) and Era 2 (corridor-stress correlation)
  findings as dedicated tabs.
- **Anomaly Log**: derived from the two model outputs above, not a separate
  detector.

`study1_hourly.csv` (36MB) and `study2_scada.csv` (60MB) are never fetched by
the browser. `Pipeline/build_dashboard_data.py` precomputes the small
aggregates each panel needs (a few hundred KB total) so the dashboard stays
fast on a static host with no backend.
