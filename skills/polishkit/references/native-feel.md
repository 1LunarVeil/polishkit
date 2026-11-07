# Native feel (平台质感)

Scope: an app window on macOS or Windows, whatever the framework underneath — Tauri, Electron, WebView2 or native. The numbers here are platform units (Apple `pt`, Microsoft `epx`), not CSS px; they never belong in `page_audit`'s WCAG script. Sources: Apple HIG and Microsoft Learn, fetched per `notes/batch-PLATFORM/`; the core numbers were first extracted in `notes/batch-A/hig.md` and `notes/batch-A/fluent.md`, which deferred them to this file.

## 何时用哪套 (which system when)

- The platform the WINDOW runs on wins over the framework. A WebView app on macOS is a macOS app: traffic lights, ⌘ shortcuts, system font. The same shell on Windows follows Fluent. A web app inside a browser tab follows web conventions — this file does not apply there.
- Users read conventions, not code. Framework defaults (browser-styled buttons, Ctrl where ⌘ belongs) read as foreign in a window shell.
- Pick one platform per window and commit. Mixing chrome from both (macOS traffic lights over a Fluent Mica backdrop, in one window) is a tell, not a synthesis.
- `design_lookup` gets a platform dimension only in 2.0 code work — recorded as deferred, not implemented here.

## macOS 清单 (macOS checklist)

