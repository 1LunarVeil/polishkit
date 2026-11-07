# Layout, density, shape and motion

## Reading order first

Before adjusting spacing, check what is seen first, second and third. Squint or blur the screenshot: the three most prominent shapes should match the job the screen exists for. If they do not, fix hierarchy before anything else.

## Grid and structure

- Web: a 12-column grid for page layout, with an 8px rhythm for vertical spacing.
- Desktop: a sidebar of about 200 to 260px, a toolbar of about 40px, a status bar of about 24px, and content panes that scroll on their own. These are starting values; set them as tokens.
- Prose inside a wide pane needs a maximum measure. Do not stretch paragraphs to the full window width.
- Break the grid on purpose, once per screen at most, and only when the break carries meaning.

## Spacing

Use a single scale, for example 4, 8, 12, 16, 24, 32, 48 and 64px. Take the smallest value that works. Group by proximity: the gap inside a group should be at most half the gap between groups. If every gap is equal, nothing is grouped.

## Density follows frequency

- Compact (desktop tables, logs, lists): rows 28 to 32px, inner padding about 8px, one line of text per row.
- Comfortable (forms, settings, inspectors): controls 32 to 40px tall, padding 12 to 16px.
- Spacious (marketing, reading, onboarding): section padding 64 to 120px.

Choose density by how often the screen is used. A screen used forty times a day should be compact. A screen used once should explain itself with more room.

## Alignment

- Left-align text by default. Center only short, one-off blocks.
- Align each region to one edge. Mixing left, centered and right in one column reads as an accident.
- Right-align numeric columns and use tabular numerals.
- Optically align icons with the text beside them. A 16px icon usually needs its box nudged to match the x-height.

## Hierarchy costs

Create hierarchy with size, weight, color and space, in that order of cheapness. Borders and boxes are the most expensive tools: they add noise to every screen they touch. Remove a border before adding a second one.

Cards are for discrete objects a person acts on, such as a model, a session or a file. Do not wrap every piece of content in a card, and never put a card inside a card. A region gets at most one divider level.

## Radius

- One small scale for the whole product, for example 0, 2, 4, 6, 8, 12, 16 and pill (999). Controls and containers differ by at most one step.
- Nested radius: inner radius = outer radius minus padding, with a floor of 0. A 12px card with 8px padding gets a 4px inner radius.
- A single radius on everything, regardless of hierarchy, is a tell (see `anti-slop.md`).

## Elevation

Three levels at most:

- 0, flat: the default for content.
- 1, raised: menus, popovers, a panel that floats over content.
- 2, overlay: dialogs and drawers, with a scrim only when the content is large.

Tint shadows to the palette: a low-alpha shadow in the accent or neutral hue, not a generic `rgba(0,0,0,.1)` under everything. Border plus shadow together belongs to overlays only.

## Breakpoints and window sizes

- Web: 360 or 390px for phones, 768px for tablets, 1024 to 1280px for desktop, and a wide layout from about 1440px.
- Desktop windows: test the app's minimum window size, 1366 by 768 and 1920 by 1080, at 100%, 125% and 150% display scaling. A layout that fits at 100% and clips at 150% is broken.

## Motion: purpose first

Animation earns its place when it does one of four jobs: shows what changed and where it came from, confirms an action, guides attention to a new element, or covers latency that cannot be removed. Anything else is decoration. Remove it.

Frequency gate: an action the user repeats many times a session (toggling, moving through a list, keyboard navigation) gets no animation, or at most 100ms. A rare, meaningful transition (opening a panel, first load, finishing a long task) may carry more.

## Durations and easing

| Use | Duration |
|---|---|
| Hover, press, toggle | 100 to 150ms |
| State change (expand, tab switch) | 150 to 250ms |
| Overlay (dialog, drawer, popover) | 200 to 300ms |
| Section or page reveal | 300 to 500ms, once per screen at most |

