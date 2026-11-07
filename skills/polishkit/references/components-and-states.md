# Components, states and copy

## State matrix

Every interactive component needs these states designed, not just the default:

- default, hover, focus-visible, pressed, selected or checked
- disabled, with the reason available (tooltip or helper text)
- loading, in place (the control shows its own progress)
- error, inline, next to the field or action it concerns
- success, a brief confirmation that names what changed

Every container needs these:

- empty: what is missing, why it matters, and one next action
- partial: some data loaded, some failed or is still loading
- unavailable or offline, with the last known state and a retry
- permission denied, with the path to resolve it
- long-running: progress, elapsed time, and a way to cancel when cancelling is safe

Use `scripts/slop_scan.py` and the break test below to find the missing ones.

## Copy

- Sentence case. Plain verbs on buttons. No exclamation marks.
- Name an action the same way everywhere: the button "Save changes", the result "Changes saved", the menu item "Save changes".
- Errors say what happened, why if it is known, and what to do. "Use a number between 1 and 65535." beats "Invalid port." beats "Oops, something went wrong."
- Empty states invite the next action. "No models yet. Add a model folder to start." beats an illustration with no words.
- Use one term for one thing across the whole app. Do not alternate "model", "instance" and "server" for the same object.
- Plan for translation growth. Allow 30 to 40 percent more width for labels that translate to longer strings, and check the bilingual screens for both languages.

## Break test (worst-case data)

Run every screen with data that breaks it. Do this before calling the work finished:

- an identifier of 200 characters with no spaces
- a path of 300 characters
- empty strings, missing optional fields, and `null` where a value is expected
- lists with 0, 1 and 10,000 items
- a number with 10 digits and a token count of 999999999
- CJK text, RTL text, and the longest translation
- a backend error message with a stack trace
- a slow response, and a response that never arrives

Pass means: nothing overflows its container, truncated values show their full text on focus or hover, the layout does not jump, and the primary action stays reachable.

## Components

- Buttons: one primary action per region. Icon-only buttons need a tooltip and an accessible name. Hit area at least 24px on desktop (32px is comfortable), 44px for touch (NN/g's researched physical floor for touch targets is 1cm × 1cm, nngroup.com/articles/touch-target-size).
- Inputs: a visible label, not a placeholder alone. Helper text under the field. Errors with an icon and text, linked with `aria-describedby` and marked with `aria-invalid`. Autofocus only when it is the obvious first action.
- Tables and lists: sticky header, sortable headers announced to assistive technology, constant row height, numeric columns right-aligned with tabular numerals, a visible selected state, and arrow-key navigation. Virtualize above a few hundred rows.
- Logs: monospace, fixed line height, a wrap toggle, filter with match counts, copy a line or the whole buffer, and auto-scroll that stops when the user scrolls up. Cap the buffer by lines and by bytes.
- Dialogs: focus is trapped inside, Escape closes, and focus returns to the element that opened the dialog. The title names the action. Do not use a dialog for content that deserves a pane.
- Menus and popovers: arrow keys move through items, Escape closes, and the anchor stays highlighted while open.
- Tabs: one tab stop for the group, arrow keys move between tabs, and each panel is labelled by its tab.
- Tooltips: appear on hover and on focus after 400 to 600ms, dismiss on Escape, and never hold essential information.
- Toasts: for non-blocking results only, shown 4 to 6 seconds, one per event. A reversible action gets an Undo for 5 to 10 seconds. Errors that need action go inline, not into a toast.
- Icons: one family. 16px in dense UI, 20px by default, 24px for hero use. Stroke weight matched to the text beside it. Never use emoji as a control's icon.
- Cards: only for objects a person acts on. Not for every piece of text.

## Destructive and reversible actions

- Destructive actions confirm, and the confirmation names the object: "Delete model Qwen3-8B? Its files stay on disk." Use the danger color for the confirm button only.
- Reversible actions skip the confirmation and offer Undo instead.

## Keyboard and focus

- Every action is reachable by keyboard, in an order that matches the visual order.
- Focus is always visible. The focus indicator must differ from hover, typically a 2px ring offset from the element, with at least 3:1 contrast.
- Shortcuts are shown next to the action they trigger, using the platform modifier.
- No hover-only actions. Anything revealed on hover must also be reachable by focus and by touch.

## Primitive behaviors (from Radix)

Interaction contracts extracted from the Radix Primitives documentation, radix-ui.com/primitives/docs (components dialog, dropdown-menu, tabs, tooltip, toast; fetched 2026-11-07). Radix implements these so the WAI-ARIA patterns hold; role and ARIA-attribute details defer to the APG source. Where Radix's own defaults differ from the heuristics above (tooltip delay), the local heuristic stays the default here and the Radix number is recorded for comparison.

- Dialog (radix-ui.com/primitives/docs/components/dialog): focus is trapped while the dialog is modal (the default); Escape closes and focus returns to the trigger; Tab and Shift+Tab move within the dialog. The open and close focus moves are interceptable events (`onOpenAutoFocus`, `onCloseAutoFocus` with `preventDefault`), as are Escape and outside interaction (`onEscapeKeyDown`, `onPointerDownOutside`, `onInteractOutside`). The title is announced on open — hide it with VisuallyHidden rather than omitting it — and dropping the description means passing `aria-describedby={undefined}` explicitly.
- Dropdown menu (radix-ui.com/primitives/docs/components/dropdown-menu): focus moves among items by roving tabindex, not one tab stop per item. ArrowDown and ArrowUp move focus, Enter or Space activates; ArrowDown from the trigger opens and focuses the first item. Escape closes and returns focus to the trigger. ArrowRight and ArrowLeft open or close submenus according to reading direction. Arrow-key looping is opt-in (`loop`, default false). Highlight is exposed to CSS as `[data-highlighted]`, state as `[data-state]`.
- Tabs (radix-ui.com/primitives/docs/components/tabs): one tab stop for the group — Tab focuses the active trigger, Tab again moves to the content. Arrow keys move focus and activate per `orientation`; Home and End jump to the first and last trigger and activate. Activation is automatic by default (`activationMode="automatic"`): moving focus switches the panel. Focus wraps by default (`loop` on the list, default true).
- Tooltip (radix-ui.com/primitives/docs/components/tooltip): opens on hover or on focus. Radix's default delay is 700ms (`delayDuration`), with 300ms (`skipDelayDuration`) before consecutive tooltips skip the wait; keyboard focus opens without delay, and Escape, Enter, Space or activating the trigger closes it instantly. The local default above (400 to 600ms) stays; Radix's 700ms is the comparison point.
- Toast (radix-ui.com/primitives/docs/components/toast): default duration 5000ms, paused on hover, focus and window blur; Escape closes when focus is on the toast; a swipe dismisses (default direction right, threshold 50px). F8 focuses the toast viewport, and making that hotkey discoverable is the author's job. Foreground toasts are announced immediately, background ones at the next graceful opportunity. An action button requires `altText` naming a permanent alternative path, and a toast "should not be held open to acquire a user response" — that is a dialog, styled however you like.
