"""Audit keyboard interaction and focus on a live page over CDP.

Usage:
  python keyboard_audit.py URL [--json] [--allow-private] [--measure N]
                               [--max-steps N] [--width W] [--height H]

page_audit.py measures the page as it first renders. This tool measures the
page a keyboard user actually navigates: it dispatches real Tab presses, then
screenshots what each stop looks like focused versus unfocused. That closes the
plugin's largest self-contradiction — it taught focus and keyboard rules it
never checked.

Every result lands in the same three buckets page_audit uses (measurable
pass/FAIL, uncertain, review), and nothing is silently guessed.

Keyboard reachability (2.1.1, A):
- UNREACHABLE  a control that looks interactive (native control or an
               interactive ARIA role) never entered the Tab walk and is not
               disabled. Measurable FAIL.
- TRAP         the walk cycles inside a strict subset of the page's tabbables.
               Inside a dialog/menu the cycle is expected (review); elsewhere
               it is a FAIL.
- TABINDEX     a positive tabindex reorders the page away from the DOM. Review:
               the order risk is real, the author's intent is unknowable.
- ORDER        the walk climbs back up the page more than once. Review, with
               the jump sites attached as evidence.
- ACTIVATION   a custom ARIA widget took focus but neither Enter nor Space
               produced a click or a DOM mutation. Review (focusable is not the
               same as operable).

Focus visibility (2.4.7 AA, 1.4.11 AA; 2.4.13 AAA reported separately):
- indicator measurement is pixel evidence, not computed style. Chrome reports
  `outline: auto` as "1px" whatever it draws, and pseudo-element rings and
  box-shadow rings exist only in the composited frame.
- NO-FOCUS      the focused and unfocused crops are identical: no indicator.
                FAIL.
- LOW-CONTRAST  pixels changed, but the strongest change is under 3:1, or the
                indicator's contrast against the surface it sits on is under
                3:1. FAIL.
- 2.4.13 (AAA)  never gates the exit code: the qualifying indicator area
                compared with the 4h+4w two-pixel perimeter, and the same-pixel
                contrast between states (median and minimum reported).

Contrast in transient states (1.4.3):
- STATE-CONTRAST  the element's own text pair measured in the focused and hovered
                  states, composited the way page_audit composites the resting
                  state. A pair that passes at rest and fails on hover is the
                  usual regression; measurable FAIL.

Focus obscured (2.4.11 AA):
- OBSCURED  every sampled point inside the focused element's border box hit-tests
            to author content that is neither the element nor an ancestor or
            descendant. The criterion says "entirely hidden", so a partly
            visible control passes.

Measurement honesty: when the page restores focus after blur(), the "unfocused"
frame is not one, so that stop is reported uncertain instead of verdicted. A
blur the audit performs itself is restored with focus({preventScroll:true}),
which was verified to preserve both :focus-visible and the Tab chain.

Exit status: 0 no measurable failures, 1 at least one FAIL, 2 no browser or
browser/CDP failure ({"verified": false} — the tool claims nothing about the
page), 3 URL rejected (visual_capture.validate_url).

Read-only: prints a report and writes nothing. stdlib only; CDP on loopback.
"""

import argparse
import base64
import json
import shutil
import sys
import time

sys.dont_write_bytecode = True
import cdp  # noqa: E402  (sibling module; no third-party dependencies)
import image_diff  # noqa: E402
import visual_capture  # noqa: E402
import wcag  # noqa: E402

MAX_STEPS = 120        # a dense page (57 stops was one real dashboard) needs headroom
MEASURE_STOPS = 12
LOAD_TIMEOUT = 10.0
CLIP_MARGIN = 18        # CSS px of surrounding surface kept around each element
DIFF_TOLERANCE = 2      # per-channel: absorbs compositor noise, not a real ring
SETTLE_ATTEMPTS = 4     # frames shot per state before accepting the last one
SETTLE_INTERVAL = 0.12  # seconds between settle attempts
FOCUS_FLOOR = wcag.AA_LARGE_OR_UI  # 3:1 for focus indicators (1.4.11)
INDICATOR_THICKNESS = 2  # 2.4.13's reference perimeter thickness, in CSS px
ACTIVATION_LIMIT = 8
LARGE_SIZE = 24.0
LARGE_BOLD_SIZE = 18.66
BOLD_WEIGHT = 700

CLAUSE_COVERAGE = (
    "WCAG 2.1.1 keyboard reachability; 2.4.3 focus order (positive tabindex, "
    "reading-order deviation); 2.4.7 focus visible; 2.4.11 focus not obscured "
    "(minimum); 1.4.11 focus indicator contrast; 1.4.3 contrast re-checked in "
    "focused and hovered states; 2.4.13 focus appearance (AAA, supplementary)"
)

