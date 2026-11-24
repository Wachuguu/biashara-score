# Biashara Score: frontend PWA

A mobile-first Next.js 14 Progressive Web App for shop owners: import M-Pesa statements, see the Biashara Score, track Customer Debts, and download a lender report.

- **Stack:** Next.js 14 (App Router) with TypeScript, Tailwind CSS 3, `lucide-react` icons and `motion` for animation. There's no UI kit and no chart library; the charts are hand-built SVG.
- **Target:** 360px-wide Android phones on patchy data. Every screen has loading, empty and error states.

## Run locally

You need Node 18+ and the backend running offline (`MOCK_AWS=true`).

```bash
# 1. Backend (from the repo root)
cp .env.example .env                    # MOCK_AWS=true, no AWS keys needed
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests          # use `python -m pytest`; plain `pytest` can't import `backend.*`
cd backend && python local_server.py    # http://localhost:8000/docs

# 2. Frontend (new terminal)
cd frontend
cp .env.example .env.local              # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm install
npm run dev                             # http://localhost:3000
```

Then open http://localhost:3000. Tap **Open demo shop**, or create a duka. Go to **Import**, choose `sample-data/mpesa_statement.csv`, and look at **Home**.

> **Port 3000 matters.** The local backend only allows CORS from `http://localhost:3000`. If that port is taken, free it rather than running the app on another port.

> **API base URL.** The root `.env.example` says `http://localhost:8000/api/v1`, but `local_server.py` serves its routes at the root. Use `http://localhost:8000` (the default when the variable isn't set). Point it at the API Gateway URL once the app is deployed.

> **Data resets.** The mock backend keeps data in memory. Restarting `local_server.py` (or a uvicorn auto-reload after a backend edit) wipes all businesses, transactions and debts. The app then shows its empty states, so re-import the CSV.

### Scripts

| Command | What it does |
| --- | --- |
| `npm run dev` | Dev server (the service worker is not registered in dev) |
| `npm run build` | Production build with type-check and lint |
| `npm start` | Serve the production build (the service worker is active) |
| `npm run lint` / `npm run typecheck` | ESLint (`next/core-web-vitals`) and `tsc --noEmit` |

## Screens

| Route | Purpose | API |
| --- | --- | --- |
| `/setup` | Create, switch or demo a duka profile | `PUT /business`, `GET /business` |
| `/import` | Upload CSV or paste SMS, then review and fix categories | `POST /statements/upload`, `POST /statements/sms`, `GET /transactions`, `PATCH /transactions/{receipt}` |
| `/dashboard` | Score gauge, 4 pillars, tips, this week's pulse, weekly trend, recent transactions | `GET /score`, `GET /summary/weekly`, `GET /transactions` |
| `/deni` | Customer Debts: summary, search and filter, add debt, record payment | `GET /debts`, `POST /debts`, `PATCH /debts/{id}` |
| `/report` | Download the lender PDF | `GET /reports/lender-pdf` |
| `/offline` | Service-worker fallback when there's no connection | none |

**Tenancy (mock mode):** each request sends `X-Business-Id` for the active duka. Profiles are kept on the device in `localStorage`. A new duka is a fresh `biz_…` id saved with `PUT /business`. In production this becomes a Cognito Bearer token; see `src/api/client.ts`.

## Code layout

```
src/
  app/            routes (App Router), manifest.ts, template.tsx (page transition)
  api/            client.ts (fetch, timeouts, error envelope → ApiError), endpoints.ts, types.ts
  components/     Button, Sheet, Toast, StateViews, AppShell (header + bottom nav),
                  ScoreGauge, PillarBars, WeekTrend, TxRow, CategoryPicker
  hooks/          useApi (load/error/retry), useActiveDuka
  utils/          format.ts (formatKSh → "KSh 14,200"), profile.ts, categories.ts
public/           sw.js, icons/
scripts/          make_icons.py (regenerates public/icons with Pillow)
```

> Don't create a `lib/` folder. The root `.gitignore` ignores `lib/` (and `build/`, `out/`, `env/`, `var/`) at any depth, so files there would never be committed.

## Design system

The look is a hand-painted duka signboard. Tokens live in `tailwind.config.ts`:

- **Colours:** `maize` #F2C230 (signboard), `cobalt` #2340A8 (actions), `ink` #14213D (text and borders), `leaf` #17663D (money in), `chili` #B42A23 (owed or loss), `paper` #F6F7F2. Chart marks use `chart.sales` #3556C4 and `chart.profit` #1F8A52, which pass the dataviz palette validator (lightness band, CVD separation and contrast on white).
- **Type:** Big Shoulders Display for headings and figures, Atkinson Hyperlegible for body text (17px base). Both load through `next/font`.
- **Touch:** controls are at least 44px tall, and primary actions are 52px. Inputs are 17px or larger so Android doesn't zoom on focus.
- **Money:** always shown through `formatKSh()`, e.g. `KSh 14,200` or `−KSh 3,251`.
- **Motion:** gauge count-up, staggered lists, sheet slide-up, page fade, button press and save toast. Every animation runs in 400ms or less. `MotionConfig reducedMotion="user"` honours `prefers-reduced-motion`.

## PWA

- `app/manifest.ts` produces `/manifest.webmanifest`: standalone display, start URL `/dashboard`, 192, 512 and maskable icons, plus shortcuts to Deni and Import.
- `public/sw.js` precaches the app shell and `/offline`. Navigations go network-first with a cached fallback. Hashed static assets use stale-while-revalidate. **API responses are never cached.**
- The service worker registers in production builds only (`npm run build && npm start`).
- Chrome's installability check (`Page.getInstallabilityErrors`) reports no errors. Lighthouse 12 no longer has a PWA category.

## Known gaps

- `GET /transactions` ignores `cursor`, so **Show more** raises `limit` instead, up to the backend maximum of 200.
- The lender PDF filename is built on the client, because the backend doesn't expose `Content-Disposition` through CORS.
- `PATCH /transactions/{receipt}` was added to `local_server.py` on this branch. The Lambda `api_handler` and the SAM route still need it before deploying.
- There's no Cognito sign-in yet. The app uses mock-mode `X-Business-Id` tenancy.
