# Visual review: render, look, change, look again

Code review approves what a rule can see. It cannot see that a page renders as a bare shell at 1440px, that content stops two thirds down the window, or that a transition lands mid-frame. Those need a picture. This step is not optional decoration: it is the only part of the review that catches layout, density and real rendering.

## 1. Get the app into a renderable state

Pick the cheapest path that reaches the real UI.

1. The app is already running. Use its URL and skip to step 2.
2. Only the frontend is needed. Serve the built frontend statically on loopback. If the UI talks to a backend, most apps still render their shell and empty states without one, which is enough to review layout and density.
3. The UI is a desktop window. Capture the window itself. On Windows use the OS screenshot path; do not add a browser dependency for a native window.

Do not describe a design as reviewed when none of these ran. Say "not visually verified" and stop.

## 2. Capture with a readiness signal

```
python scripts/visual_capture.py http://127.0.0.1:5173 --out shots --matrix
python scripts/visual_capture.py http://127.0.0.1:5173 --out shots --dark --full-page --hover "button.primary"
```

The tool finds a Chromium-family browser by absolute path only, then for each view shoots repeatedly until two consecutive frames are identical. It prints JSON with each file, its colour count, whether it settled, and any console errors. When a browser exists the capture runs over CDP with one persistent browser for the whole plan: `--dark` then really emulates `prefers-color-scheme` (the light and dark frames of the same view come out different, which is the proof), `--full-page` shoots past the fold, `--element`, `--hover` and `--focus` reach interaction states. Any CDP failure falls back to the legacy per-view engine and the JSON states it (`engine: "screenshot"`, `cdp_error`); the fallback cannot reach the interaction views, so a claim about them must say so.

Why it works this way, from a real session:

- A fixed 4s wait captured a half-rendered shell at one window size while a longer wait captured the same page complete. Never trust a single shot or a fixed delay.
- The shell had 204 distinct colours and a full render had 837 to 1143. The blank test is colour count, not file size: the shell was a 12 KB file, comfortably "non-empty". Dark themes legitimately produce fewer shades, so the dark threshold is lower; a toy page can still trip the heuristic, which is why `blank` marks a suspect shot and not a verdict.
- A 390px viewport needed three attempts to settle. Report `settled: false` when it never does, and look at that shot with suspicion.

If no browser is found, the tool exits 2 and says so. That is the honest outcome; do not substitute a guess.

## 3. Read the pictures

Look at each capture. Check what code cannot show:

- Does the first screen match the job? Is the primary action obvious without reading everything?
- Is the content distributed for the window, or piled top-left with dead space below?
- At the narrow size, does anything clip, overlap, or fall below the fold that matters?
- At 150% scale, does dense text still fit its row?
- Do the empty and loading states look like states, or like a broken page?

Console errors count as failures, as does a `blank` or unsettled capture.

## 4. Change, then prove the change

After editing, capture again to the same paths and compare:

```
python scripts/image_diff.py shots/wide-1440x900-light@1.png shots2/wide-1440x900-light@1.png
```

It reports the changed pixel count, ratio and bounding box. Use it to check your own claim: if you said a section moved, the box should cover that section. If the diff is empty, the change did not reach the render, and that is a finding about the change, not about the image.

Two limits to respect:

- It is not a regression gate. A redesign may change every pixel on purpose. The tool never fails a build for being different.
- Only non-interlaced 8-bit PNG is decoded. Anything else is reported as unsupported rather than compared badly.

## 5. States worth capturing

Capture these when they exist. Skip any that need unavailable data, and say which you skipped.

| State | Why it matters |
|---|---|
| default | the primary judgement |
| empty | the most common first impression for a new user |
| loading | reveals layout shift and skeletons that do not match |
| error | copy quality and whether recovery is offered |
| narrow window | clipping, overflow, collapsed navigation |
| 150% scale | text fitting, touch targets, row height |
| dark theme | the second theme usually gets no review; `--dark` emulates it for real |
| hover and focus states | where the cursor and keyboard actually land (`--hover`, `--focus`) |
| full page | what lives below the fold (`--full-page`) |

## Report format

Add a Visual section to the review:

```
Visual (captured at 1440x900, 1100x720, 390x844; 150% scale)
- wide: content occupies the top two thirds; 300px of dead space below the fold [blocking]
- narrow: the toolbar wraps onto two lines, pushing the primary action below the fold [important]
- writer console: no errors
- not captured: error and loading states (backend not running)
```

Every claim in that section must point at a capture you looked at. Every state you skipped must be named.