- Entering or responding: ease-out. Exiting: ease-in, at about 60 to 75 percent of the enter duration.
- Moving between two on-screen states: ease-in-out.
- Linear only for progress and continuous loops.

These durations are heuristics from common practice, not a standard. Keep them as tokens and tune them on the real screens.

## Material Motion mapping

Material Design 3 publishes easing and duration tokens for the same ground the tier table above covers. The mapping extends the table above; nothing here overrides the table above. One currency note: in the M3 expressive update (May 2025) Material introduced a spring-based motion physics system that "is replacing the previous system based on easing and duration"; the easing-and-duration system "is still used for transitions and can be used by teams that haven't yet updated to GM3 Expressive, but is no longer maintained", and the M3 transition patterns themselves "use the legacy easing and duration system". This mapping targets the easing-and-duration system, because it is the one that compiles to CSS `cubic-bezier` tokens.

M3 duration tokens, verbatim from the spec: short 50/100/150/200ms, medium 250/300/350/400ms, long 450/500/550/600ms, extra-long 700/800/900/1000ms (`md.sys.motion.duration.short1` through `extra-long4`).

| Plugin tier | Plugin duration | M3 band and tokens | M3 reference values |
|---|---|---|---|
| Hover, press, toggle | 100 to 150ms | Short (50 to 200ms): short2, short3 | "Selection controls have a short duration of 200ms with Standard easing" |
| State change (expand, tab switch) | 150 to 250ms | Short 200ms to medium 250ms: short4, medium1 | Medium band: "transitions that traverse a medium area of the screen" |
| Overlay (dialog, drawer, popover) | 200 to 300ms | Short 200ms to medium 300ms: short4, medium1, medium2 | M3 suggested pairs: Standard 300ms "begin and end on screen", Standard decelerate 250ms enter, Standard accelerate 200ms exit |
| Section or page reveal | 300 to 500ms | Medium 350/400ms to long (450 to 600ms): medium3, medium4, long2 | "A Card expanding to full screen uses a long 500ms duration with Emphasized easing" |

The plugin bands sit inside M3's, trimmed at both ends. M3's short band reaches down to 50ms; the plugin keeps a 100ms floor because faster feedback reads as no feedback (see the frequency gate above). M3's long band reaches 600ms and its extra-long band covers "ambient transitions that don't involve user input"; the plugin's ceiling stays 500ms because everything in the tier table is user-initiated. M3's suggested default for a begin-and-end-on-screen transition (Standard, 300ms) lands between the plugin's state-change and overlay tiers — the pairs are a cross-check, not an override.

On easing, the plugin's `--ease-out` cubic-bezier(0.2, 0, 0, 1) is exactly M3's `md.sys.motion.easing.standard` (CSS `cubic-bezier(0.2, 0.0, 0, 1.0)`). The plugin's `--ease-in` cubic-bezier(0.4, 0, 1, 1) is M2's accelerated easing (`cubic-bezier(0.4, 0.0, 1, 1)`); M3's standard-accelerate is `cubic-bezier(0.3, 0, 1, 1)`, a slightly softer takeoff.

M3's headline curve, `md.sys.motion.easing.emphasized`, is a two-curve composite with no single CSS value: the spec's CSS row reads "N/A (Use Standard as a fallback)", and the guidance says "The Standard set is also a fallback for platforms that don't support Emphasized easing, like iOS and Web." On the web, the plugin's single `--ease-out` is what M3 itself prescribes. Where M3's emphasized set applies:

| M3 token | CSS value | M3 role and suggested pair | Plugin mapping |
|---|---|---|---|
| easing.emphasized | N/A (composite; "Use Standard as a fallback") | Begin and end on screen, 500ms | `--ease-out` |
| easing.emphasized.decelerate | cubic-bezier(0.05, 0.7, 0.1, 1.0) | Enter the screen, 400ms | `--ease-out` (standard fallback) |
| easing.emphasized.accelerate | cubic-bezier(0.3, 0.0, 0.8, 0.15) | Exit the screen, 200ms | `--ease-in` (same role) |

