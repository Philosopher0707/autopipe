# AutoPipe Dashboard — Frontend Refinement Plan
## Precision Design-to-Code Specification

---

## 1. Current State Analysis (from Screenshots)

### Screenshot A — Profile / Projects List (`12.23.04 PM`)
**Page:** `/profile` or org-level projects view
- Left sidebar: user profile card (avatar, name, email, org, location, team)
- Top tabs: Profile | Reports | Projects | Stars
- Content: starred projects empty-state, project table with columns (Name, Last Run, Visibility, Runs, Traces)
- **Gaps:** No quick-action hover states; table is bare; missing filter chips; no project health indicators.

### Screenshot B — Profile Dashboard (`12.23.42 PM`)
**Page:** `/profile` (Profile tab active)
- Highlight projects card, Links card, Activity heatmap (GitHub-style), Recent Runs mini-table
- **Gaps:** Heatmap has almost no data density; Recent Runs table lacks status color pills; cards have no interactivity.

### Screenshot C — Run Workspace / Tables & Charts (`12.34.05 PM`)
**Page:** `/runs/:runId` (Workspace view)
- Left sidebar: Project | Workspace | Runs | Tables | Automat. | Sweeps | Reports | Artifacts
- Top: query input bar (`runs.summary["sample_predictions"]`), Filter button
- Tables panel: image / prediction / ground_truth / correct? columns
- Charts panel: train/loss, train/epoch_loss, train/epoch_accuracy, train/accuracy line charts
- **Gaps:** query bar looks plain; charts lack synchronized cursors / crosshair; table pagination controls missing; no column resize.

### Screenshot D — Run Workspace / Parameters (`12.33.54 PM`)
**Page:** `/runs/:runId` scrolled to parameters section
- Parameter histograms: fc3.weight, fc3.bias, fc2.weight, fc2.bias, fc1.weight, fc1.bias
- Each histogram uses a violin/density bar chart with blue-white gradient
- Below: Tables section with sample_predictions
- **Gaps:** Parameter charts are monochromatic and lack hover detail tooltips; section headers ("parameters 6") are plain text pills; no collapse/expand.

### Screenshot E — Home / Recent Activity (`12.27.29 PM`)
**Page:** `/` (Dashboard home)
- Left sidebar: Home, Projects, Core (Registry, Launch, Inference), Profile, Teams
- Main: Recent activity table (mnist-run-1, finished, project, type Run, 14 days ago)
- Your recent reports promo card
- **Gaps:** Empty states dominate; sidebar icons lack active-state accent; table row hover missing; no inline actions.

---

## 2. Design System Tokens (Current → Refined)

| Token | Current | Refined |
|-------|---------|---------|
| `--background` | `222.2 84% 4.9%` (very dark slate) | Keep; refine layered surfaces with `bg-[hsl(220,15%,8%)]` for content area and `bg-card` for panels |
| `--card` | Same as background | Slightly elevated: `220 15% 10%` with `border-border/60` |
| `--primary` | `217.2 91.2% 59.8%` (bright blue) | Keep; add glow variant for active nav |
| `--muted-foreground` | `215 20.2% 65.1%` | Slightly dimmer for hierarchy: `215 15% 55%` |
| `--border` | `217.2 32.6% 17.5%` | `217 20% 14%` — subtler dividers |
| Sidebar width | `16rem` (256px) | `15rem` (240px) — tighter, modern density |
| Border radius | `0.75rem` (cards), `0.5rem` (buttons) | Cards `0.75rem`, inner panels `0.5rem`, pills `9999px` |
| Shadow | `shadow` (barely visible) | Cards get `shadow-lg shadow-black/20`, hover gets `shadow-xl` |
| Font | Default sans | Keep; add tabular nums for tables and mono for metrics |

---

## 3. Global Component Refinements