- Window chrome: the frame carries the window controls — close, minimize, zoom — above the body (HIG "Windows", macOS anatomy). Keep the leading region of the title bar clear for them; a custom toolbar or drag region must never put interactive content under the controls. Key windows show colored controls; inactive windows gray them and drop vibrancy — a custom title bar must reproduce all three window states (main/key/inactive) or use the system's.
- Menu bar: App, File, Edit, Format, View, app-specific, Window, Help — in that order, Apple menu leading. Keep standard menus visible and disable inapplicable items instead of hiding them. App-level settings go in the App menu (Settings…, ⌘,), not a gear button.
- Keyboard (HIG "Keyboards", standard shortcuts): ⌘C/⌘V/⌘X/⌘A, ⌘Z/⇧⌘Z, ⌘N/O/S/P, ⌘Q quit, ⌘W close window, ⌘F find, ⌘, settings, ⌘? help, Esc cancel, ⌘` next window. Do not repurpose them for custom actions.
- Type: system font SF (SF Pro for UI; New York for serif), via the system text styles rather than embedded fonts. Default 13pt, minimum 10pt on macOS; prefer Regular, Medium, Semibold, Bold — no Light weights (HIG "Typography").
- Materials: macOS gives standard materials plus vibrant versions of all system colors, in two blending modes — behind window and within window (HIG "Materials", macOS section). On iOS the same system defines four thicknesses (ultraThin/thin/regular/thick) and vibrancy levels for labels (default/secondary/tertiary/quaternary) and fills (default/secondary/tertiary); quaternary labels are too low-contrast on the thin materials.
- Liquid Glass: two variants — regular (blurs and adjusts luminosity to stay legible) and clear (translucent, for media-rich backgrounds; add a dark dimming layer of about 35% opacity over bright content). It belongs to controls and navigation, not the content layer (HIG "Materials").
- Controls (batch A numbers): default 28×28pt, minimum 20×20pt on macOS. Button hit region at least 44×44pt generally (60×60pt in visionOS). Push buttons opening another window, view or app take a trailing ellipsis. Contrast floors in HIG "Accessibility" mirror WCAG AA (4.5:1 normal, 3:1 at 18pt or bold) — which is why `page_audit` can serve both platforms.
- Correction to batch A: the Mini 28 / Small 32 / Regular 44 / Large 52 / XL 64 pt button ladder is visionOS's table, not macOS's — see `notes/batch-PLATFORM/hig.md`.

## Windows 清单 (Windows checklist)

- Mica (Learn "Mica material"): opaque, dynamic, incorporates theme and desktop wallpaper; samples the wallpaper once; for the app backdrop — the base layer of long-lived windows. Mica Alt is the stronger-tinted variant for tabbed title bars. Recommended structure: Mica base layer, one content layer above it using `LayerFillColorDefaultBrush` (a low-opacity solid). Mica falls back to a solid color when the window is inactive, when transparency is off, in Battery Saver, on low-end hardware, and to the user's colors in High Contrast mode.
- Acrylic (Learn "Acrylic material"): background acrylic is for transient UI only — context menus, flyouts, non-modal popups, light-dismiss panes; in-app acrylic is for supporting surfaces inside the frame, such as panes that overlap scrolling content. Recipe: background, blur, exclusion blend, color tint, noise. Never stack multiple acrylic surfaces, never place two edge-to-edge (striping), and no accent-colored text on acrylic — Learn states it fails contrast at the default 14px. Same solid fallbacks as Mica; background acrylic additionally goes solid when the window deactivates or runs on Xbox/HoloLens/tablet.
- Type ramp (Learn "Typography"; batch A record): Caption 12/16, Body 14/20, Body Strong 14/20 Semibold, Body Large 18/24, Subtitle 20/28, Title 28/36, Title Large 40/52, Display 68/92 — epx as size/line-height. Floors, verbatim from Learn: "14px Semibold, 12px Regular — text smaller than these sizes and weights are illegible in some languages". Measure 50–60 characters per line; never below 20 or above 60. Sentence case for all UI text including titles; use Semibold, not Bold; no italics.
- Geometry (Learn "Rounded corners"): 8px radius on top-level containers — app windows, dialogs, flyouts; 4px on in-page elements — buttons, list backplates, TextBox, CheckBox; bars (ProgressBar, ScrollBar, Slider) 4px; ToolTip is the exception at 4px. Resources: `ControlCornerRadius` 4px, `OverlayCornerRadius` 8px; Win32 windows opt in via the DWM API.
- Controls: standard text-control minimum height 32px, list rows 40px, dialog buttons 32px (WinUI `generic.xaml`); compact density drops text controls to 24px and rows to 32px (`Compact.xaml`) — exactly two density levels exist, no arbitrary values. Command buttons: minimum width 120px, maximum label 26 characters (Learn "Button"). Target size stays the WCAG 24 CSS px floor here; the HIG's 44×44pt does not carry over.
- Elevation (Learn "Layering and elevation"): shadow plus a 1px contour. Values: Window 128, Dialog 128, Flyout 32, Tooltip 16, Card 8, Control 2, Layer 1; intensity shifts with the theme.
- Navigation: `NavigationView` for left navigation, `CommandBar` for commands, command palette (Ctrl+K) once the app has enough actions. Accelerator hints show Ctrl, never ⌘.
- Theme: default to the user's Windows light/dark setting. Within a theme, darker surfaces mark less important background layers and brighter surfaces mark important ones; accent color is sparse and contrast-optimized per mode (Learn "Color").

## 平台 tells (what breaks native feel)

- Any platform: browser-styled components inside a window shell; both platforms' chrome blended in one window; a hand-drawn title bar that ignores the OS controls.
- macOS: Ctrl where ⌘ belongs (Ctrl+C is a web-ism on a Mac); a hamburger menu or bottom tab bar; an in-window settings screen instead of App menu → Settings…; hand-drawn red/yellow/green dots with wrong spacing or no grayed inactive state; a title-bar area that cannot drag the window; applying iOS-only material names to macOS chrome.
- Windows: ⌘ glyphs in shortcut hints; square corners everywhere or 8px radius on in-page controls (that is the overlay value — controls take 4px); italic or Bold where Fluent wants regular and Semibold; ALL-CAPS headings against sentence case; a hand-painted wallpaper tint behind content instead of the system Mica backdrop, which silently breaks every fallback (inactive, transparency off, Battery Saver, High Contrast); a light/dark toggle that ignores the system setting.

## 测试要点 (break test additions)

- macOS: switch focus to another app — controls must gray out and vibrancy must drop; ⌘W, ⌘Q, ⌘, and ⌘` do what the menu says; resize to minimum width — no control or toolbar item may land under the window controls; the menu bar order matches the standard list.
- Windows: follow the system theme toggle both ways; force the fallbacks (transparency off, window inactive) — surfaces go solid and stay legible; check 8px vs 4px radii landed on the right layer; shortcut hints read Ctrl; if compact density is used, it applies to a whole panel, not scattered controls.
- Both: type floors hold — macOS body never below 10pt (13pt default), Fluent never below 12px Regular / 14px Semibold; pick the measure convention per platform (50–60 for Fluent, 45–75 for web text) and do not mix them in one surface; then run the usual states, dark theme and scaling passes from `desktop-app.md`.

## 刻意不采用 (deliberately rejected)

- Liquid Glass recipes for custom controls: the HIG gives qualitative rules only, system components adopt the material automatically, and hand-replicating it reads as a tell. Only the variant/dimming/layer-placement rules above are recorded.
- Cross-platform hit-target harmonization: the HIG 44×44pt stays a macOS expectation; importing it into the WCAG script would double-standard against 24 CSS px (`notes/batch-A/hig.md` deferred it for exactly this reason).
- visionOS/watchOS/iOS platform tables (button size ladder, 17pt iOS default): wrong platform for a desktop shell.
- fluent2.microsoft.design as a numeric source: the site publishes no numbers (batch A verified page by page); Microsoft Learn and the WinUI resources are the citable implementation of Fluent 2.
- Segoe UI Variable axis details (wght/opsz): no script-checkable item (batch A).
- Sources: new fetches are listed in `notes/batch-PLATFORM/hig.md` and `notes/batch-PLATFORM/fluent.md`; batch A's extraction record covers the pages this file reuses numbers from.
