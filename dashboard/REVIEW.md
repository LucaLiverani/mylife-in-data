# My Life in Data — design + product review

> Brutally honest review against `PRODUCT.md` and `DESIGN.md`.
> Generated 2026-05-21 via `/impeccable critique` + `/impeccable audit`.
> Detector script: 0 anti-patterns found in `src/`.

## 1) Executive verdict

The dashboard is in a much better place than its `git status` suggests. The refactor has cleared the worst absolute-ban offenders — the detector script found **zero** anti-patterns in `src/`, and the new `ChannelStrip` / `Sparkline` / `Surface` / `KPIMetric` set is a real, internally consistent system. But the surface still reads "advanced side project" in three specific ways: (a) two of the four source pages bleed Tailwind-default rainbow hex into channel-lane charts, breaking the most strategically-important rule in DESIGN.md; (b) the source pages diverge in chart sophistication and loading-state language enough that they feel built by different sessions; (c) the IA is one-deep — there's no navigation between sources and no help/explainer layer, so a portfolio visitor cannot drill from "glance" to "depth," which is design principle #4. Spotify and Home are real product. YouTube, Maps, and Calendar are partway through becoming it.

## 2) Health scores

### Audit dimensions (0–4)

| # | Dimension | Score | Key finding |
|---|---|---|---|
| 1 | Accessibility | 2.5 | Focus rings + ARIA mostly present; no skeleton loading; `text-red-400` and `bg-yellow-500/10` slip outside the contrast/system; chart text alternatives missing |
| 2 | Performance | 3 | Lazy routes; Sparkline is pure SVG; Leaflet dynamic import; Spotify poll is visibility-aware. Recharts still ships to Home via DataGenerationChart |
| 3 | Responsive | 2.5 | Breakpoints exist (`md:`/`lg:`) but the Live Track card and the TopList secondary-column measurement need real device verification; fixed-px chart heights |
| 4 | Theming | 2.5 | Channel system is well-built; `#3b82f6`/`#10b981`/`#f59e0b`/`#8b5cf6` rainbow hex in YouTubeCharts and MapsCharts is the biggest theming regression in the repo |
| 5 | Anti-Patterns | 3 | Detector: 0 findings. Manual: rainbow hex (above), generic SaaS spinners on 3 pages, headline style mix, blockquote side-stripe is borderline |
| **Total** | | **13.5/20** | **Acceptable — significant work needed, but the foundation is right** |

### Nielsen's 10 (LLM critique) — 0–4

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Live Spotify + ClickHouse-offline banner are good; no skeleton on data |
| 2 | Match real world | 3 | "Channel/console/signal" vocab is consistent |
| 3 | User control & freedom | 1 | **No nav between sources.** Every cross-navigation routes through Home |
| 4 | Consistency & standards | 2 | Headline styles, loading states, chart strategies, and color palettes diverge across pages |
| 5 | Error prevention | 2 | Few destructive surfaces. Error UIs functional but ad-hoc |
| 6 | Recognition over recall | 3 | LED + mono labels read clearly |
| 7 | Flexibility & efficiency | 1 | No keyboard shortcuts, no search, no filters, no deep links into charts |
| 8 | Aesthetic & minimalist | 3 | Producer-console direction is distinctive |
| 9 | Error recovery | 3 | RouteErrorBoundary is well-built |
| 10 | Help & documentation | 1 | Zero. No KPI explainers, no infra walkthrough, no source-level docs |
| **Total** | | **22/40** | **Mid-band — acceptable, room to climb** |

### Composite per page

| Page | A11y | Theming | Anti-Patterns | Voice | Consistency | Composite |
|---|---|---|---|---|---|---|
| Home `/` | 3 | 3 | 3 | 3 | 3 | **15/20** — strongest |
| Spotify `/spotify` | 2.5 | 2.5 | 3 | 3 | 2.5 | **13.5/20** — best content, headline mix |
| YouTube `/youtube` | 2.5 | **1.5** | 2 | 2.5 | 2 | **10.5/20** — rainbow hex hurts |
| Maps `/maps` | 2 | **1.5** | 2 | 2.5 | 2 | **10/20** — rainbow hex + yellow alert |
| Calendar `/google` | 3 | 3 | 3 | 2 | 3 | **14/20** — clean but slim |

