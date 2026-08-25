# AutoPipe Dashboard Frontend — Pure Implementation Prompt
## File-by-file Build Guide (no screenshot references)

---

## CONSTRAINTS
- React 18 + Vite + TypeScript
- Tailwind CSS v3 (config in `tailwind.config.js` or `postcss.config.js`)
- Recharts for charts
- @tanstack/react-query for data
- react-router-dom v6
- Lucide React for icons
- NO new npm dependencies without explicit approval
- Extend existing `src/components/ui/index.tsx`; do not swap for external UI libraries
- Dark mode is default via `ThemeProvider`
- `pnpm build` and `pnpm lint` must pass when done

---

## PHASE 1 — GLOBAL SHELL (files to modify)

### `src/styles/globals.css`
**Action:** Append utility classes. Do not change existing theme variables.
```css
@layer utilities {
  .surface-elevated {
    @apply bg-[hsl(220,15%,10%)] border border-border/60 rounded-xl;
  }
  .panel-header {
    @apply flex items-center justify-between px-3 py-2 border-b border-border bg-muted/20 rounded-t-lg text-sm font-medium;
  }
  .tabular-nums {
    font-variant-numeric: tabular-nums;
  }
}
```

### `src/components/ui/index.tsx`
**Action:** Append these components after existing exports.

1. `StatusPill` — colored dot + label. Variants: `pending` (amber, pulse), `running` (blue, pulse), `finished` (green), `failed` (red).
2. `PanelHeader` — icon + title + count badge on left; action buttons (settings, add, fullscreen) on right.
3. `ChartCard` — `bg-card border border-border rounded-lg p-4`; renders `PanelHeader` + children.

### `src/components/layout/Layout.tsx`
**Action:** Refactor sidebar + header.

**Sidebar changes:**
- Collapse toggle shrinks sidebar to `w-14` icon-only mode.
- Active nav item: left 3px accent bar `border-l-2 border-primary` + `bg-primary/5`.
- Hover: `hover:bg-muted/50 transition-colors duration-150`.
- Bottom user card: smaller inline layout (avatar + name truncate + role tag).

**Header changes:**
- Replace static header with breadcrumb + contextual actions area.
- Keep `New Pipeline` button.

---

## PHASE 2 — NEW FILES TO CREATE

### `src/components/layout/Breadcrumb.tsx`
- Reads current `react-router-dom` `useLocation`.
- Renders segments as clickable links (e.g., `runs` → `/runs`, `mnist-run-1` stays text).
- Style: `text-sm text-muted-foreground`, last segment `text-foreground font-medium`.
- Separator: `ChevronRight` icon at `w-4 h-4`.

### `src/components/layout/GlobalSearch.tsx`
- A modal triggered by header button (and `Cmd+K` keyboard listener on window).
- Overlay: `fixed inset-0 bg-black/50 z-50`.
- Modal panel: centered, `w-[640px] max-w-[90vw]`, `rounded-xl bg-card border border-border shadow-2xl`.
- Input field at top, placeholder "Search runs, models, experiments…".
- Empty state: "Type to search".
- No backend integration yet; UI-only.

### `src/components/charts/SyncCrosshairProvider.tsx`
- `React.createContext<{ sharedX: number | null; setSharedX: (x: number | null) => void }>`.
- Wraps chart sections in Run Detail.
- All line charts read this context and render a `ReferenceLine` at `sharedX` when present.

### `src/components/ui/ProjectCard.tsx`
- Props: `name`, `lastRunStatus`, `runCount`, `colorSeed`.
- Card: `w-64 h-36 rounded-xl surface-elevated relative overflow-hidden`.
- Background: subtle gradient derived from `colorSeed` (use a deterministic hue map).
- Bottom-left: project name `font-semibold text-sm`.
- Top-right: run count pill.
- Hover: `hover:shadow-lg hover:border-border/80 transition-shadow`.

### `src/components/ui/ActivityHeatmap.tsx`
- Props: `data: { date: string; count: number }[]`.
- Grid: 7 rows (Mon–Sun), 52 columns (weeks). Cell size `10px`, gap `2px`.
- Color scale via opacity on `bg-primary`: `bg-muted` (0), `bg-primary/30` (1–3), `bg-primary/60` (4–7), `bg-primary` (8+).
- Tooltip on hover: date + exact count.

