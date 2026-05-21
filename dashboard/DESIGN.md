---
name: My Life in Data
description: A personal data platform dashboard with a producer-console aesthetic.
colors:
  channel-green: "#1DB954"
  channel-red: "#FF0000"
  channel-violet: "#A855F7"
  channel-blue: "#4285F4"
  rack-black: "#1A1A1A"
  rack-charcoal: "#2D2D2D"
  signal-white: "#FFFFFF"
  signal-white-60: "#FFFFFF99"
  signal-white-40: "#FFFFFF66"
  signal-white-10: "#FFFFFF1A"
  trace-up: "#34D399"
  trace-down: "#F87171"
typography:
  display:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(3rem, 7vw, 6rem)"
    fontWeight: 700
    lineHeight: 1.0
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    letterSpacing: "0.05em"
  numeric:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1
    fontFeature: "tnum"
rounded:
  sm: "4px"
  md: "8px"
  lg: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
  2xl: "64px"
components:
  channel-tile:
    backgroundColor: "{colors.rack-black}"
    textColor: "{colors.signal-white}"
    rounded: "{rounded.md}"
    padding: "20px"
  kpi-meter:
    backgroundColor: "{colors.rack-black}"
    textColor: "{colors.signal-white}"
    typography: "{typography.numeric}"
    rounded: "{rounded.md}"
    padding: "16px 20px"
  button-primary:
    backgroundColor: "{colors.signal-white}"
    textColor: "{colors.rack-black}"
    rounded: "{rounded.sm}"
    padding: "10px 16px"
  button-ghost:
    backgroundColor: "{colors.rack-black}"
    textColor: "{colors.signal-white-60}"
    rounded: "{rounded.sm}"
    padding: "10px 16px"
  input-field:
    backgroundColor: "{colors.rack-black}"
    textColor: "{colors.signal-white}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
---

# Design System: My Life in Data

## 1. Overview

**Creative North Star: "The Producer's Console"**

The dashboard is a control room for one person's digital life. Four channels — Spotify, YouTube, Maps, Calendar — feed signal into one master view. The aesthetic borrows from studio gear and modular synths: matte rack surfaces, mono-forward labels, LED-tinted accents, fader-strip layouts where each channel has its lane and its signature color. The home page reads like a mixing desk; each source page reads like a soloed channel.

Two reference frequencies share the band: **Raycast** sets the baseline tempo (dense, restrained, confident), and **Spotify Wrapped at ~70% intensity** owns the expressive moments (a soloed channel briefly takes over a hero, a big mono numeral lands like a peak meter). They alternate — never both at full volume at once. A Wrapped-flavored hero earns its loudness because the KPI rows beneath it are surgical and calm.

The dashboard rejects what saturates the category: dark-purple SaaS templates, glass-card stacks, hero-metric tile grids, and Wrapped's social-share excess (full-bleed story-per-screen, 100%-saturation everywhere, screen-filling display type). Those are campaigns; this is a product.

**Key Characteristics:**
- Producer-console aesthetic: rack surfaces, fader strips, LED-tinted channel colors, mono numerics
- Calm bones (Raycast), expressive moments (Wrapped at 70%) — never both loud at once
- Flat-by-default surfaces; lift only in response to state (hover, focus)
- Voice in copy, not in chrome
- Channel-color discipline: each source owns one accent, used as signal not decoration

## 2. Colors

A near-black rack body lit by four signature channel colors. Neutrals are tinted toward warm gray; nothing is pure `#000` or `#fff`. Source colors are LEDs on a console — used to identify a lane, not to flood it.

### Primary

The four channel colors. Each owns one source and never crosses lanes.

- **Channel Green** (`#1DB954`): Spotify lane. Listening data, the live-now indicator, all Spotify-page accents.
- **Channel Red** (`#FF0000`): YouTube lane. Watching data, ads markers, YouTube-page accents.
- **Channel Violet** (`#A855F7`): Maps lane. Movement, directions, place visits, Maps-page accents.
- **Channel Blue** (`#4285F4`): Calendar lane. Meetings, time blocks, scheduling. (Replaces the legacy Google Search treatment; the same blue carries through.)