## 3) Detailed findings

### Cross-cutting — these touch every page

**[P0] Rainbow hex inside channel lanes.** `YouTubeCharts.tsx:74–77,91,181–214` and `MapsCharts.tsx:118–122,133,207–242` ship `#3b82f6`, `#10b981`, `#f59e0b`, `#8b5cf6` as series colors inside the YouTube and Maps pages. Spotify-green-adjacent and Calendar-blue-adjacent colors are landing on YouTube and Maps surfaces. Single most damaging violation in the codebase against the Channel-Lane Rule (DESIGN.md §2). Fix: extend `CHANNEL_RAMP` to cover sub-segments per source and pass that ramp into every multi-series chart.

**[P0] `CHART_COLORS.google` is `undefined`.** `chartConfig.ts:7–18` defines `spotify/youtube/maps/calendar/traceUp/traceDown` plus shade arrays — but no `google` key. `DataGenerationChart.tsx:41,54,145,147` reads `CHART_COLORS.google` four times. The "Google" line on Home renders with no stroke color (browser default). Also: the chart still labels a series "Google" when the dashboard's taxonomy has moved to "Calendar."

**[P1] Loading states diverge.** Home: `Loading the console…` (mono uppercase, on-voice). Calendar: `Loading the schedule…`. Spotify, YouTube, Maps: `border-4 border-channel-{x} border-t-transparent rounded-full animate-spin` spinner with prose. Three patterns. Pick one.

**[P1] Headline-style mix within pages.** Each source page interleaves two H2 idioms:
- `font-mono text-xs uppercase tracking-wider text-signal-white/60` (producer-console label) — good
- `text-2xl font-bold` (generic dashboard headline) — generic

Examples: `SpotifyCharts.tsx:44 vs 72`; `YouTubeCharts.tsx:108 vs 227`; `MapsCharts.tsx:144 vs 253`. Two voices in one page. Pick the mono label as system standard.

**[P1] No persistent navigation.** `App.tsx:24–29` defines four routes. Only way between them is via Home channel strips. DESIGN.md §5 acknowledges this gap.

**[P2] `text-red-400` and yellow alert color outside tokens.** `Spotify.tsx:79`, `YouTube.tsx:101` use `text-red-400`. `Maps.tsx:103` uses `bg-yellow-500/10 border-yellow-500/20 text-yellow-300`. System has `trace-down`; no yellow exists.

**[P2] Hardcoded inline hex in TravelMap.** `TravelMap.tsx:60,75,78,131` uses `#fff`, `#1A1A1A`, `#666`, gradient. Marker has unconditional `box-shadow` glow (Flat-Rest violation).

**[P2] DataGenerationChart embeds three mini-KPIs inside a card.** `DataGenerationChart.tsx:60–82` — hero-metric-tile-strip wedged inside another container.

**[P3] Sparkline scale loses meaning.** `Sparkline.tsx:50–51` uses min/max of each series. All-equal-low and all-equal-high render identically.

**[P3] DESIGN.md doc drift.** Still references deleted `ParticleBackground` and `Typewriter`.

### Home `/`

**Strengths.** Channel-strip grid is genuinely good. Pulsing-LED-when-live signal is the cleanest piece of micro-state in the app. Hero copy is on-voice.

- **[P1] Blockquote side-stripe** on `Home.tsx:261`. Replace with leading channel-green glyph or just italic + 60% opacity.
- **[P1] Three identical channel panels in Recent Signal omit Calendar.** Either add a fourth panel or replace whole section with a unified cross-channel timeline.
- **[P2] DataGenerationChart still references "Google" series.** Breaks page taxonomy.
- **[P2] Hero feels under-committed.** Three lines of stacked copy. Commit it (big mono number) or shrink it further.
- **[P2] No "now" signal in hero.** Most exciting thing (live Spotify) buried 200px down.