# Injected once. Everything DOM-side lives here; the walk itself is driven from
# Python with real Input.dispatchKeyEvent presses so :focus-visible, scroll
# anchoring and in-page focus management behave exactly as for a keyboard user.
PRELUDE_JS = r"""(function () {
  if (window.__pk) return "already";
  var NATIVE = "a[href],area[href],button,input,select,textarea,summary,iframe";
  var pk = {};
  window.__pk = pk;
  window.__pkClicks = 0;
  window.__pkMutations = 0;

  // Element identity: a WeakMap counter. Tag names are for display only -
  // two unnamed <button>s must not be mistaken for one another.
  pk.ids = new WeakMap();
  pk.byId = {};
  pk.next = 0;
  pk.idOf = function (el) {
    var known = pk.ids.get(el);
    if (known === undefined) {
      known = ++pk.next;
      pk.ids.set(el, known);
      pk.byId[known] = el;
    }
    return known;
  };
  pk.of = function (id) { return pk.byId[id] || null; };

  function isVisible(el) {
    if (!el || el.nodeType !== 1) return false;
    var cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || cs.visibility === "collapse") return false;
    if (parseFloat(cs.opacity) === 0) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  pk.isVisible = isVisible;

  pk.tabbables = function () {
    var all = document.querySelectorAll(NATIVE + ",[tabindex],*[contenteditable=true]");
    var out = [];
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      var ti = el.getAttribute("tabindex");
      var negative = ti !== null && parseInt(ti, 10) < 0;
      var naturally = el.matches(NATIVE) && !negative;
      var opted = ti !== null && !negative;
      if (!naturally && !opted) continue;
      if (el.disabled) continue;
      if (el.getAttribute("aria-hidden") === "true") continue;
      if (!isVisible(el)) continue;
      out.push(el);
    }
    return out;
  };

  function label(el) {
    var cls = typeof el.className === "string" ? el.className.trim().split(/\s+/)[0] : "";
    if (el.id) return el.tagName.toLowerCase() + "#" + el.id;
    if (cls) return el.tagName.toLowerCase() + "." + cls;
    // Unnamed elements still need to be distinguishable in a sequence report:
    // a page of five identical <button> tags hides which one is broken.
    var text = (el.innerText || el.value || el.getAttribute("aria-label") || "")
      .replace(/\s+/g, " ").trim();
    return el.tagName.toLowerCase() + (text ? '["' + text.slice(0, 18) + '"]' : "");
  }

  pk.describe = function (el) {
    if (!el || el.nodeType !== 1) return { id: 0, tag: "(none)" };
    var r = el.getBoundingClientRect();
    var text = (el.innerText || el.value || el.getAttribute("aria-label") ||
                el.getAttribute("placeholder") || "").replace(/\s+/g, " ").trim();
    var dialog = el.closest("[role=dialog],[role=alertdialog],[role=menu],[aria-modal=true],dialog");
    return {
      id: pk.idOf(el),
      tag: label(el),
      // body/document, not a label: focus landing here means the walk reached
      // the end of the document and the browser chrome comes next.
      is_root: el === document.body || el === document.documentElement,
      name: el.tagName.toLowerCase(),
      role: el.getAttribute("role") || "",
      type: el.getAttribute("type") || "",
      text: text.slice(0, 60),
      tabindex: el.getAttribute("tabindex"),
      disabled: !!(el.disabled || el.getAttribute("aria-disabled") === "true"),
      in_dialog: !!dialog,
      // viewport coordinates: what elementFromPoint and hit-testing use
      rect: { x: r.x, y: r.y, left: r.left, top: r.top,
              width: r.width, height: r.height,
              right: r.right, bottom: r.bottom },
      // page coordinates: what a CDP screenshot clip uses
      page_rect: { x: r.left + window.scrollX, y: r.top + window.scrollY,
                   width: r.width, height: r.height },
      focus_visible: (function () { try { return el.matches(":focus-visible"); } catch (e) { return false; } })(),
      focus_self: (function () { try { return el.matches(":focus"); } catch (e) { return false; } })()
    };
  };

  // Composite a text colour over the first opaque ancestor background the way
  // page_audit resolves the resting state, and reuse its honesty labels so the
  // two reports can be read side by side.
  pk.stylePair = function (el) {
    function rgb(c) {
      var m = /rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+))?\s*\)/.exec(c);
      if (!m) return null;
      return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4] };
    }
    function over(top, bottom) {
      return { r: top.r * top.a + bottom.r * (1 - top.a),
               g: top.g * top.a + bottom.g * (1 - top.a),
               b: top.b * top.a + bottom.b * (1 - top.a), a: 1 };
    }
    function text(c) {
      return "rgb(" + Math.round(c.r) + ", " + Math.round(c.g) + ", " + Math.round(c.b) + ")";
    }
    var dark = false;
    try { dark = window.matchMedia("(prefers-color-scheme: dark)").matches; } catch (e) {}
    var cs = getComputedStyle(el);
    var fg = rgb(cs.color);
    if (!fg) return { method: "uncertain:unparseable-color", evidence: cs.color };
    var layers = [];
    var node = el;
    var method = "resolved";
    while (node && node.nodeType === 1) {
      var s = getComputedStyle(node);
      if (s.backgroundImage && s.backgroundImage !== "none") {
        return { method: "uncertain:background-image", evidence: label(node) };
      }
      if ((s.opacity !== "" && parseFloat(s.opacity) < 1) ||
          (s.filter && s.filter !== "none") ||
          (s.mixBlendMode && s.mixBlendMode !== "normal")) {
        return { method: "uncertain:effect-in-chain", evidence: label(node) };
      }
      var bg = rgb(s.backgroundColor);
      if (bg && bg.a > 0) {
        layers.push(bg);
        if (bg.a >= 1) break;
      }
      node = node.parentElement;
    }
    if (!layers.length || layers[layers.length - 1].a < 1) {
      var white = dark ? 0 : 255;
      layers.push({ r: white, g: white, b: white, a: 1 });
      method = "assumed-canvas";
    }
    var base = layers[layers.length - 1];
    for (var i = layers.length - 2; i >= 0; i--) base = over(layers[i], base);
    if (fg.a < 1) base = over(fg, base);
    return {
      method: method,
      fg: text(fg),
      bg: text(base),
      font_size: parseFloat(cs.fontSize) || 0,
      font_weight: parseFloat(cs.fontWeight) || 0
    };
  };

  // Five sample points inside the border box. 2.4.11's bar is "entirely
  // hidden", so one related hit is enough to pass.
  pk.hitTest = function (el) {
    var r = el.getBoundingClientRect();
    var xs = [0.5, 0.2, 0.8, 0.2, 0.8];
    var ys = [0.5, 0.2, 0.2, 0.8, 0.8];
    var samples = [];
    for (var i = 0; i < xs.length; i++) {
      var x = r.left + r.width * xs[i];
      var y = r.top + r.height * ys[i];
      var hit = null;
      try { hit = document.elementFromPoint(x, y); } catch (e) {}
      samples.push({
        x: Math.round(x), y: Math.round(y),
        related: !!hit && (el.contains(hit) || hit.contains(el)),
        hit: hit ? label(hit) : "(none)"
      });
    }
    return {
      samples: samples,
      visible_in_viewport: r.bottom > 0 && r.top < window.innerHeight &&
                           r.right > 0 && r.left < window.innerWidth
    };
  };

  document.addEventListener("click", function (event) {
    window.__pkClicks += 1;
    var t = event.target && event.target.nodeType === 1 ? label(event.target) : "(non-element)";
    window.__pkLastClick = t;
  }, true);

  if (window.MutationObserver) {
    try {
      new MutationObserver(function (records) { window.__pkMutations += records.length; })
        .observe(document.documentElement, { subtree: true, childList: true,
                                             attributes: true, characterData: true });
    } catch (e) {}
  }
  return "ready";
})()"""


# --- pure logic (no browser; entries here are plain dicts) ------------------


def positive_tabindex(value):
    """True when a tabindex attribute moves the element ahead of DOM order."""
    if value is None:
        return False
    try:
        return int(str(value).strip()) > 0
    except ValueError:
        return False


def median(values):
    """Median of a non-empty list; None for an empty one."""
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def perimeter_area(width, height, thickness=INDICATOR_THICKNESS):
    """2.4.13's reference area: the `thickness`-px perimeter of a w x h box.

    For a solid r-thickness outline: 2*r*(w + h) = 4h + 4w at r=2. Rounded
    boxes need slightly less; the plugin reports the flat rectangle as the
    stated approximation rather than guessing the corner radius.
    """
    return 2 * thickness * (float(width) + float(height))


def tabindex_reviews(stops):
    """One review per element carrying a positive tabindex (2.4.3 order risk)."""
    found = []
    for stop in stops:
        if not positive_tabindex(stop.get("tabindex")):
            continue
        found.append({
            "check": "TABINDEX",
            "tag": stop.get("tag", "(unknown)"),
            "status": "review",
            "severity": "review",
            "clause": "WCAG 2.4.3 (order risk, not a failure)",
            "message": (f"{stop.get('tag')} uses tabindex=\"{stop.get('tabindex')}\"; "
                        f"the Tab order no longer follows the DOM, so visual order "
                        f"and keyboard order can disagree"),
        })
    return found