### `src/components/ui/QueryBar.tsx`
- Props: `value`, `onChange`, `onExecute`.
- Monospace font, `bg-muted/30 rounded-lg border border-border px-3 py-2`.
- Placeholder: `runs.summary["sample_predictions"]`.
- Filter button on right.
- On `Enter`, call `onExecute`.

### `src/components/ui/DataTable.tsx`
- Generic reusable table wrapper.
- Props: `columns`, `data`, `emptyMessage`, `emptyAction?`.
- Header: `text-xs uppercase tracking-wider text-muted-foreground font-semibold`, row height `h-10`.
- Row hover: `hover:bg-muted/30`.
- Empty state: centered icon + `emptyMessage` text + optional `emptyAction` button.
- Expose `onRowClick` optional prop.

---

## PHASE 3 — PAGE REFINEMENTS (modify existing)

### `src/pages/dashboard/Dashboard.tsx`
**Action:** Keep structure, upgrade components only.

- Stat cards: add a 2px colored top accent line matching icon color (blue/green/amber/purple).
- Trends below value: `text-xs text-muted-foreground`.
- Activity feed: replace generic list with denser items; each row = icon + event text + relative time ("2w ago").
- Active pipelines section: table with inline progress bars for running pipelines.
- Resource usage chart: wrap in `ChartCard`, add synced hover crosshair (see SyncCrosshairProvider).

### `src/pages/runs/RunDetail.tsx`
**Action:** Major refactor into a single-scroll workspace page.

**Top section:**
- Breadcrumb + run title + `StatusPill`.
- Action buttons: Compare, Download, Share.

**Tab bar:** `[Charts] [Overview] [Logs] [Files] [Artifacts]` — sticky, active tab gets bottom border primary.

**Charts tab (default):**
- QueryBar at top.
- Panels in sequence:
  1. Tables — `PanelHeader` + `DataTable` (image | prediction | ground_truth | correct?). Correct column = green checkmark in `bg-green-500/10` pill.
  2. Train charts — grid of 4 line charts: `train/loss`, `train/epoch_loss`, `train/epoch_accuracy`, `train/accuracy`. Use `ChartCard` + gradient fill under lines + `SyncCrosshairProvider`.
  3. Parameters — grid of histograms (fc1.weight, fc1.bias, fc2.weight, fc2.bias, fc3.weight, fc3.bias). Diverging color: blue for negative, coral for positive, white at center. Use Recharts `BarChart` with `<Cell>` per bar.

**Overview tab:**
- Keep existing stat cards, step list, training config accordion, step durations bar chart, checkpoints table.
- Wrap all charts in `ChartCard`. Replace raw `<Badge>` for status with `StatusPill`.

**Logs tab:**
- Keep existing terminal-style log viewer. No changes needed.

**Metrics tab:**
- Keep existing metrics grid. Add hover effects.

**Checkpoints tab:**
- Keep existing table. Wrap in `DataTable` if possible.

### `src/pages/workspace/Workspace.tsx`
**Action:** No structural changes. Ensure panels use `ChartCard` when rendering charts, and `PanelHeader` for section titles.

---

## PHASE 4 — NEW PAGE (create)

### `src/pages/projects/ProjectsPage.tsx`
**Action:** Create from scratch; wire into routes.

**Layout:**
- Header: title "Projects" + `+ New project` button.
- Toolbar: Search input + Filter dropdown + Sort dropdown + View toggle (grid/table).
- Starred projects: horizontal scroll row of `ProjectCard`.
- All projects table: columns = Name | Last Run | Visibility (StatusPill) | Runs | Traces | Health.
- Health column: sparkline of last 7 run success rates (mini area chart, 80×24px).
- Empty state: centered `FolderOpen` icon + "No projects yet" + "Create project" CTA.

### `src/routes.tsx`
**Action:** Add route entry.
```tsx
const ProjectsPage = lazy(() => import('@/pages/projects/ProjectsPage').then(m => ({ default: m.ProjectsPage })))
```
Insert `<Route path="/projects" element={<ProtectedLayout><ProjectsPage /></ProtectedLayout>} />` before the wildcard catch-all.