### Spotify `/spotify`

**Strengths.** Best-realized source page. Live Track card is the strongest single component. TopList alignment work is craft.

- **[P1] H2 styling collision.** Top Artists / Genre Distribution are mono-uppercase; Daily Listening Hours / Recently Played are `text-2xl font-bold`.
- **[P1] "Recently Played" list re-implements EventRow inline** — `SpotifyCharts.tsx:99–129`.
- **[P2] Spinning circle loader.** Replace with skeleton or mono-uppercase loading line.
- **[P2] Page never reaches its own promise** — tagline says "deep dive into obsessions" but the charts are top-of-mind only.

### YouTube `/youtube`

- **[P0] Rainbow hex.** Single biggest issue on the page.
- **[P0] Two of five series default-off** (`Visits: false, Other: false` — `YouTubeCharts.tsx:53–55`).
- **[P1] H2 mix.**
- **[P1] "Ads" KPI is the most distinctive YouTube signal and the page doesn't lean into it.** Promote to hero stat.
- **[P2] No genre/category breakdown over time.**

### Maps `/maps`

- **[P0] Rainbow hex.**
- **[P0] No distance, no time-away-from-home, no real movement story.** Page is branded "Travel" but contains zero travel KPIs.
- **[P1] Yellow alert color.**
- **[P1] Map marker glow at rest.**
- **[P2] Inline popup styles** with literal hex.
- **[P2] Map polylines connect markers in input order** without dates — mathematically meaningless.

### Calendar `/google`

**Strengths.** Cleanest source page. Uses `ChannelPie`, `ChannelHistogram`, `Surface` correctly. No rainbow hex.

- **[P1] Tagline is the weakest.** "Plans made, places to be. Negative space included." — generic.
- **[P1] "Coming up" colors compete** — per-category LED + channel-blue time text on same row.
- **[P2] Only four charts; thin page.**
- **[P2] Route is `/google`, page H1 is "Calendar."** Rename `/calendar`, redirect from `/google`.
- **[P3] No upcoming today/this-week segmentation.**

## 4) Proposals

### 4.1 New KPIs

**Spotify**
- ★ **Concentration index** — Gini coefficient of plays-per-artist (or top-5-share-of-total-hours). "I'm a sampler" (0.3) vs "I'm obsessed with 4 artists" (0.7).
- **Discovery rate** — first-time artists per month.
- **Longest streak** — consecutive days with ≥1 listen.
- ★ **Late-night share** — % of listening between 22:00 and 04:00.

**YouTube**
- ★ **Ads-as-share-of-time** — promote existing computation to hero stat above KPI row.
- ★ **Autoplay-chain length** — average count of consecutive videos watched within N minutes.
- **Channel monogamy** — % of total time spent on top-1 / top-5 channels.
- **Deep-watch rate** — share of videos watched >50%.

**Maps**
- ★ **Kilometers traveled** — straight-line distance summed across consecutive activities with location.
- ★ **Days away from home** — count of days with any activity >50km from home centroid.
- **New-place rate** — first-time location visits per month.
- **Longest single trip** — consecutive days away from home.

**Calendar**
- ★ **Free time / day** — sum of unscheduled minutes inside 09:00–19:00 window, daily average.
- ★ **Longest unscheduled stretch** — average longest contiguous gap per day, in hours.
- **Meeting fragmentation** — Herfindahl index of small blocks splitting the day.
- **Weekend leakage** — count of weekend events.

**Home (cross-source)**
- ★ **Noisiest hour** — single hour of past 24h with most events across all four channels.
- ★ **Quiet streak** — minutes since last event of any kind.
- **Channel dominance %** — share of last-24h events by source.
- **Days tracked** — count of distinct days the platform has data for.

★ = signature signals (not in source app UIs).

### 4.2 New charts

**Spotify**
- **Listening calendar heatmap** — 53 weeks × 7 days × intensity. New primitive `CalendarHeatmap`.
- **Hour-of-day ridgeline** — 24 vertical mini-curves by hour-of-day, one per weekday.