def order_deviation(stops):
    """Backwards jumps in reading order along the walk.

    A stop counts as backwards only when it moves *up* by more than one row
    band (40px). The tolerance matters because elements on one visual row sit a
    few pixels apart: comparing band indices makes an 8px difference straddle a
    band boundary and read as a climb. Moving further right on the next row is
    normal grid flow, not a jump.

    A single climb is normal (a skip target, a footer link); repeated climbs
    are what break the intuition the page is built on.
    """
    row_tolerance = 40
    jumps = []
    previous = None
    for stop in stops:
        rect = stop.get("rect") or {}
        current = (rect.get("top") or 0, rect.get("left") or 0)
        if previous is not None and current[0] < previous[0] - row_tolerance:
            jumps.append({"from": list(previous), "to": list(current),
                          "tag": stop.get("tag", "(unknown)")})
        previous = current
    return {"jumps": jumps, "backwards": len(jumps)}


def order_reviews(walk):
    """Review when the Tab walk disagrees with reading order more than once."""
    deviation = walk.get("order") or {}
    if deviation.get("backwards", 0) < 2:
        return []
    first = deviation["jumps"][0]
    return [{
        "check": "ORDER",
        "tag": first.get("tag", "(unknown)"),
        "status": "review",
        "severity": "review",
        "clause": "WCAG 2.4.3 (meaningful sequence)",
        "message": (f"the Tab walk moves back up the page {deviation['backwards']} "
                    f"times (first at {first.get('tag')}); compare the sequence "
                    f"with the visual order before shipping"),
        "jumps": deviation["jumps"][:5],
    }]


def trap_verdict(walk):
    """A walk that never reached the end of the page has a keyboard trap.

    `stop_reason` separates the endings: "end" is a page that wrapped normally
    (focus leaves the document), "cycle" is a repeated element id, and "budget"
    is a walk cut short by the step limit. Only the first is healthy. A cycle
    through every tabbable is still a cycle — a page whose handlers pin Tab to
    its whole set is as trapping as one pinned to two controls.

    A cycle confined to a dialog is the expected modal behaviour and comes back
    as a review naming the container, so the reviewer confirms an escape route.
    """
    stops = walk.get("stops") or []
    reason = walk.get("stop_reason")
    if reason == "end":
        return None
    scoped = any(stop.get("in_dialog") for stop in stops)
    if reason == "budget":
        tags = ", ".join(sorted({stop.get("tag", "?") for stop in stops}))[:200]
        return {
            "check": "TRAP",
            "tag": stops[0].get("tag", "(unknown)") if stops else "(unknown)",
            "status": "uncertain:walk-truncated",
            "severity": "review",
            "clause": "WCAG 2.1.1 / 2.1.2 (walk incomplete)",
            "message": (f"the walk stopped at the {len(stops)}-step budget before the "
                        f"page ran out of elements ({tags}); raise --max-steps to "
                        f"decide whether the order wraps or traps"),
        }
    tags = ", ".join(sorted({stop.get("tag", "?") for stop in stops}))[:200]
    total = walk.get("tabbable_count") or 0
    covers_all = total and len(stops) >= total
    return {
        "check": "TRAP",
        "tag": stops[0].get("tag", "(unknown)") if stops else "(unknown)",
        "status": "review" if scoped else "FAIL",
        "severity": "review" if scoped else "important",
        "clause": "WCAG 2.1.1 / 2.1.2 (no keyboard trap)",
        "message": (
            f"focus cycles among {len(stops)} of {total} tabbables ({tags}); "
            + ("the cycle sits inside a dialog, which is expected — confirm Esc "
               "or a close control leaves it" if scoped
               else ("every tabbable is reachable, but Tab can never leave the "
                     "document: the browser's own controls become unreachable"
                     if covers_all else
                     "the page never reaches its own end, so anything outside "
                     "the cycle cannot be reached by Tab"))),
    }


def unreachable_finding(payload):
    """Interactive elements the keyboard cannot reach.

    Two distinct cases share one finding, because both mean "a keyboard user
    cannot operate this":

    - removed     a native control or interactive ARIA role carrying
                  tabindex="-1": it exists, it is visible, it is not disabled,
                  and no other route into the Tab order exists. This is the
                  classic 2.1.1 violation and it never enters the walk at all.
    - stranded    a tabbable the walk never landed on, but only when the walk
                  reached the end of the page. After a trap or a truncated
                  walk, those elements are unreached rather than unreachable,
                  and listing them would report one root cause many times.
    """
    removed = payload.get("removed_from_order") or []
    missing = payload.get("unreachable") or []
    walk = payload.get("walk") or {}
    reason = walk.get("stop_reason")

    found = []
    if removed:
        listed = ", ".join(item.get("tag", "?") for item in removed[:8])
        found.append({
            "check": "UNREACHABLE",
            "tag": removed[0].get("tag", "(unknown)"),
            "status": "FAIL",
            "severity": "important",
            "clause": "WCAG 2.1.1 (keyboard)",
            "message": (f"{len(removed)} interactive element(s) carry tabindex=\"-1\" "
                        f"and stay out of the Tab order: {listed}"),
            "elements": removed,
        })
    if missing and reason == "end":
        listed = ", ".join(f"{item.get('tag')} ({item.get('reason')})"
                           for item in missing[:8])
        found.append({
            "check": "UNREACHABLE",
            "tag": missing[0].get("tag", "(unknown)"),
            "status": "FAIL",
            "severity": "important",
            "clause": "WCAG 2.1.1 (keyboard)",
            "message": (f"{len(missing)} interactive element(s) never entered the Tab "
                        f"walk: {listed}"),
            "elements": missing,
        })
    return found


def obscured_verdict(obscured):
    """Classify one 2.4.11 sample set; "entirely hidden" is the bar."""
    if obscured.get("status"):
        return dict(obscured)
    if not obscured.get("visible_in_viewport"):
        return dict(obscured, status="uncertain:out-of-viewport", severity="review",
                    evidence="the focused element sits outside the viewport after focus")
    samples = obscured.get("samples") or []
    related = sum(1 for sample in samples if sample.get("related"))
    if samples and related == 0:
        hits = ", ".join(sorted({sample.get("hit", "?") for sample in samples}))
        return dict(obscured, status="FAIL", severity="important", clause="WCAG 2.4.11",
                    message=(f"none of the {len(samples)} sampled points inside the "
                             f"focused element belongs to it; author content covers "
                             f"it ({hits})"))
    return dict(obscured, status="pass", related=related, sampled=len(samples))