M3's duration logic matches the plugin's. "Transitions that exit, dismiss, or collapse an element use shorter durations. Exit transitions are faster because they require less attention than the user's next task" — M3's suggested enter/exit pairs (400ms/200ms, 250ms/200ms) agree with the plugin's rule that exits run at 60 to 75 percent of the enter duration, without being its source. And "Transitions that cover small areas of the screen have short durations. Those that traverse large areas have long durations." The spring system scales speed by element size the same way ("smaller elements may use fast and larger elements may use slow").

### Stagger

Material publishes no stagger milliseconds. The rendered text of M3's tokens-specs, applying-easing-and-duration, transition-patterns and applying-transitions pages, and M2's speed, choreography and understanding-motion pages, contains no stagger values at all. M3's sequencing guidance is directional only: "Elements are grouped and move along a primary axis instead of moving in independent directions", and its transition checklist warns against animating "many persistent elements independently". The plugin's 30 to 50ms per sibling, 300 to 400ms in total, stays a plugin heuristic: the 300 to 400ms total is consistent with M3's medium band (250 to 400ms) as the reveal window, but the per-item numbers are not attributable to Material. The stagger figures in `data/motion.csv` (30 to 80ms per item) are vendored GSAP practice, not Material guidance (see `data/PROVENANCE.md`).

### What this mapping deliberately does not adopt

- The M3 Expressive motion physics system (springs): overshooting spatial springs, expressive and standard schemes, fast/default/slow speeds. It is Material's current system, but it is platform-specific — "Available" on Jetpack Compose, "Available. Not added to components" on Android Views, "Unavailable" on Flutter, and on Web only "Compatible with Compose springs" — and CSS transitions have no spring primitive. A duration-token model needs curves that compile to `cubic-bezier`, which is the system mapped above.
- Emphasized easing as a required default. M3 recommends it "for most transitions", but marks its CSS value "N/A (Use Standard as a fallback)". Keeping one curve pair, per the table above, wins on consistency.
- Platform-default navigation transitions (Android's fade-while-slide, iOS's parallax push). Web and desktop WebView products do not carry those platform defaults; the page-reveal tier covers the need.
- Extra-long durations (700 to 1000ms). M3 scopes them to ambient, non-user-initiated transitions, which the frequency gate above already excludes.

## What to animate

- Animate transform and opacity. Avoid width, height, top, left, margin and padding, which force layout on every frame.
- For expanding content, prefer the `grid-template-rows` from `0fr` to `1fr` transition over animating `max-height`.
- Stagger siblings by 30 to 50ms, to 300 to 400ms in total, and only in one place per screen.
- Hover changes color, background or border. A lift plus a shadow on every card is a generic tell.
- An interaction in progress must be interruptible: a new click reverses or redirects the transition.

## Reduced motion and flashing

- Honour `prefers-reduced-motion: reduce`. Remove decorative transforms and parallax. Keep state changes, using an instant change or a short opacity fade.
- Progress indicators convey status, so keep them, but make them steady rather than pulsing.
- Never flash content more than three times per second (WCAG 2.3.1). Prefer no blinking indicators at all.
- Live data updates change content, not motion.

```css
:root {
  --dur-micro: 120ms;
  --dur-state: 180ms;
  --dur-overlay: 240ms;
  --ease-out: cubic-bezier(0.2, 0, 0, 1);
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --dur-micro: 0ms;
    --dur-state: 0ms;
    --dur-overlay: 0ms;
  }
  .panel-enter { transform: none; }
}
```

## Loading feedback

- Skeletons for shapes the layout already knows, such as a table with its header.
- A spinner with a label when the duration is unknown.
- Delay the indicator 200 to 300ms, so fast responses do not flicker.
- Progress bars show a number when the total is known.
- Never leave a blank panel.