### Neutral

The console body and signal layer.

- **Rack Black** (`#1A1A1A`): the deepest neutral. Body gradient origin, modal scrims, console base.
- **Rack Charcoal** (`#2D2D2D`): the body gradient terminus. Together they form the matte rack finish (`bg-gradient-to-br from-#1A1A1A to-#2D2D2D`).
- **Signal White** (`#FFFFFF`): primary text. Used at full opacity for headlines, KPI numerics.
- **Signal White / 60%** (`#FFFFFF` at 0.6): body copy, secondary labels.
- **Signal White / 40%** (`#FFFFFF` at 0.4): tertiary metadata, timestamps, deemphasized chrome.
- **Signal White / 10%** (`#FFFFFF` at 0.1): hairline borders, dividers, axis lines on charts.

### Tertiary (state)

- **Trace Up** (`#34D399`): positive trends, increases. Distinct from Channel Green so a positive Spotify trend doesn't visually collide with Spotify's identity.
- **Trace Down** (`#F87171`): negative trends, decreases, error states.

### Named Rules

**The Channel-Lane Rule.** A channel color owns its source page and only its source page. Channel Green never appears on the YouTube page; Channel Red never appears in a Spotify chart. Cross-source aggregate pages (Home, AI chat) may show all four together — that is the only context where they share a screen.

**The 10% Rule, Reframed.** Outside Wrapped-flavored moments, the channel color occupies ≤10% of any given screen. Inside a Wrapped moment — a hero, a live-now card, a soloed channel — it may occupy 30–60% of a contained area, never the whole viewport.

**The Trace-Not-Identity Rule.** Trends (up/down) use Trace Up / Trace Down, not the channel color. The channel color is the source's identity; the trace is the data's direction. They never overlap on the same element.

## 3. Typography