def indicator_verdict(indicator):
    """Verdict for one focused/unfocused crop comparison.

    FAIL  -> no pixel changed (2.4.7), or the change is under 3:1 (no visible
             cue), or the indicator's adjacent contrast is under 3:1 (1.4.11).
    pass  -> an indicator exists and clears the floor.
    uncertain:* -> the pair is not a clean focused/unfocused comparison.
    `aaa` is the 2.4.13 reading; it never drives the exit code.
    """
    if str(indicator.get("status", "")).startswith("uncertain"):
        return dict(indicator, severity="review")

    changed = int(indicator.get("changed_pixels") or 0)
    qualifying = int(indicator.get("qualifying_pixels") or 0)
    adjacent = indicator.get("adjacent_worst")
    area_min = indicator.get("area_minimum") or 0
    aaa = {
        "area_pixels": qualifying,
        "area_minimum": area_min,
        "area_pass": qualifying >= area_min,
        "same_pixel_median": indicator.get("same_pixel_median"),
        "same_pixel_min": indicator.get("same_pixel_min"),
    }
    if changed == 0:
        return dict(indicator, status="FAIL", severity="important", clause="WCAG 2.4.7",
                    aaa=aaa,
                    message=("focused and unfocused frames are identical; the control "
                             "shows no focus indicator at all"))
    if qualifying == 0:
        strongest = indicator.get("same_pixel_median") or 0.0
        return dict(indicator, status="FAIL", severity="important", clause="WCAG 1.4.11",
                    aaa=aaa,
                    message=(f"pixels changed ({changed}) but the strongest state "
                             f"change is {strongest:.2f}:1, below the "
                             f"{FOCUS_FLOOR:.1f}:1 floor; the indicator is not "
                             f"perceivable"))
    if adjacent is not None and adjacent < FOCUS_FLOOR:
        readable = int(indicator.get("adjacent_readable") or 0)
        sides = int(indicator.get("adjacent_sides") or 0)
        # One edge dissolving into an existing hard shadow does not hide the
        # state; an indicator unreadable against most of its surroundings does.
        if readable * 2 <= sides:
            return dict(indicator, status="FAIL", severity="important",
                        clause="WCAG 1.4.11", aaa=aaa,
                        message=(f"the indicator exists but only reaches {adjacent:.2f}:1 "
                                 f"against the colours it touches, on {sides - readable} "
                                 f"of {sides} sides (needs {FOCUS_FLOOR:.1f}:1); it "
                                 f"disappears into its surroundings"))
        return dict(indicator, status="pass", severity="none",
                    clause="2.4.7 / 1.4.11", aaa=aaa,
                    note=(f"one edge ({sides - readable} of {sides}) sits at "
                          f"{adjacent:.2f}:1 against adjacent content; the ring stays "
                          f"readable on the rest, so this passes with a caveat"))
    return dict(indicator, status="pass", severity="none",
                clause="2.4.7 / 1.4.11", aaa=aaa)


def state_contrast_verdict(state):
    """1.4.3 contrast for the element's own text in one transient state."""
    method = str(state.get("method", ""))
    if method.startswith("uncertain:"):
        return dict(state, status="uncertain", severity="review")
    try:
        ratio = wcag.contrast_ratio(state["fg"], state["bg"])
    except (ValueError, KeyError) as exc:
        return dict(state, method="uncertain:unparseable", status="uncertain",
                    severity="review", evidence=str(exc))
    size = float(state.get("font_size") or 0)
    weight = float(state.get("font_weight") or 0)
    threshold = (wcag.AA_LARGE_OR_UI
                 if size >= LARGE_SIZE or (size >= LARGE_BOLD_SIZE and weight >= BOLD_WEIGHT)
                 else wcag.AA_TEXT)
    status = "pass" if ratio >= threshold else "FAIL"
    message = None
    if status == "FAIL":
        message = (f"in the {state.get('state', 'transient')} state the text pair "
                   f"{state.get('fg')} on {state.get('bg')} is {ratio:.2f}:1, below "
                   f"{threshold:.1f}:1 for {size:g}px/{weight:g}; the pair may pass "
                   f"at rest and fail once the state applies")
    return dict(state, ratio=round(ratio, 2), threshold=threshold, status=status,
                severity="none" if status == "pass" else "important",
                clause="WCAG 1.4.3", message=message)


def hover_same_reviews(stops):
    """Focus and hover crops that are identical hide the focus state.

    Only reported for stops that have a visible indicator: when there is no
    indicator at all, NO-FOCUS already owns that root cause and a second
    finding would count the same defect twice.
    """
    found = []
    for stop in stops:
        indicator = stop.get("indicator") or {}
        if indicator.get("hover_identical") is not True:
            continue
        if not indicator.get("qualifying_pixels"):
            continue
        found.append({
            "check": "HOVER-SAME",
            "tag": stop.get("tag", "(unknown)"),
            "status": "review",
            "severity": "review",
            "clause": "plugin floor (focus must differ from hover)",
            "message": (f"{stop.get('tag')} looks identical on hover and on keyboard "
                        f"focus; a keyboard user cannot tell the two states apart"),
        })
    return found


def classify(payload):
    """Split everything into (measures, uncertain, reviews)."""
    measures, uncertain, reviews = [], [], []
    measures.extend(unreachable_finding(payload))
    trap = trap_verdict(payload.get("walk") or {})
    if trap is not None:
        (reviews if str(trap["status"]).startswith(("review", "uncertain"))
         else measures).append(trap)
    for stop in payload.get("stops") or []:
        tag = stop.get("tag", "(unknown)")
        obscured = stop.get("obscured")
        obscured_fail = False
        if obscured:
            result = obscured_verdict(obscured)
            obscured_fail = result["status"] == "FAIL"
            bucket = (uncertain if str(result["status"]).startswith("uncertain")
                      else measures)
            bucket.append(dict(result, tag=tag))
        indicator = stop.get("indicator")
        if indicator and indicator.get("measured", True):
            result = indicator_verdict(dict(indicator, tag=tag))
            # An obscured control's ring is behind the covering content, so a
            # "no indicator" verdict there would report the same defect twice
            # and blame the wrong cause. The 2.4.11 finding owns it.
            if obscured_fail and result["status"] == "FAIL" \
                    and result.get("clause") == "WCAG 2.4.7":
                result = dict(result, status="uncertain:obscured",
                              severity="review",
                              evidence="the control is covered (2.4.11); its "
                                       "indicator cannot be seen or measured")
            bucket = (uncertain if str(result["status"]).startswith("uncertain")
                      else measures)
            bucket.append(dict(result, tag=tag))
        for state in stop.get("states") or []:
            result = state_contrast_verdict(dict(state, tag=tag))
            # Focus and hover can hit the same unmeasurable background (a page
            # texture, an image hero). Listing the identical uncertainty twice
            # inflates the count and says nothing new, so states collapse onto
            # one row that names both.
            if result["status"] == "uncertain":
                key = (tag, result.get("method"), result.get("evidence"))
                known = next((item for item in uncertain
                              if (item.get("tag"), item.get("method"),
                                  item.get("evidence")) == key), None)
                if known is not None:
                    known["states"] = sorted(set(
                        (known.get("states") or []) + [result.get("state")]))
                    continue
                result["states"] = [result.get("state")]
                uncertain.append(result)
            else:
                measures.append(result)
    reviews.extend(tabindex_reviews(payload.get("stops") or []))
    reviews.extend(order_reviews(payload.get("walk") or {}))
    reviews.extend(hover_same_reviews(payload.get("stops") or []))
    for entry in payload.get("activation") or []:
        if entry.get("reacted"):
            continue
        reviews.append({
            "check": "ACTIVATION",
            "tag": entry.get("tag", "(unknown)"),
            "status": "review",
            "severity": "review",
            "clause": "WCAG 2.1.1 (operable, not only focusable)",
            "message": (f"{entry.get('tag')} takes focus but neither Enter nor Space "
                        f"produced a click or a DOM change; confirm the custom "
                        f"control can be operated"),
        })
    return measures, uncertain, reviews


