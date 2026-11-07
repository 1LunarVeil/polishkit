# Desktop and WebView apps

Use this file when the UI is an application window, not a website: a Tauri, Electron or WebView2 shell, or a native desktop tool. Most rules still apply from the other references; this file adds what changes when the interface lives in a window. Per-platform specifics — macOS traffic lights, menu bar and ⌘ keys, Fluent Mica/Acrylic, the type ramp and control metrics — extend it in `native-feel.md`.

## Think window, not page

- Fixed chrome (title bar, toolbar, sidebar, status bar) and scrolling panes. Scroll inside panes, never the whole window behind a sticky mega-header.
- Set a minimum window size and collapse gracefully below it. Test the collapse.
- Splitters and resize handles need a keyboard path.
- Do not make the window look like a browser tab with a fake address bar.

## Pointer first, keyboard always

- Mouse is the main input, so controls can be 24 to 32px. Rows of 28 to 32px suit lists and tables.
- Every action is reachable from the keyboard. Show shortcuts in menus and tooltips with the platform modifier: Ctrl on Windows, ⌘ on macOS — the expected mappings (⌘C/V/W/Q/…) are listed in `native-feel.md`.
- A command palette (Ctrl+K) pays off once an app has more than a few dozen actions.
- Escape closes overlays. Tab order follows the visual layout. Focus is restored after a dialog closes.
- Context menus (Shift+F10 and the menu key) should exist wherever right-click does.

## Chrome

- A custom title bar needs drag regions and window controls with their own hover and focus states.
- Keep platform conventions the user already knows: standard window controls, system menus where the platform expects them, and no in-app hamburger menu on desktop.
- Do not invent a new window shape. Match the system's corner and shadow behaviour unless the brief asks otherwise. The per-platform numbers (Win11's 8px window / 4px control radii, the macOS window states, the traffic-light region) are in `native-feel.md`.

## Theme and system settings

- Follow the OS light or dark setting by default, with a manual override. On Windows the theme is the user's system preference and Fluent's surface hierarchy (darker = less important) plus the Mica/Acrylic fallback behaviour apply — see `native-feel.md`.
- Respect forced colors (`@media (forced-colors: active)`). Use system colors in that mode: `CanvasText`, `Canvas`, `Highlight`, `ButtonText`, `ButtonFace`, `GrayText`. Focus and borders must remain visible.
- Respect the reduced-motion setting, which Windows exposes as the animation toggle.

## Scaling and fonts

- Use `rem` for type and spacing so text scales with the user's settings. Use px for hairlines only.
- Test at 100%, 125% and 150% display scaling. Check that nothing clips and that dense rows still fit their text.
- Use the system font stacks from `color-and-type.md`, with the CJK fallbacks. A bundled font is fine when it is licensed, woff2, and actually loads.
- If the app's content security policy blocks external font or image hosts, nothing from a CDN will load. Design the fallback deliberately and verify the packaged build, not only the dev server.

## Density and panels

- A typical app layout: a sidebar of 200 to 260px, a toolbar of about 40px, panes with their own scroll, and a status bar of about 24px carrying live facts (running count, port, memory).
- Judge density by how much is visible without scrolling. Pro tools earn density; reading views earn room.
- Lists of logs, models or sessions use compact rows, sortable headers and keyboard selection.

## Text that people copy

- Logs, IDs, paths and error messages must be selectable and copyable.
- Show the full value somewhere: a tooltip, an expand control or a detail pane. Truncation without access to the full text loses information.
- Long lines: wrap, or scroll horizontally with a visible scrollbar. Never clip silently.

## First run and empty states

- The first run gets one clear path: choose the model folder, add the first model, start the server. Do not show an empty dashboard with six competing calls to action.
- Empty states name the missing thing and offer the single next action.

## Notifications and motion

- Use native notifications for events the user may not be watching for, such as a finished long task. Use in-app toasts for confirmations.
- Keep motion under 150ms in dense views. Live data updates change content only.

## Desktop anti-patterns

- Landing-page structure inside an app: a hero section, a feature grid, a footer.
- Hover-only actions and tooltips that hold the only copy of a label.
- Bottom tab bars and hamburger menus, which are mobile patterns.
- Modal dialogs for content that should live in a pane, such as settings with many sections.
- Giant rounded cards around every list item.
- Full-window scroll with a sticky header that eats a third of the screen.