**Display Font:** system sans (Tailwind `ui-sans-serif`) — placeholder. Production target: a humanist sans with engineering character (IBM Plex Sans or Inter Tight, see Do's).
**Body Font:** same as Display.
**Label / Numeric Font:** system mono (Tailwind `ui-monospace`) — placeholder. Production target: IBM Plex Mono or JetBrains Mono.

**Character.** Sans for prose, mono for everything that should read as instrumented — KPI values, timestamps, axis ticks, channel identifiers. Mono is the console's data layer; sans is the voice.

### Hierarchy

- **Display** (700, `clamp(3rem, 7vw, 6rem)`, line-height 1.0, tracking −0.02em): hero on Home; the source-page title on Spotify / YouTube / Maps / Calendar pages.
- **Headline** (700, 1.875rem / 30px, line-height 1.2): top-of-section H2s within a page.
- **Title** (600, 1.25rem / 20px): card titles, sub-section headers.
- **Body** (400, 1rem, line-height 1.6, max 65–75ch): prose, KPI explainer markdown, tooltip detail.
- **Label** (mono, 500, 0.75rem, tracking 0.05em): KPI captions, axis labels, channel identifiers. Slight letter-spacing to read as instrumented.
- **Numeric** (mono, 700, 1.875rem, tabular figures): all KPI values, every figure that updates as data changes.

### Named Rules

**The Mono-for-Data Rule.** Anything that is a number rendered from data — KPI values, timestamps, percentages, durations, axis ticks — is set in mono with tabular figures (`font-feature-settings: "tnum"`). Prose is sans. Mixing the two is how the producer console reads as instrumented rather than narrated.

**The 65ch Rule.** Body prose (the explainer pages especially) caps line length at 65–75ch. The dashboard breathes; long lines do not.

## 4. Elevation

**Flat-by-default with state-driven lift.** Surfaces sit on the rack body without shadow, separated only by a hairline border (Signal White / 10%) or a tonal step. Elevation appears as a *response*: on hover, on focus, on the active live-now state. Never as decoration.

The legacy glassmorphism (`bg-white/5 backdrop-blur-sm border-white/10` everywhere) is the system's prior aesthetic and is being phased out. The frontmatter and Components below describe the destination, not the current code.

### Shadow Vocabulary

- **Lift** (`box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4)`): hover state on interactive surfaces (channel tiles, list rows). Subtle, downward, charcoal-tinted.
- **Channel Glow** (`box-shadow: 0 0 32px {channel-color}/30`): hover or active state on a soloed channel tile only. Tinted by the channel color, used sparingly to suggest the lane is live.
- **Focus Ring** (`outline: 2px solid {channel-color}; outline-offset: 2px`): keyboard focus on any interactive element. Sharp, not glowing — clarity over decoration.

### Named Rules

**The Flat-Rest Rule.** Every surface is flat at rest. No drop shadows, no glass blur, no gradient borders. If the surface looks elevated when nothing is happening, it is over-designed.

**The Single-Lift Rule.** Only one element on a screen lifts at a time. Hover state is exclusive — when one tile lifts, the rest stay flat. Multiple simultaneous lifts read as a card party, not a console.

## 5. Components

### Channel Tile

The signature component. Used on Home as the four source cards; conceptually a strip of a mixing desk.

- **Shape:** rounded-md (8px). Square-ish, decisive corners.
- **Background:** Rack Black at rest.
- **Border:** Signal White / 10% hairline at rest.
- **Internal padding:** 20px.
- **Layout:** channel color LED (8px square, top-left), label in mono / uppercase / tracked, primary KPI in display-mono numeric, secondary KPI smaller below. A thin horizontal fader-bar at the bottom visualizes magnitude vs. the other channels (optional, on Home only).
- **Hover:** Lift shadow + Channel Glow tinted by the channel color. Border becomes the channel color at 40% opacity.
- **Focus:** Focus Ring in the channel color.

### KPI Meter

The fader-strip variant for per-source pages.

- **Shape:** rounded-md (8px), hairline border.
- **Background:** Rack Black.
- **Layout:** mono label across the top (uppercase, small, tracked), large mono numeric in the channel color, a thin fader-bar below showing value-vs-target or value-vs-period — optional, but where the fader-strip metaphor lives.
- **States:** flat at rest. No hover state on KPI meters (they are not interactive); only the focus ring if focusable for keyboard users.

### Cards / Containers

There are no decorative cards. Containers exist only when grouping is semantically real (a chart and its legend, a list and its header). When they exist:

- **Corner Style:** rounded-md (8px).
- **Background:** Rack Black, no glass blur.
- **Border:** Signal White / 10% hairline.
- **Internal padding:** 24px.
- **Shadow Strategy:** none at rest. See Elevation.
- **No nested containers.** A card inside a card is forbidden.

### Buttons

- **Shape:** rounded-sm (4px). Compact, deliberate.
- **Primary:** Signal White background, Rack Black text, 10px × 16px padding, font-weight 500, mono. Used sparingly — confirmation actions, only.
- **Ghost:** Rack Black background, Signal White / 60% text, hairline border. Default for nav and secondary actions.
- **Hover:** Lift shadow on primary; border opacity steps up on ghost (60% → full).
- **Focus:** Focus Ring in Signal White or channel color depending on context.
- **No CTA gradients, no glow buttons, no Wrapped-style oversized buttons.**

### Inputs / Fields

- **Style:** Rack Black surface, hairline border at rest, mono input text.
- **Focus:** Border becomes Signal White; outline ring in the page's channel color (or Signal White on Home). Sharp transition, no glow blur.
- **Error:** Border becomes Trace Down. Error text in Trace Down, mono, beneath the field.

### Live Track Card (Spotify signature)

The dashboard's clearest Wrapped-flavored moment. Already a strong starting point; refine within the system.

- **Background at rest:** Rack Black with a thin Channel Green hairline.
- **Background when playing:** drenched Channel Green gradient (40% → 5% top-to-bottom), Channel Green border. The "soloed channel" treatment.
- **Layout:** album art (rounded-md, 128px) left, track / artist / status right in display-sans + mono metadata. "LIVE NOW" indicator with a pulsing channel-color dot.
- **Voice opportunity:** the metadata lines ("Album: …", "Device: …") are flat by default. Add a wry one-line caption when nothing is playing ("The studio is quiet.") rather than a generic empty state.

### Recent Event Row (Home)

A list item, not a card.

- **Shape:** no border-radius on the row itself; padding only. Subtle horizontal hairline (Signal White / 10%) between rows.
- **Channel indicator:** an 8×8 channel-color LED on the left, not a side stripe. (The current `border-left: 3px solid` treatment is the side-stripe anti-pattern — replace it.)
- **Hover:** Row background steps from Rack Black to a slight tonal lift (Signal White / 3%). No shadow.

### Navigation

Not yet implemented. Direction:

- **Style:** persistent top bar with channel buttons (Spotify / YouTube / Maps / Calendar) as ghost buttons in mono, plus a logo/wordmark on the left.
- **Active state:** the active source's channel color in the underline or focus ring; never as a full background fill.
- **Mobile:** collapses to a slide-over with the four channels stacked vertically.

## 6. Do's and Don'ts

### Do:

- **Do** treat every source as a channel: one color, one lane, one signature LED. Cross-channel mixing happens only on aggregate views (Home, the planned AI chat).
- **Do** set all numerics in mono with tabular figures. Every KPI, every timestamp, every axis tick.
- **Do** keep surfaces flat at rest. Lift, glow, and ring belong to *response*, not decoration.
- **Do** earn Wrapped-flavored loud moments by surrounding them with restraint. A drenched hero buys its volume by being followed by surgical KPI rows.
- **Do** put personality in copy first: headlines, empty states, error messages, the no-track caption on the Live Track card. The chart stays calm.
- **Do** install a real type pairing in Tailwind config: **IBM Plex Sans + IBM Plex Mono** (or **Inter Tight + JetBrains Mono**) before treating typography as solved. The current system-stack fallback is a placeholder.
- **Do** respect `prefers-reduced-motion`. Disable Typewriter, ParticleBackground, and entrance Framer Motion when set.
- **Do** maintain 4.5:1 contrast on body text and 3:1 on labels — even inside Wrapped-flavored drenched moments.

### Don't:

- **Don't** use glassmorphism (`backdrop-blur`, `bg-white/5` frosted panels) as a default surface. It is on impeccable's absolute-ban list and is the current dashboard's biggest tell.
- **Don't** ship side-stripe borders (`border-left: 3px solid {color}`) as a row affordance. Replace with the 8×8 LED + hairline divider.
- **Don't** nest containers. A card inside a card is forbidden. The Home page's "Recent Events" colored sub-blocks inside a glass wrapper are exactly this.
- **Don't** repeat the hero-metric template (big number, small label, supporting stat, gradient accent — × 4 across the top of every page). One KPI row per page is enough; the rest of the page should not be more KPI tiles.
- **Don't** use purple-to-blue or any other "AI tool" gradient. Channel colors are LEDs, not gradients.
- **Don't** apply `background-clip: text` gradient text anywhere. Single solid colors for type, always.
- **Don't** let Wrapped energy spill into format. No story-mode-per-viewport, no full-bleed single-stat screens, no 100%-saturation flooding the whole canvas. The 70% intensity cap is real.
- **Don't** style trend indicators with the channel color. Trends use Trace Up / Trace Down. The channel color is identity, not direction.
- **Don't** hard-code source hex values in components (`#1DB954`, `#FF0000` repeated dozens of times across `Home.tsx`, `Spotify.tsx`, charts). Reference them through the `colors.channel-*` tokens.