def build_report(url, payload, viewport=None):
    """Full report dict from one walk payload (real or synthetic)."""
    measures, uncertain, reviews = classify(payload)
    fails = [item for item in measures if item.get("status") == "FAIL"]
    passes = [item for item in measures if item.get("status") == "pass"]
    walk = payload.get("walk") or {}
    stops = payload.get("stops") or []
    measured = [stop for stop in stops
                if (stop.get("indicator") or {}).get("measured") is True]
    measured_indicators = [stop["indicator"] for stop in measured
                           if (stop["indicator"] or {}).get("changed_pixels") is not None]
    aaa_pass = sum(1 for indicator in measured_indicators
                   if indicator.get("qualifying_pixels", 0)
                   >= (indicator.get("area_minimum") or 0))
    summary = {
        "tabbables": walk.get("tabbable_count", 0),
        "stops_walked": len(stops),
        "stop_reason": walk.get("stop_reason", "budget"),
        "unreachable": (len(payload.get("unreachable") or [])
                        + len(payload.get("removed_from_order") or [])),
        "removed_from_order": len(payload.get("removed_from_order") or []),
        "indicators_measured": len(measured_indicators),
        "no_indicator": sum(1 for item in fails if item.get("clause") == "WCAG 2.4.7"),
        "indicator_low_contrast": sum(1 for item in fails
                                     if item.get("clause") == "WCAG 1.4.11"),
        "state_contrast_fail": sum(1 for item in fails
                                   if item.get("clause") == "WCAG 1.4.3"),
        "obscured": sum(1 for item in fails if item.get("clause") == "WCAG 2.4.11"),
        "pass": len(passes),
        "fail": len(fails),
        "uncertain": len(uncertain),
        "review": len(reviews),
        "activation_probed": len(payload.get("activation") or []),
        "positive_tabindex": sum(1 for stop in stops
                                 if positive_tabindex(stop.get("tabindex"))),
        "aaa_area_pass": aaa_pass,
        "aaa_area_measured": len(measured_indicators),
    }
    if payload.get("measure_skipped"):
        summary["measure_skipped"] = payload["measure_skipped"]
    return {
        "url": url,
        "verified": True,
        "viewport": viewport,
        "clause_coverage": CLAUSE_COVERAGE,
        "walk": {
            "tabbable_count": walk.get("tabbable_count", 0),
            "order": walk.get("order"),
            "stop_reason": walk.get("stop_reason", "budget"),
            "sequence": [{"tag": stop.get("tag"), "text": stop.get("text"),
                          "focus_visible": stop.get("focus_visible")}
                         for stop in stops],
        },
        "findings": fails + passes + uncertain + reviews,
        "summary": summary,
    }


def has_measurable_fail(report):
    """Exit rule: any focus/keyboard FAIL, never a review or an uncertain."""
    return bool(report["summary"]["fail"])


def render_text(report):
    """Human report: FAILs, then reviews, then uncertain, then the summary."""
    summary = report["summary"]
    walk = report["walk"]
    ending = {"end": "walked to the end of the page",
              "cycle": "cycle closed on a repeated element",
              "budget": "stopped at the step budget (walk incomplete)"
              }.get(walk["stop_reason"], walk["stop_reason"])
    # "unreachable" is only a claim the walk can support when it reached the
    # end; after a trap or a truncation the honest word is "unvisited".
    walked_out = walk["stop_reason"] == "end"
    stranded = summary["unreachable"] - summary["removed_from_order"]
    if stranded and not walked_out:
        tail = f"{stranded} unvisited, walk did not finish"
    elif stranded:
        tail = f"{stranded} unreachable"
    else:
        tail = "0 unreachable"
    lines = [
        f"Keyboard audit: {report['url']}",
        f"Clauses: {report['clause_coverage']}",
        f"Tab walk: {walk['tabbable_count']} tabbable elements, "
        f"{summary['stops_walked']} stops, {ending}; "
        f"{summary['indicators_measured']} indicators measured by pixels",
    ]
    for finding in report["findings"]:
        if finding.get("status") != "FAIL":
            continue
        lines.append(f"FAIL [{finding.get('clause')}] {finding.get('tag')} — "
                     f"{finding.get('message')}")
    for finding in report["findings"]:
        if finding.get("status") == "review":
            lines.append(f"REVIEW [{finding.get('clause')}] {finding.get('tag')} — "
                         f"{finding.get('message')}")
    for finding in report["findings"]:
        if finding.get("status") == "uncertain":
            detail = finding.get("evidence") or finding.get("message") or ""
            lines.append(f"UNCERTAIN [{finding.get('method') or finding.get('clause')}] "
                         f"{finding.get('tag')} — {detail}")
    lines.append(
        f"Summary: {summary['pass']} pass, {summary['fail']} FAIL, "
        f"{summary['uncertain']} uncertain, {summary['review']} review "
        f"across {summary['tabbables']} tabbables ({tail})")
    if summary.get("aaa_area_measured"):
        lines.append(
            f"2.4.13 (AAA, supplementary): {summary['aaa_area_pass']} of "
            f"{summary['aaa_area_measured']} indicators meet the 4h+4w two-pixel "
            f"perimeter area; this reading never affects the exit status")
    if summary.get("measure_skipped"):
        lines.append(f"Skipped: {summary['measure_skipped']}")
    return "\n".join(lines)


# --- pixel measurement (pure: PNG bytes in, measurements out) --------------


def _channels(pixels, width, height):
    return 4 if len(pixels) == width * height * 4 else 3


def _pixel(pixels, index, channels):
    base = index * channels
    return pixels[base:base + 3]


def _ratio(pixel_a, pixel_b):
    high, low = sorted((wcag.relative_luminance(tuple(value / 255 for value in pixel_a)),
                        wcag.relative_luminance(tuple(value / 255 for value in pixel_b))),
                       reverse=True)
    return (high + 0.05) / (low + 0.05)


def _side(index, width, element_width, element_height, margin):
    """Which side of the element's box a changed pixel lies on."""
    x, y = index % width, index // width
    left, top = margin, margin
    right, bottom = left + element_width, top + element_height
    if y < top:
        return "top"
    if y >= bottom:
        return "bottom"
    if x < left:
        return "left"
    if x >= right:
        return "right"
    return "inside"


def make_clip(rect, margin=CLIP_MARGIN):
    """CDP screenshot clip for an element given its page-coordinate rect."""
    return {
        "x": float(rect.get("x") or 0) - margin,
        "y": float(rect.get("y") or 0) - margin,
        "width": float(rect.get("width") or 1) + 2 * margin,
        "height": float(rect.get("height") or 1) + 2 * margin,
        "scale": 1,
    }