### `src/pages/profile/ProfilePage.tsx`
**Action:** Create from scratch; wire into routes at `/profile`.

**Layout:**
- Top: avatar (`w-20 h-20 rounded-xl` with initials), name, email, org, location.
- Tabs: Profile | Reports | Projects | Stars. Active tab = pill style: `bg-primary text-primary-foreground rounded-full px-4 py-1.5`.
- Profile tab content:
  - Highlighted projects card (grid of ProjectCard or empty state).
  - Links card (list of URL chips or empty state).
  - ActivityHeatmap.
  - Recent Runs `DataTable`.
- Reports / Projects / Stars tabs: scaffold with "Coming soon" centered text for now.

### `src/routes.tsx`
**Action:** Add route.
```tsx
const ProfilePage = lazy(() => import('@/pages/profile/ProfilePage').then(m => ({ default: m.ProfilePage })))
```
Insert `<Route path="/profile" element={<ProtectedLayout><ProfilePage /></ProtectedLayout>} />`.

---

## PHASE 5 — POLISH CHECKLIST (apply everywhere)

| Rule | How to verify |
|------|-------------|
| Every table uses `DataTable` or `tabular-nums` on numeric cells | `grep -r "tabular-nums\|DataTable" src/pages` |
| Every status display uses `StatusPill`, never raw `<Badge>` for status | `grep -r "StatusPill" src/pages` |
| Every empty state has icon + message + optional CTA | Spot-check each page |
| Every card/chart has `surface-elevated` or `ChartCard` wrapper | Visual inspection |
| All buttons have `focus-visible:ring-2 focus-visible:ring-ring` | Already in `Button` component; verify usage |
| Scrollable areas use `scrollbar-thin` | Add class to panels and tables |
| No hydration mismatch: wrap client-only content in `mounted` guard | Follow pattern in existing `Dashboard.tsx` |
| Sidebar collapse works and active state is visible | Manual test |
| Crosshair sync works across all line charts on Run Detail | Hover one chart; verify vertical rule appears on others |

---

## FILE SUMMARY

### Modify (10 files)
1. `src/styles/globals.css` — add `.surface-elevated`, `.panel-header`, `.tabular-nums`
2. `src/components/ui/index.tsx` — add `StatusPill`, `PanelHeader`, `ChartCard`
3. `src/components/layout/Layout.tsx` — collapsible sidebar, breadcrumb area, user card shrink
4. `src/pages/dashboard/Dashboard.tsx` — stat card accents, denser activity feed, progress bars
5. `src/pages/runs/RunDetail.tsx` — reorganize into workspace view with QueryBar, ChartCard, synced charts, parameters histograms
6. `src/components/charts/TrainingMetricsChart.tsx` — gradient fill, hook into SyncCrosshairProvider
7. `src/routes.tsx` — add `/projects` and `/profile` lazy routes
8. `src/pages/workspace/Workspace.tsx` — adopt ChartCard / PanelHeader where rendering charts
9. `src/components/charts/ChartRenderer.tsx` — ensure chart wrappers respect new design tokens
10. `src/api/endpoints/runs.ts` (or equivalent) — if needed, add `getProjects()` for ProjectsPage

### Create (7 files)
1. `src/components/layout/Breadcrumb.tsx`
2. `src/components/layout/GlobalSearch.tsx`
3. `src/components/charts/SyncCrosshairProvider.tsx`
4. `src/components/ui/ProjectCard.tsx`
5. `src/components/ui/ActivityHeatmap.tsx`
6. `src/components/ui/QueryBar.tsx`
7. `src/components/ui/DataTable.tsx`
8. `src/pages/projects/ProjectsPage.tsx`
9. `src/pages/profile/ProfilePage.tsx`

---

## SUCCESS CRITERIA
1. `pnpm build` — zero TypeScript errors.
2. `pnpm lint` — passes.
3. Sidebar collapses to icon-only; active item has accent bar.
4. Run Detail shows Query bar, Tables, synced line charts, and parameters histograms in one scrollable page.
5. All empty states show icon + message + CTA.
6. No visual regressions on `/workspace`.
7. `/projects` and `/profile` loads without errors.
