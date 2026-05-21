# Product

## Register

product

## Users

Two audiences sharing one surface.

- **Primary (Luca, daily):** owner of the data platform. Glances at the dashboard to see what their digital life looks like across services (Spotify listening, YouTube watching, Maps activity, Google Calendar) and to sanity-check that ingestion is still running.
- **Secondary (portfolio visitor, first-time):** recruiter, peer, or curious link-follower. Lands without context. Must understand within seconds that this is a real product showcasing end-to-end data-platform skills (ingestion → ClickHouse → dbt → dashboard), not a weekend side project.
- **Future:** anyone interacting with the planned AI chat-with-my-data feature and the per-source explainer pages (rendered markdown about KPI definitions and the infrastructure that produces them).

## Product Purpose

Visualize one person's digital life across services in a single coherent surface, while doubling as a public portfolio piece for the underlying data platform.

The dashboard is the visible tip of a larger system: streaming Spotify ingest, batch YouTube / Google Takeout pipelines, dbt-modeled gold tables, all rendered through one product surface. Four signals tracked today: Spotify (listening), YouTube (watching), Maps (movement), Google Calendar (time and meetings). The roadmap adds an AI chat over the same data and per-source documentation pages (KPI explainers + infrastructure walkthroughs) — the dashboard isn't just charts, it's the front door for the whole project.

Success: a first-time visitor reads it as designed-on-purpose, not "personal dashboard side project." Returning Luca uses it daily without friction.

## Brand Personality

**Three words: dry, self-aware, technical** — with permission to be expressive.

The voice is funny and ironic, but the joke is always at the author's expense, never the visitor's. Existing taglines set the register:

- *"Turning bad habits into pretty charts."*
- *"Pretty charts, brutal honesty, optional self-improvement."*
- *"Obsessively tracking everything I should probably forget."*

That's the upper bound on quippiness. Voice belongs in headings, empty states, KPI labels, error messages, and the occasional Wrapped-flavored moment — places where the visitor expects flat copy and gets a small surprise.

### Twin benchmarks

Two co-equal references that share the surface:

- **Raycast — the calm product bones.** Sets the baseline for typography, density, navigation, restraint, and the way micro-interactions feel. Most of the dashboard reads in this register. Confident product surface, no apologies, voice in the words rather than the chrome.
- **Spotify Wrapped at ~70% intensity — the personality moments.** Used where a moment earns it: the hero on Home, the live track card, the intro header on each source page, occasional KPI flourishes. Drenched color in a contained area, one big stat treated like a statement, confident first-person copy. **Dialed down** from real Wrapped — no full-bleed story-per-screen, no 100%-saturation everywhere, no social-share excess.

The blend rule: Raycast-grade calm by default, Wrapped-flavored moments where they earn the volume. **Never both at full intensity at once.** A page with a Wrapped-style hero gets dashboard-calm KPI rows below it. A page with dense data tables gets a flat, restrained header.

## Anti-references

What this must explicitly NOT look like:

- **The Wrapped social-share excess.** One stat per viewport, story-mode scrolling, 100%-saturation everything, screen-filling display type. That's a campaign, not a product. We borrow Wrapped's energy at ~70%, not its format.
- **Generic dark-purple SaaS template.** Purple-to-blue gradients, glass cards, hero-metric tiles, the "AI tool" landing page reflex. The whole category is saturated; this should not blend in.
- **Corporate Tableau / PowerBI dashboard.** Default chart styling, gray-on-white sobriety, no voice. The data is real but the surface should not be a report.

## Design Principles

1. **Real product, not a side project.** Reads as designed-on-purpose to a first-time visitor with zero context. No "personal dashboard" framing, no apologies, no caveats. If a recruiter lands on it cold, they should see craft.
2. **Calm bones, expressive moments.** Raycast-grade restraint as the baseline tempo; Wrapped-flavored bursts in specific places (hero, live track, page intros). Earn the loud moments by surrounding them with calm. The dashboard breathes — it doesn't shout the whole time.
3. **Voice carries weight; the chart doesn't have to.** Personality lives in copy first — headings, empty states, KPI labels, error messages, microcopy on the live track. Charts and KPI rows stay calm and legible. The expressive moments use type and color, not chart decoration.
4. **One surface, many depths.** A KPI links to its chart, which links to its explainer (markdown), which links to the infrastructure doc that produces it. The design system has to support this drill-down — from glance to deep-dive — without the surface becoming heavy or losing its product feel.
5. **The joke is on the author, not the visitor.** Self-deprecating about the owner's own habits ("brutal honesty, optional self-improvement"). Never patronizing, never explaining the joke, never inside-baseball that excludes a cold reader.

## Accessibility & Inclusion

Target: **WCAG AA, keyboard navigable.**

- 4.5:1 contrast on body text, 3:1 on large text and meaningful non-text elements (icons, focus rings).
- Visible focus states on every interactive element. Logical tab order. No keyboard traps.
- Color is an accent, never the sole carrier of meaning. Each source has a signature color (Spotify green, YouTube red, Maps purple, Google blue) but state and meaning must also read through copy, icon, or shape.
- Wrapped-flavored moments still respect contrast targets. A "drenched" treatment on a hero block doesn't get to drop body-text contrast below AA.
- Respect `prefers-reduced-motion`. Disable ParticleBackground, Typewriter, and Framer Motion entrances when set. Motion is a "yes by default with an explicit off-switch," not the other way around.
- Charts get text alternatives — summary copy or accessible-name attributes that read meaningfully without the visual.