def measure_indicator(focused_png, blurred_png, rect, margin=CLIP_MARGIN):
    """Compare the focused and unfocused crops of one element.

    Both frames come from the same clip in the same viewport, so index geometry
    is shared. Measurements:

      changed_pixels      pixels differing by more than DIFF_TOLERANCE/channel
      qualifying_pixels   changed pixels whose focused-vs-unfocused contrast is
                          >= 3:1 — 2.4.13's same-pixel change, and the only
                          pixels that count toward the indicator area
      same_pixel_median   median same-pixel contrast over changed pixels
      same_pixel_min      minimum same-pixel contrast (antialiasing lives here)
      adjacent_worst      worst per-side median contrast between a qualifying
                          pixel and a *stable* neighbour pixel (one unchanged
                          between the frames). The median keeps antialiased
                          corners from faking a failure; the statistic is the
                          worst side so a ring invisible on one edge shows up.
      area_minimum        4h + 4w, the 2px perimeter of the element's box
    """
    width_a, height_a, pixels_a = image_diff.decode_png_bytes(focused_png)
    width_b, height_b, pixels_b = image_diff.decode_png_bytes(blurred_png)
    if (width_a, height_a) != (width_b, height_b):
        return {"status": "uncertain:frame-size", "measured": False,
                "evidence": f"{width_a}x{height_a} vs {width_b}x{height_b}"}
    channels = _channels(pixels_a, width_a, height_a)
    if channels != _channels(pixels_b, width_b, height_b):
        return {"status": "uncertain:channel-count", "measured": False,
                "evidence": "the two frames carry a different channel count"}

    changed = {}
    for index in range(width_a * height_a):
        first = _pixel(pixels_a, index, channels)
        second = _pixel(pixels_b, index, channels)
        if max(abs(first[0] - second[0]), abs(first[1] - second[1]),
               abs(first[2] - second[2])) > DIFF_TOLERANCE:
            changed[index] = (first, second, _ratio(first, second))

    area_min = round(perimeter_area(
        float(rect.get("width") or 0), float(rect.get("height") or 0)))
    if not changed:
        return {
            "changed_pixels": 0,
            "qualifying_pixels": 0,
            "same_pixel_median": 0.0,
            "same_pixel_min": 0.0,
            "adjacent_worst": None,
            "adjacent_by_side": {},
            "area_minimum": area_min,
            "measured": True,
        }

    magnitudes = [entry[2] for entry in changed.values()]
    qualifying = {index: entry for index, entry in changed.items()
                  if entry[2] >= FOCUS_FLOOR}
    by_side = {}
    element_width = float(rect.get("width") or 0)
    element_height = float(rect.get("height") or 0)
    for index in qualifying:
        side = _side(index, width_a, element_width, element_height, margin)
        x, y = index % width_a, index // width_a
        first = qualifying[index][0]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width_a and 0 <= ny < height_b):
                continue
            neighbour_index = ny * width_a + nx
            if neighbour_index in changed:
                continue  # another indicator pixel, not the surface behind it
            by_side.setdefault(side, []).append(
                _ratio(first, _pixel(pixels_b, neighbour_index, channels)))

    side_stats = {
        side: {"samples": len(values),
               "median": round(median(values), 2),
               "minimum": round(min(values), 2)}
        for side, values in by_side.items()
    }
    # 1.4.11 judges whether the state can be picked out, not whether every
    # edge is perfect. A ring that dissolves into a hard shadow on one edge
    # while clearing 17:1 on the other three is still perceivable; a ring the
    # colour of its own control is not, on any edge. So count sides that clear
    # the floor and fail only when the indicator is unreadable overall.
    readable = [side for side, stats in side_stats.items()
                if stats["median"] >= FOCUS_FLOOR]
    worst = None if not side_stats else min(
        stats["median"] for stats in side_stats.values())
    return {
        "changed_pixels": len(changed),
        "qualifying_pixels": len(qualifying),
        "same_pixel_median": round(float(median(magnitudes)), 2),
        "same_pixel_min": round(min(magnitudes), 2),
        "adjacent_worst": None if worst is None else round(worst, 2),
        "adjacent_by_side": side_stats,
        "adjacent_sides": len(side_stats),
        "adjacent_readable": len(readable),
        "area_minimum": area_min,
        "measured": True,
    }


def crops_identical(first_png, second_png):
    """True when two crops agree within DIFF_TOLERANCE; None when unreadable."""
    return _frames_agree(first_png, second_png)


# --- browser path (raises on any failure; main() reports "claims nothing") --


def _evaluate(session, session_id, expression, await_promise=False):
    result = session.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": await_promise},
        session=session_id,
    )
    return result["result"].get("value")


def _json_eval(session, session_id, expression):
    value = _evaluate(session, session_id, expression)
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


def _press(session, session_id, key, code, virtual_key, modifiers=0):
    """One real key press (rawKeyDown + keyUp), so the page sees trusted input."""
    for kind in ("rawKeyDown", "keyUp"):
        session.send("Input.dispatchKeyEvent", {
            "type": kind, "key": key, "code": code,
            "windowsVirtualKeyCode": virtual_key,
            "nativeVirtualKeyCode": virtual_key,
            "modifiers": modifiers,
        }, session=session_id)


def _shot(session, session_id, clip):
    data = session.send("Page.captureScreenshot", {
        "format": "png", "clip": clip, "captureBeyondViewport": True,
    }, session=session_id)["data"]
    return base64.b64decode(data)


def _frames_agree(first_png, second_png):
    """True when two crops match within DIFF_TOLERANCE; None when unreadable."""
    try:
        width_a, height_a, pixels_a = image_diff.decode_png_bytes(first_png)
        width_b, height_b, pixels_b = image_diff.decode_png_bytes(second_png)
    except Exception:  # noqa: BLE001 - an unreadable crop proves nothing either way
        return None
    if (width_a, height_a) != (width_b, height_b):
        return None
    channels = _channels(pixels_a, width_a, height_a)
    if channels != _channels(pixels_b, width_b, height_b):
        return None
    for index in range(width_a * height_a):
        first = _pixel(pixels_a, index, channels)
        second = _pixel(pixels_b, index, channels)
        if max(abs(first[0] - second[0]), abs(first[1] - second[1]),
               abs(first[2] - second[2])) > DIFF_TOLERANCE:
            return False
    return True


def _settled_shot(session, session_id, clip, attempts=SETTLE_ATTEMPTS,
                  interval=SETTLE_INTERVAL):
    """Shoot until two consecutive frames agree, then use that frame.

    A focus style can animate — `transition: box-shadow` on a `.copy` button was
    enough — and then the first frame after focus is mid-transition. Measured
    for real: the same page produced a passing indicator on one run and 1.02:1
    on the next, because the frame landed at different points in the animation.
    An audit that reports different verdicts for an unchanged page is not
    evidence, so every measured frame waits for the same two-frame agreement the
    capture tool uses.
    """
    previous = None
    for _ in range(max(2, attempts)):
        current = _shot(session, session_id, clip)
        if previous is not None and _frames_agree(previous, current):
            return current
        previous = current
        time.sleep(interval)
    return previous