### 3.1 Sidebar (`Layout.tsx`)
**Current:** static list, single-level, badge counts.
**Refined:**
- Collapsible sections: Overview, ML Lifecycle, System, Projects (pinned).
- Active item gets a **left 3px accent bar** (primary color) + subtle `bg-primary/5`.
- Hover: `hover:bg-muted/50` with `transition-colors duration-150`.
- Add **pin/unpin** for projects to sidebar (like Screenshot B's "Starred projects" concept moved to nav).
- Bottom user card: smaller, inline avatar + name, role as muted tag.
- Add a **global search shortcut** (`⌘K`) trigger button at top of sidebar.

### 3.2 Top Header
**Current:** hamburger + New Pipeline button + theme toggle.
**Refined:**
- Breadcrumb trail (Home → Projects → mera-pehla-experiment → Runs → mnist-run-1) with clickable segments.
- Right cluster: global search input (cmd-k), notification bell (badge if drift alerts), user dropdown.
- "New Pipeline" → primary blue button with Play icon; keep.
- Add **contextual actions** that change per route (e.g., on Run Detail: "Compare", "Download", "Share").

### 3.3 Tables (Global)
**Refined:**
- Header: `text-xs uppercase tracking-wider text-muted-foreground font-semibold`.
- Rows: `hover:bg-muted/30 transition-colors`, `h-10` density.
- Status cells: colored dot + label pill (Running = pulsing blue, Finished = green, Failed = red).
- Actions column: icon-only buttons (eye, edit, delete) visible on hover.
- Column resizing: optional `react-table` or CSS `resize` on header.
- Empty state: centered icon + message + CTA button (not just text).

### 3.4 Charts (Global)
**Refined:**
- Line charts: gradient fill under line (`<defs><linearGradient>…</defs>`), 2px stroke, crosshair synced across all charts on the page via a shared hover context.
- Tooltip: dark card with `shadow-lg`, mono values, clear timestamp.
- Axis labels: `text-muted-foreground text-[10px]`.
- Histograms: use a **diverging color scale** (blue for negative, white for zero, coral for positive) instead of monochrome. Add hover tooltip with exact bin count.
- All charts get a **"Download PNG"** and **"View fullscreen"** action in top-right corner.

---

## 4. Page-by-Page Precision Design

---

### PAGE: Home (`/`)
**Current:** stat cards, resource area chart, active pipelines, activity feed.
**Refined layout:**

```
┌─────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home                                            │
├─────────────────────────────────────────────────────────────┤
│ Welcome back, [User]           [Quick actions: New Run |   │
│                                New Experiment | Registry]   │
├─────────────────────────────────────────────────────────────┤
│┌────────────┐┌────────────┐┌────────────┐┌────────────┐     │
││ Total Runs ││ Models   ││ Drift     ││ Experiments│     │
││  1,247    ││  23      ││  2 alerts ││  8 active  │     │
││ ↑ 12%     ││ ↑ 3 new  ││ ↓ 1 fixed ││ ↑ 2 trials │     │
│└────────────┘└────────────┘└────────────┘└────────────┘     │
├─────────────────────────────────────────────────────────────┤
│┌──────────────────────────┐┌─────────────────────────────┐│
││ Resource Usage (24h)     ││ Recent Activity Feed        ││
││ [AreaChart]              ││ • mnist-run-1 finished      ││
││                          ││ • model v2 registered       ││
││                          ││ • drift detected on_fc1    ││
│└──────────────────────────┘└─────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│┌─────────────────────────────────────────────────────────┐  │
││ Active Pipelines (table: name | status | last run |   │  │
││ actions)                                               │  │
│└─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Precision specs:**
- Stat cards: `h-28`, `rounded-xl`, top edge gets a 2px colored accent line (blue/green/amber/purple matching icon color).
- Activity feed: icon + text + relative time ("14 days ago" → "2w ago"), hover reveals exact timestamp.
- Active pipelines: table with progress bar in status cell for running pipelines.

---

### PAGE: Projects List (`/projects`)
**Matches Screenshot A.**
**Refined layout:**

```
┌─────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home / Projects                               │
├─────────────────────────────────────────────────────────────┤
│ Projects                                       [ + New ]   │
│ [Search _______________]  [Filter ▼] [Sort ▼] [View: ▤▦]  │
├─────────────────────────────────────────────────────────────┤
│┌─────────────────────────────────────────────────────────┐  │
││ ★ Starred Projects (horizontal scroll if > 3)           │  │
││ [card] [card] [card]                                    │  │
│└─────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│┌─────────────────────────────────────────────────────────┐  │
││ All Projects                                            │  │
││ Name | Last Run | Visibility | Runs | Traces | Health | ▮│  │
││ mera-pehla-experiment | 2026-04-08 | 🔒 Team | 1 | 0 | ●│  │
│└─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Precision specs:**
- Project cards: `w-64 h-36`, gradient background based on project color seed, last run status dot, run count chip.
- Table: add **Health** column (sparkline of last 7 runs' success rate).
- Visibility: pill badge (Public = green outline, Team = blue outline, Private = gray).
- Row hover: background shift + "Open" button appears.
- Empty state: centered illustration + "Create your first project" CTA.

---

### PAGE: Run Detail (`/runs/:runId`)
**Matches Screenshot C + D (W&B-style workspace).**
**Refined layout:**

```
┌─────────────────────────────────────────────────────────────┐
│ Breadcrumb: … / mera-pehla-experiment / Runs / mnist-run-1 │
├──────┬────────────────────────────────────────────────────┤
│      │ Run #mnist-run-1    [Finished ●]                   │
│Side- │ [Compare] [Download] [Share] [⋮]                   │
│bar   │────────────────────────────────────────────────────│
│(colla├────────────────────────────────────────────────────┤
│psible)│ Tabs: [Charts] [Overview] [Logs] [Files] [Artifacts]│
│      │────────────────────────────────────────────────────│
│      │ Query: runs.summary["sample_predictions"]   [⚙]    │
│      │┌───────────────────────────────────────────────────┐│
│      ││ Tables 1  |  Export CSV | Columns | Reset        ││
│      ││ image | prediction | ground_truth | correct?      ││
│      ││ …                                                ││
│      │└───────────────────────────────────────────────────┘│
│      │┌───────────────────────────────────────────────────┐│
│      ││ train 4  |  ← →  |  1-4 of 4  |  ⚙  |  ⊕        ││
│      ││ ┌─────┐ ┌──────────┐ ┌──────────────┐          ││
│      ││ │loss │ │epoch_loss│ │epoch_accuracy│ [+]      ││
│      ││ └─────┘ └──────────┘ └──────────────┘          ││
│      │└───────────────────────────────────────────────────┘│
│      │┌───────────────────────────────────────────────────┐│
│      ││ parameters 6  |  ← →  |  1-6 of 6  |  ⚙  |  ⊕││
│      ││ [Histogram grid: fc1.weight … fc3.bias]           ││
│      │└───────────────────────────────────────────────────┘│
│      │┌───────────────────────────────────────────────────┐│
│      ││ Tables 1  |  … sample_predictions …             ││
│      │└───────────────────────────────────────────────────┘│
└──────┴────────────────────────────────────────────────────┘
```

**Precision specs:**
- **Collapsible sidebar:** Same items as current, but grouped: Project (overview link), Workspace (active), Runs, Tables, Automation, Sweeps, Reports, Artifacts. Active section gets primary accent. Collapse to icon-only `w-14` on toggle.
- **Tab bar:** sticky under breadcrumb. Active tab has bottom border primary + text primary.
- **Query bar:** monospace font, `bg-muted/30` pill shape, syntax-highlight keys/values, execute on Enter, history dropdown on Up arrow.
- **Panel headers:** `flex items-center gap-2 text-sm font-medium px-3 py-2 border-b border-border bg-muted/20 rounded-t-lg`. Count badge is `bg-muted text-muted-foreground text-[10px] px-1.5 rounded`. Navigation arrows are small subtle buttons.
- **Charts grid:** CSS Grid `repeat(3, 1fr)` with `gap-4`. Each chart card: `rounded-lg border border-border bg-card p-4`. Title aligned left, actions (⚙ settings, ⊕ add) aligned right.
- **Crosshair sync:** All line charts on the page share an `x` value via React context; hovering one chart draws vertical rule on all.
- **Histograms:** use custom Recharts bar with diverging color. Tooltip shows: parameter name, step range, bin count, mean ± std.
- **Tables:** `font-feature-settings: "tnum"` for aligned numbers. Correct column: green checkmark with `bg-green-500/10` pill. Pagination: compact prev/next with page number input.

---

### PAGE: Profile (`/profile`)
**Matches Screenshot B.**
**Refined layout:**

```
┌─────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home / Profile                                  │
├─────────────────────────────────────────────────────────────┤
│┌──────┐ LALIT NARAYAN SINGH                    [Edit]      │
││ LN   │ philosopher | rajseelalit@outlook.com              │
│└──────┘ Independent | India                                │
├─────────────────────────────────────────────────────────────┤
│ [Profile] [Reports] [Projects] [Stars]                      │
├─────────────────────────────────────────────────────────────┤
│┌────────────────────────────┐┌──────────────────────────────┐│
││ Highlighted Projects       ││ Links                        ││
││ [card grid or empty state] ││ [link list or empty]        ││
│└────────────────────────────┘└──────────────────────────────┘│
│┌──────────────────────────────────────────────────────────┐│
││ Activity (heatmap)                                        ││
││ [dense github-style grid with hover tooltip showing       ││
││  exact run count per day]                                 ││
│└──────────────────────────────────────────────────────────┘│
│┌──────────────────────────────────────────────────────────┐│
││ Recent Runs                                               ││
││ Name | Project | State | Created | By                     ││
││ mnist-run-1 | mera-pehla-experiment | ● Finished | 2w ago ││
│└──────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**Precision specs:**
- Avatar: `w-20 h-20 rounded-xl` (not circle) with initials.
- Tabs: pill-style active tab `bg-primary text-primary-foreground rounded-full px-4 py-1.5`, inactive `text-muted-foreground hover:text-foreground`.
- Activity heatmap: 7 rows (Mon-Sun), 52 columns (weeks). Cell size `10px`, gap `2px`. Color scale: `bg-muted` (0) → `bg-primary/30` (1-3) → `bg-primary/60` (4-7) → `bg-primary` (8+). Tooltip on hover: date + run count.

---

## 5. Interaction & Animation Specs

| Interaction | Spec |
|-------------|------|
| Sidebar toggle | `transition-transform duration-200 ease-in-out`, content reflows smoothly |
| Card hover | `transition-shadow duration-150`, `hover:shadow-lg hover:border-border/80` |
| Table row hover | `bg-muted/30`, action buttons fade in `opacity-0 group-hover:opacity-100 transition-opacity` |
| Chart tooltip | `fade-in-0 zoom-in-95` (already in Dropdown), delay 50ms |
| Panel drag (future) | CSS grid-aware; for now, keep grid static but add **reorder dropdown** in panel header |
| Tab switch | Instant, no animation; lazy-load content with skeleton |
| Toast notifications | Top-right stack, `slide-in-from-right`, auto-dismiss 4s |
| Loading states | Skeleton matching final layout exactly (no generic spinners) |

---

## 6. Component Inventory to Build / Refine

### New Components
1. `Breadcrumb` — `components/layout/Breadcrumb.tsx`
2. `GlobalSearch` — `components/layout/GlobalSearch.tsx` (cmd-k modal)
3. `ProjectCard` — `components/ui/ProjectCard.tsx`
4. `ActivityHeatmap` — `components/ui/ActivityHeatmap.tsx`
5. `StatusPill` — `components/ui/StatusPill.tsx` (replaces raw Badge usage)
6. `ChartCard` — `components/charts/ChartCard.tsx` (wrapper with title bar + actions)
7. `SyncCrosshairProvider` — `components/charts/SyncCrosshairProvider.tsx` (React context for multi-chart hover)
8. `PanelHeader` — `components/ui/PanelHeader.tsx` (title + count + nav + actions)
9. `QueryBar` — `components/ui/QueryBar.tsx` (monaco-like pill input)
10. `CollapsibleSidebar` — refactor `Layout.tsx` sidebar into collapsible variant

### Refine Existing
1. `Layout.tsx` → add breadcrumb, global search trigger, contextual actions
2. `RunDetail.tsx` → adopt ChartCard + PanelHeader + SyncCrosshair + QueryBar
3. `Dashboard.tsx` → add sparkline stat cards, active pipeline progress bars
4. `Table` patterns → standardize across all pages (extract reusable `DataTable`)
5. `TrainingMetricsChart.tsx` → add gradient fill, crosshair sync

---

## 7. Sidecar ↔ Page Connections

The Run Detail page (Screenshot C/D) and Home page (Screenshot E) share the **same left sidebar** but the Run Detail sidebar should be **collapsible** to maximize workspace area.

| Page | Sidebar Mode | Contextual Actions in Header |
|------|-------------|------------------------------|
| Home (`/`) | Full expanded | New Run, New Experiment |
| Projects (`/projects`) | Full expanded | New Project |
| Run Detail (`/runs/:runId`) | Collapsible (icon-only) | Compare, Download, Share |
| Profile (`/profile`) | Full expanded | Edit Profile |
| Workspace (`/workspace`) | Full expanded | Add Panel, Edit Toggle |

**Navigation flow:**
```
Home ──→ Projects ──→ Project Detail ──→ Runs ──→ Run Detail
  │         │              │                │
  └─────────┴── Activities ┴── Reports ────┘
```

---

## 8. Comprehensive Implementation Prompt

**Copy and paste the following into Claude Code:**

---

```
Refine the AutoPipe dashboard frontend to match the attached design specifications.

TECH STACK CONSTRAINTS:
- React 18 + Vite + TypeScript
- Tailwind CSS v3 (use arbitrary values sparingly; prefer configured tokens)
- Recharts for charts
- @tanstack/react-query for data
- react-router-dom v6
- Lucide React for icons
- NO new dependencies beyond the above without explicit approval
- Existing components in src/components/ui/index.tsx must be preserved/extended, not replaced with external libraries

PRIORITY ORDER — implement in this exact sequence:

1. GLOBAL SHELL REFINEMENT
   - Update Layout.tsx:
     a) Tighten sidebar to `w-60` (15rem), add collapsible toggle that shrinks to `w-14` icon-only.
     b) Active nav item gets a `border-l-2 border-primary bg-primary/5` accent.
     c) Add a Breadcrumb component to the main header area using current route segments.
     d) Add a cmd-k search trigger button in header (just UI; backend later).
   - Add components/layout/Breadcrumb.tsx and components/layout/GlobalSearch.tsx.

