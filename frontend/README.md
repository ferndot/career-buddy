# CareerDesk frontend

React 19 + TypeScript + Chakra UI v3, built with Vite. Standalone: it talks to the Python API over `/api`.
Package manager: **pnpm** (lockfile: `pnpm-lock.yaml`).

## Commands

```bash
pnpm install
pnpm dev        # http://localhost:5173, proxies /api -> http://127.0.0.1:8000
pnpm typecheck  # tsc --noEmit
pnpm test       # vitest run (jsdom + Testing Library)
pnpm build      # typecheck + vite build -> frontend/dist
```

Run the Python API on port 8000 first (start the backend the way you normally do from the repo root). To point at another backend set `VITE_API_URL`
(e.g. `VITE_API_URL=http://host:8000 pnpm dev`); leave it unset to use the dev proxy.

## Folder conventions (`src/`)

| Folder | Purpose |
|---|---|
| `theme/` | Chakra system. Colors are semantic tokens under the `app.` namespace (`bg="app.surface"`, `color="app.muted"`); values live in `tokens.ts` as `[light, dark]`. `ThemeProvider` follows the system color mode; `ColorModeToggle` flips it. |
| `brand/` | `CareerBuddyLogo` and `CareerBuddyMark` (the robot). |
| `app/` | Shell (sidebar / top bar), nav items (`nav.ts`), routes (`routes.tsx`), providers. |
| `components/` | Shared presentational pieces (`PageHeader`, `EmptyState`). Add reusable widgets here. |
| `api/` | `apiFetch<T>`, `ApiError`, `queryClient`, and `endpoints.ts` (typed path builders, no fetching). |
| `screens/<name>/` | One folder per route: `<Name>Screen.tsx` plus `index.ts` re-exporting it. Replace a placeholder by editing only its own folder (put screen-local components, hooks and tests beside it). |
| `test/` | Vitest setup and the `renderApp` helper. |

Screens: `sources` (`/sources`), `career` (`/career`), `documents` (`/documents`),
`document-new` (`/documents/new`), `settings` (`/settings`). Keep every file under ~450 lines.

Use Chakra components for UI and the `app.*` tokens for color so light and dark both work.
Data fetching: `useQuery`/`useMutation` with `apiFetch(endpoints.x.y())`. For file downloads
(`/api/resume/{fmt}`, `/api/cover-letter`) use `apiUrl(path)` with a plain `fetch` or link.