def _unreachable(session, session_id, visited_ids):
    """Tabbables whose id never appeared in the walk, with the reason."""
    expression = (
        "(function () {"
        "var visited = " + json.dumps(sorted(visited_ids)) + ";"
        "var seen = {}; for (var i = 0; i < visited.length; i++) seen[visited[i]] = 1;"
        "var out = []; var all = __pk.tabbables();"
        "for (var j = 0; j < all.length; j++) {"
        "  var el = all[j]; var id = __pk.idOf(el);"
        "  if (seen[id]) continue;"
        "  var role = el.getAttribute('role') || '';"
        "  var interactive = !!(el.matches('a[href],button,input,select,textarea,summary') ||"
        "    /^(button|link|checkbox|radio|switch|tab|menuitem|option|slider|spinbutton|combobox)$/.test(role));"
        "  var d = __pk.describe(el);"
        "  out.push({tag: d.tag, role: role,"
        "    reason: interactive ? 'interactive but not reachable by Tab'"
        "                         : 'focus stop outside the Tab cycle'});"
        "}"
        "return JSON.stringify(out);"
        "})()")
    return _json_eval(session, session_id, expression) or []


def _measure_stop(session, session_id, stop):
    """Pixel and state evidence for one focused element.

    Order matters, and the hover pair must be read *while* the pointer is on the
    element — reading it after the mouse leaves returns the resting state and
    would report a hover regression as a pass.

    Sequence: focused frame (Tab already put the element in view) -> blur ->
    unfocused frame -> hover frame and hover style pair (pointer on element) ->
    restore focus so the next Tab continues from the same place.
    """
    rect = stop.get("page_rect") or {}
    if (rect.get("width") or 0) <= 0 or (rect.get("height") or 0) <= 0:
        stop["indicator"] = {"status": "uncertain:zero-size", "measured": False,
                            "evidence": "the focused element has no box to screenshot"}
        return stop

    clip = make_clip(rect)
    focused_frame = _settled_shot(session, session_id, clip)
    _evaluate(session, session_id, "document.activeElement && document.activeElement.blur()")
    restored = _evaluate(
        session, session_id,
        "document.activeElement && document.activeElement !== document.body && "
        "document.activeElement !== document.documentElement")
    if restored:
        stop["indicator"] = {
            "status": "uncertain:refocused-by-page", "measured": False,
            "evidence": ("the page restored focus after blur(); the second frame is "
                         "not an unfocused frame, so no verdict is made"),
        }
        return stop

    blurred_frame = _settled_shot(session, session_id, clip)
    indicator = measure_indicator(focused_frame, blurred_frame, rect)

    hovered_frame, hover_pair = _hover(session, session_id, stop, clip)
    if hovered_frame is not None:
        indicator["hover_identical"] = crops_identical(focused_frame, hovered_frame)
    stop["indicator"] = indicator
    if hover_pair:
        stop.setdefault("states", []).append(dict(hover_pair, state="hover"))

    focus_pair = _refocus(session, session_id, stop)
    if focus_pair:
        stop.setdefault("states", []).append(dict(focus_pair, state="focus"))
    stop["obscured"] = _hit_test(session, session_id, stop)
    return stop


def _hover(session, session_id, stop, clip):
    """Point at the element; return (hovered frame, hover style pair).

    Both reads happen while the pointer is still on the element, in one
    uninterleaved block, because moving the pointer away first silently turns
    any hover regression into a pass.
    """
    rect = stop.get("rect") or {}
    if (rect.get("width") or 0) <= 0:
        return None, None
    session.send("Input.dispatchMouseEvent", {
        "type": "mouseMoved",
        "x": (rect.get("x") or 0) + (rect.get("width") or 0) / 2,
        "y": (rect.get("y") or 0) + (rect.get("height") or 0) / 2,
    }, session=session_id)
    frame = _settled_shot(session, session_id, clip)
    pair = _json_eval(
        session, session_id,
        "(function(){var el=__pk.of(" + str(stop.get("id") or 0) + ");"
        "return el ? JSON.stringify(__pk.stylePair(el)) : null;})()")
    session.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 0, "y": 0},
                 session=session_id)
    return frame, pair


def _refocus(session, session_id, stop):
    """Restore focus after measurement; returns the focused-state colour pair.

    focus({preventScroll:true}) is the documented restore path: it was verified
    to keep :focus-visible true and to leave the Tab chain advancing from the
    same element.
    """
    expression = (
        "(function(){var el=__pk.of(" + str(stop.get("id") or 0) + ");"
        "if(!el) return null; el.focus({preventScroll:true});"
        "if(document.activeElement!==el) return null;"
        "return JSON.stringify(__pk.stylePair(el));})()")
    return _json_eval(session, session_id, expression)


def _hit_test(session, session_id, stop):
    """2.4.11 sample set for the currently focused, refocused element."""
    expression = (
        "(function(){var el=__pk.of(" + str(stop.get("id") or 0) + ");"
        "if(!el || document.activeElement!==el) return null;"
        "return JSON.stringify(__pk.hitTest(el));})()")
    return _json_eval(session, session_id, expression)


def _probe_activation(session, session_id, stops, payload):
    """Enter/Space on custom ARIA widgets: focusable is not the same as operable."""
    customs = [stop for stop in stops
               if stop.get("role") in ("button", "link", "checkbox", "switch",
                                       "tab", "menuitem", "option")
               and stop.get("tag", "").split(".")[0].split("#")[0]
               not in ("button", "a", "input", "select", "textarea")]
    for stop in customs[:ACTIVATION_LIMIT]:
        focused = _evaluate(
            session, session_id,
            "(function(){var el=__pk.of(" + str(stop.get("id") or 0) + ");"
            "if(!el) return false; el.focus({preventScroll:true});"
            "return document.activeElement===el;})()")
        if not focused:
            continue
        _evaluate(session, session_id, "window.__pkClicks=0; window.__pkMutations=0;")
        _press(session, session_id, "Enter", "Enter", 13)
        entered = _evaluate(session, session_id, "window.__pkClicks") or 0
        mutated_enter = _evaluate(session, session_id, "window.__pkMutations") or 0
        _evaluate(session, session_id, "window.__pkClicks=0; window.__pkMutations=0;")
        _press(session, session_id, " ", "Space", 32)
        spaced = _evaluate(session, session_id, "window.__pkClicks") or 0
        mutated_space = _evaluate(session, session_id, "window.__pkMutations") or 0
        payload["activation"].append({
            "tag": stop.get("tag"),
            "reacted": bool(entered or spaced or mutated_enter or mutated_space),
            "enter_clicks": entered, "space_clicks": spaced,
            "mutations": mutated_enter + mutated_space,
        })