2. DESIGN TOKENS & GLOBAL STYLES
   - In globals.css, add:
     a) `.surface-elevated { @apply bg-[hsl(220,15%,10%)] border border-border/60 rounded-xl; }`
     b) `.panel-header { @apply flex items-center justify-between px-3 py-2 border-b border-border bg-muted/20 rounded-t-lg text-sm font-medium; }`
     c) Utility `.tabular-nums { font-variant-numeric: tabular-nums; }`
   - Ensure dark mode is default (already true via ThemeProvider).

3. REUSABLE UI COMPONENTS
   - Add to src/components/ui/index.tsx:
     a) StatusPill: colored dot + text label. Variants: pending (amber pulse), running (blue pulse), finished (green), failed (red), default (gray).
     b) PanelHeader: left side = icon + title + count badge; right side = action buttons (settings, add, fullscreen).
     c) ChartCard: wraps a Recharts chart with PanelHeader and `bg-card border border-border rounded-lg p-4`.
   - Add src/components/charts/SyncCrosshairProvider.tsx: React context that stores a shared x-axis value; all line charts read from it and render a ReferenceLine when active.

4. PAGE: RUN DETAIL (`/runs/:runId`)
   - Refactor RunDetail.tsx into a multi-section scrollable page, NOT separate routes. Keep current tabs (logs, metrics, checkpoints) but add the W&B-style workspace sections:
     a) Query bar at top: monospace pill input, `runs.summary["..."]` syntax highlighted, Filter button.
     b) Tables section: PanelHeader + dataframe table with tabular nums, status checkmarks in green pills.
     c) Charts section ("train"): grid of line charts using ChartCard + SyncCrosshairProvider. Add gradient fill under lines. Charts: train/loss, train/epoch_loss, train/epoch_accuracy, train/accuracy.
     d) Parameters section: histogram grid with diverging colors (blue for negative, coral for positive, white center). Use BarChart from Recharts with custom cells.
   - Add chart download button: serialize Recharts SVG to PNG via canvas.
   - All tables get row hover states `hover:bg-muted/30`.