**YouTube**
- **Category stacked area over 90d** — stream graph showing how watching mix shifts.
- **Channel-discovery network** — node-link map of channels watched ≥5 videos from. New primitive `ChannelGraph`.

**Maps**
- **Distance-over-time area chart** — cumulative km traveled by month.
- **Trip-segments timeline** — horizontal Gantt-like bars per "away period." New primitive `TimelineBars`.

**Calendar**
- **Weekly schedule grid** (24h × 7d) — canonical "where did time go?" view. New primitive `WeekGrid`.
- **Free-time ridgeline by weekday.**

**Home (cross-source)**
- **Cross-channel 24h activity heatmap** — 4 rows × 24 columns. The single most important chart Home is missing.
- **Signal mix over 90d** — stacked area replacing DataGenerationChart, with channel-correct colors and "Calendar" not "Google."

### 4.3 New sections / pages

1. **`/now`** ★ — last 60 minutes across all channels. Single timeline scrolled to the right. The producer-console as real-time.
2. **`/system`** ★ — pipeline health page. Ingestion lag per source, last-successful-batch timestamps, dbt run status, ClickHouse query latency, error counts. **The portfolio piece.**
3. **`/year`** — cross-source year-in-review. Wrapped-flavored, scrolled vertically, dense not loud.
4. **`/explain/[source]`** — KPI definition pages. Markdown rendered. Makes design principle #4 real.
5. **Global search.** Cmd-K palette across all events.
6. **AI chat (PRODUCT.md roadmap).** Persistent slide-over entry from top bar.

### 4.4 Home rebuild

**Option A (incremental, S–M):** strip hero to one line + tagline; replace DataGenerationChart mini-KPIs with quiet 90d stacked area; replace three-panel Recent Signal with single cross-channel 24h heatmap; add cross-channel KPI under hero.

**Option B (rebuild, M–L) — recommended:** cross-channel 24h heatmap as **literal background** behind hero; channel strips collapse to **fader bank** (vertical meters); instrumentation row of Quiet-streak / Noisiest-hour / Days-tracked; Recent Signal becomes `/now` link.

### 4.5 Weaknesses

- **Maps page** weakest — branded "Travel" but zero travel KPIs.
- **Calendar page** thinnest — clean but slim. WeekGrid + Free-time addition would make it most differentiated.
- **No help layer** kills design principle #4.
- **Inconsistent chart sophistication** signals "built in different sessions."

## 5) PRODUCT.md / DESIGN.md — challenges

- **DESIGN.md §2 says channel colors are LEDs, never gradients.** Live Track card breaks this with channel-green/30 → channel-green/5. That's a good gradient. Amend rule: "Gradients permitted only in declared Wrapped-flavored moments."
- **"No decorative cards" rule vs ubiquitous Surface usage.** Doc and code disagree. Either acknowledge section grouping IS semantic, or strip surfaces where headings alone suffice.
- **"No full-bleed story-per-screen"** anti-reference. For `/year`, that's exactly what works. Carve a yearly exception.

## 6) Recommended next moves

1. **`/impeccable colorize`** — eliminate rainbow hex. P0.
2. **`/impeccable polish`** — loading states + headline-mix + bad color tokens + shared EventRow. P1.
3. **`/impeccable shape`** — `/system` page. P1.
4. **`/impeccable shape`** — Home Option B rebuild. P1.
5. **`/impeccable craft`** — Maps travel KPIs. P1.
6. **`/impeccable craft`** — Calendar `WeekGrid` + Free-time KPIs. P1.
7. **`/impeccable layout`** — global top-bar navigation. P1.
8. **`/impeccable document`** — refresh DESIGN.md. P2.
9. **`/impeccable craft`** — `/now` page + AI chat slide-over. P2.

After step 2, re-run `/impeccable audit` and `/impeccable critique` — composite score should jump from ~13.5/20 to ~16/20.

---

**Verdict in one sentence:** the bones are right; the surface needs one ruthless color-discipline pass, one consistency pass, and one ambitious page (`/system`) to stop reading as "advanced side project" and start reading as "real product."