def _removed_from_order(session, session_id):
    """Visible, enabled, interactive controls carrying tabindex="-1".

    These never enter the walk, so the walk cannot report them. Only elements
    that look interactive are listed: a tabindex="-1" on a container is the
    standard way to make a skip target focusable programmatically and is not a
    defect. aria-hidden and disabled elements are excluded for the same reason
    page_audit excludes them.
    """
    expression = (
        "(function(){"
        "var out=[];"
        "var all=document.querySelectorAll('[tabindex]');"
        "for (var i=0;i<all.length;i++){"
        "  var el=all[i];"
        "  if (parseInt(el.getAttribute('tabindex'),10) >= 0) continue;"
        "  if (el.disabled || el.getAttribute('aria-hidden')==='true') continue;"
        "  if (!__pk.isVisible(el)) continue;"
        "  var role=el.getAttribute('role')||'';"
        "  var interactive=!!(el.matches('a[href],button,input,select,textarea,summary')||"
        "    /^(button|link|checkbox|radio|switch|tab|menuitem|option|slider|spinbutton|combobox)$/.test(role));"
        "  if (!interactive) continue;"
        "  var d=__pk.describe(el);"
        "  out.push({tag:d.tag, role:role});"
        "}"
        "return JSON.stringify(out);"
        "})()")
    return _json_eval(session, session_id, expression) or []


def _is_walk_end(description):
    """True when a Tab landed on the document root or nothing at all.

    The browser's end-of-document stop is <body>. Its rendered text must not be
    used as the test: `label()` gives body a text label, so comparing the tag
    string misses it. `is_root` comes from the browser, where identity is exact.
    """
    if not description or not description.get("id"):
        return True
    return description.get("is_root") is True


def _walk_and_measure(session, session_id, max_steps, measure):
    """Tab through the page for real; measure the first `measure` stops.

    Tab goes to the page rather than being simulated with el.focus(), so
    :focus-visible matches, the page scrolls its own way, and focus-management
    scripts run. Three endings are distinguished, because they mean different
    things: "cycle" (an id repeats — possible trap), "end" (focus left the
    document or reached a body/html stop — the normal end of the page), and
    "budget" (max_steps ran out — the walk is incomplete, so nothing can be
    called unreachable).
    """
    stops = []
    seen = set()
    reason = "budget"
    for _ in range(max(1, max_steps)):
        _press(session, session_id, "Tab", "Tab", 9)
        description = _json_eval(
            session, session_id, "JSON.stringify(__pk.describe(document.activeElement))")
        if _is_walk_end(description):
            reason = "end"
            break
        identity = description["id"]
        if identity in seen:
            reason = "cycle"
            break
        seen.add(identity)
        stops.append(description)
        if measure and len(stops) <= measure:
            _measure_stop(session, session_id, stops[-1])
    return stops, reason, seen


def audit_url(url, max_steps=MAX_STEPS, measure=MEASURE_STOPS,
              width=1280, height=800):
    """Launch one browser, walk the Tab order, measure the stops.

    Raises on any failure so main() can print {"verified": false}.
    """
    browser = visual_capture.find_browser()
    if not browser:
        raise cdp.BrowserError(
            "no Chromium-family browser found at an absolute path; keyboard audit disabled")
    process = profile = connection = session = target_id = None
    try:
        process, profile, ws_url = visual_capture._start_cdp_browser(browser)  # noqa: SLF001 - documented sibling reuse
        connection = cdp.Connection(ws_url)
        session = cdp.Session(connection)
        target_id = session.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        session_id = session.send(
            "Target.attachToTarget", {"targetId": target_id, "flatten": True}
        )["sessionId"]
        for domain in ("Page", "Runtime"):
            session.send(domain + ".enable", session=session_id)
        session.send("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
        }, session=session_id)
        session.send("Page.navigate", {"url": url}, session=session_id)
        if cdp.wait_for_event(
            session, "Page.loadEventFired", LOAD_TIMEOUT,
            match=lambda message: message.get("sessionId") == session_id,
        ) is None:
            raise cdp.BrowserError(f"page did not fire load within {LOAD_TIMEOUT:g}s")
        _evaluate(session, session_id,
                  "(async () => { try { if (document.fonts && document.fonts.ready) "
                  "await document.fonts.ready; } catch (e) {} return 1; })()",
                  await_promise=True)
        _evaluate(session, session_id, PRELUDE_JS)
        # A prelude that threw would leave __pk undefined and every later read
        # would come back empty — reported as "0 tabbables, all clean". That
        # silent-clean failure mode is worse than a crash, so assert instead.
        ready = _evaluate(session, session_id,
                          "typeof __pk !== 'undefined' && typeof __pk.describe === 'function'")
        if ready is not True:
            raise cdp.BrowserError(
                "the audit prelude did not install (script blocked or threw); "
                "claiming nothing about this page")

        count = _evaluate(session, session_id, "__pk.tabbables().length") or 0
        budget = max(0, measure or 0)
        stops, reason, visited = _walk_and_measure(session, session_id, max_steps, budget)
        payload = {
            "walk": {
                "tabbable_count": count,
                "stop_reason": reason,
                "stops": stops,
                "order": order_deviation(stops),
            },
            "unreachable": _unreachable(session, session_id, visited),
            "removed_from_order": _removed_from_order(session, session_id),
            "stops": stops,
            "activation": [],
        }
        _probe_activation(session, session_id, stops[:budget], payload)
        if budget == 0:
            payload["measure_skipped"] = "pixel and state checks disabled (--measure 0)"
        elif len(stops) > budget:
            payload["measure_skipped"] = (
                f"{len(stops) - budget} stops past the first {budget} were walked "
                f"but not measured (raise --measure to cover more)")
        return payload
    finally:
        if session is not None and target_id is not None:
            try:
                session.send("Target.closeTarget", {"targetId": target_id}, timeout=3)
            except Exception:
                pass
        if session is not None:
            try:
                session.send("Browser.close", timeout=3)
            except Exception:
                pass
        if connection is not None:
            connection.close()
        if process is not None:
            process.terminate()
        if profile is not None:
            shutil.rmtree(profile, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Keyboard and focus audit over CDP: Tab order, focus visibility, "
                    "indicator contrast, obscured focus, state contrast.")
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true",
                        help="print the JSON report instead of text")
    parser.add_argument("--allow-private", action="store_true",
                        help="allow non-public, non-loopback addresses")
    parser.add_argument("--measure", type=int, default=MEASURE_STOPS,
                        help=f"stops to measure with screenshots "
                             f"(default {MEASURE_STOPS}; 0 skips pixel checks)")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS,
                        help=f"maximum Tab presses before stopping (default {MAX_STEPS})")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        url = visual_capture.validate_url(args.url, allow_private=args.allow_private)
    except visual_capture.UrlRejected as exc:
        print(json.dumps({"verified": False, "reason": f"URL rejected: {exc}"},
                         ensure_ascii=False))
        return 3

    try:
        payload = audit_url(url, max_steps=args.max_steps, measure=args.measure,
                            width=args.width, height=args.height)
    except Exception as exc:  # noqa: BLE001 - the documented "claims nothing" contract
        print(json.dumps({
            "verified": False,
            "reason": f"no audit performed: {type(exc).__name__}: {exc}",
        }, ensure_ascii=False))
        return 2

    report = build_report(url, payload,
                          viewport={"width": args.width, "height": args.height})
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 1 if has_measurable_fail(report) else 0


if __name__ == "__main__":
    sys.exit(main())