5. PAGE: HOME (`/`)
   - Stat cards: add top accent line (2px) matching icon color. Trend text below value.
   - Replace generic activity list with a denser feed: icon + event text + relative time.
   - Active pipelines table: add inline progress bars for running pipelines.
   - Keep resource usage area chart; add synced hover crosshair.

6. PAGE: PROJECTS LIST (create if missing at `/projects`)
   - Build the Projects page referenced in routes.tsx that currently has no dedicated component.
   - Horizontal "Starred Projects" card row at top.
   - Main table: Name | Last Run | Visibility (pill) | Runs | Traces | Health (sparkline).
   - Empty states with CTA buttons.

7. PAGE: PROFILE (`/profile`)
   - Redesign current placeholder or create new.
   - Avatar with initials, tabbed interface (Profile / Reports / Projects / Stars).
   - Activity heatmap: 52×7 grid, color scale using primary opacity, tooltip on hover.
   - Recent Runs table with StatusPill.

8. POLISH & CLEANUP
   - Every table, card, and chart must have a defined empty state.
   - Replace all raw `<Badge>` usage for status with `<StatusPill>`.
   - Ensure all buttons have `focus-visible:ring-2 focus-visible:ring-ring`.
   - Add `scrollbar-thin` utility to all scrollable panels.
   - Verify no hydration mismatches; use `mounted` guard pattern already in Dashboard.tsx everywhere client-only content is rendered.

SUCCESS CRITERIA:
- Run `pnpm build` passes with zero TypeScript errors.
- Run `pnpm lint` passes (or your pre-configured lint command).
- Sidebar is collapsible and active state is clear.
- Run Detail page shows Query bar, Tables, Charts (with synced crosshair), and Parameters sections in a single scrollable view.
- All empty states show icon + message + CTA.
- No visual regressions on existing Workspace page (`/workspace`).
```

---

**END OF PROMPT**
