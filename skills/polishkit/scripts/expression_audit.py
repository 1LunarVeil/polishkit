"""Read how a page allocates its expression budget, and ask about the conflicts.

Usage:
  python expression_audit.py URL [--json] [--allow-private] [--width W] [--height H]

This tool replaced an earlier version that reported a single "type ratio" —
largest font size divided by body size. The maintainer's critique was right:
that number says how loud the page is, never whether the loud thing deserved
to be loud. A 100px "Hello" scores the same as a 100px revenue figure. Worse,
it measured the largest text on the whole page, so a decorative numeral far
below the fold could carry a page's "drama" score.

What it reports now, all measured on the first screen (the viewport), because
that is where the allocation decision is visible:

- ATTENTION      the loudest text element (largest size, then largest area).
                 Everything else is graded against it: how many distinct size
                 steps sit below it, and whether the second-loudest text is
                 close enough in size to compete.
- COLUMN FILL    of the vertical strip the loudest element occupies, how much
                 is filled by other text before the fold. A 70px figure over a
                 mostly-empty 480px band fills little; the same figure inside a
                 dense panel fills most of it. This is the measure that
                 separates "the number carries the page" from "the number is
                 the page".
- STEP LADDER    the sizes present on the first screen, as a ladder from the
                 loudest down to body. A ladder with a missing rung (70 then 22,
                 nothing between) leaves a visual desert; a ladder with
                 88/30/20/15 has no gap for the eye to fall through.
- DENSITY        text items per 100,000 CSS px² of first screen, as a raw
                 number with no threshold — a photo portfolio is legitimately
                 sparse and a dashboard is not, so this never becomes a verdict.

What it asks instead of judging: for the loudest element it prints the size, the
text, the count of other information in its own band, the blank run below it,
and the page's own h1 if there is one. Then it states the question a reviewer
should answer — "is this the thing the screen exists to show?" — because that is
a product question and no rectangle can answer it.

Nothing here gates a build. Every finding is review severity; the exit status is
0 unless the audit could not run at all. A tool that let taste break CI would
reproduce the failure mode the benchmark's human-verdict section warns about.

Exit status: 0 always, 2 no browser or CDP failure ({"verified": false}),
3 URL rejected.

Read-only: prints a report and writes nothing. stdlib only; CDP on loopback.
"""

import argparse
import json
import sys

sys.dont_write_bytecode = True
import cdp  # noqa: E402  (sibling module; no third-party dependencies)
import visual_capture  # noqa: E402

BODY_FALLBACK = 16.0
DISPLAY_MIN = 32.0          # a size worth calling display-scale, in CSS px
BAND_PAD_FACTOR = 1.5       # the loud element's band, as a multiple of its height
LADDER_GAP_FACTOR = 1.8     # a size jump above this ratio is a missing rung
COMPETITOR_RATIO = 0.75     # a second element at 75%+ of the loudest competes
MAX_SAMPLES = 500

CLAUSE_COVERAGE = (
    "references/expression.md item 1 (type drama) and item 4 (focal engineering) "
    "as first-screen geometry: attention target, column fill, size ladder, "
    "density. Composition, texture and signature are printed as questions, not "
    "scored."
)

MANUAL_ITEMS = (
    "is the loudest element the thing this screen exists to show?",
    "does any hero-scale field look dead flat, or does it carry texture?",
    "would removing the signature element leave the page generic?",
    "is there exactly one asymmetry, or does the tension fight itself?",
    "does the copy name the same action the same way everywhere?",
)

COLLECTOR_JS = r"""(function () {
  var MAX = __MAX_SAMPLES__;
  var DISPLAY_MIN = __DISPLAY_MIN__;
  var BAND_PAD = __BAND_PAD__;
  var result;
  try {
    result = collect();
  } catch (err) {
    result = { error: String((err && err.message) || err) };
  }
  return JSON.stringify(result);

  function label(el) {
    var cls = typeof el.className === "string" ? el.className.trim().split(/\s+/)[0] : "";
    if (el.id) return el.tagName.toLowerCase() + "#" + el.id;
    if (cls) return el.tagName.toLowerCase() + "." + cls;
    return el.tagName.toLowerCase();
  }

  function ownText(el) {
    var out = "";
    for (var i = 0; i < el.childNodes.length; i++) {
      if (el.childNodes[i].nodeType === 3) out += el.childNodes[i].nodeValue;
    }
    return out.replace(/\s+/g, " ").trim();
  }

  function collect() {
    var VH = window.innerHeight, VW = window.innerWidth;
    var nodes = document.querySelectorAll("*");
    var items = [];
    var capped = false;

    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var text = ownText(el);
      if (!text) continue;
      var rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      var cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      if (parseFloat(cs.opacity) === 0) continue;
      if (items.length >= MAX) { capped = true; break; }
      items.push({
        tag: label(el),
        text: text.slice(0, 60),
        size: Math.round(parseFloat(cs.fontSize)) || 0,
        weight: parseInt(cs.fontWeight, 10) || 400,
        top: Math.round(rect.top),
        bottom: Math.round(rect.bottom),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        above_fold: rect.top < VH
      });
    }

    // The loud element: biggest size, then biggest area, among first-screen
    // text. Restricting to the fold is the correction this rewrite is about —
    // a decorative numeral 2000px down should not decide the page's score.
    var onScreen = items.filter(function (it) { return it.above_fold; });
    var loud = null;
    for (var j = 0; j < onScreen.length; j++) {
      var it = onScreen[j];
      if (!loud) { loud = it; continue; }
      var areaA = (it.right - it.left) * (it.bottom - it.top);
      var areaB = (loud.right - loud.left) * (loud.bottom - loud.top);
      if (it.size > loud.size || (it.size === loud.size && areaA > areaB)) loud = it;
    }

    var bodySize = parseFloat(getComputedStyle(document.body || document.documentElement).fontSize) || 16;

    if (!loud) {
      return { viewport: {w: VW, h: VH}, body_size: bodySize, items: [],
               loud: null, capped: capped };
    }

    // The loud element's own band: its height grown by BAND_PAD on both sides.
    var pad = Math.max(40, (loud.bottom - loud.top) * BAND_PAD);
    var bandLo = loud.top - pad, bandHi = loud.bottom + pad;
    var band = onScreen.filter(function (it) {
      return it !== loud && it.bottom > bandLo && it.top < bandHi;
    });

    // The blank run directly below the loud element, in its horizontal range.
    var below = onScreen.filter(function (it) {
      return it.top >= loud.bottom - 2 && it.right > loud.left && it.left < loud.right;
    }).sort(function (a, b) { return a.top - b.top; });
    var gapBelow = below.length ? Math.round(below[0].top - loud.bottom) : null;

    // Column fill: of the vertical strip the loud element occupies, how much is
    // covered by text before the fold. The strip stops at the fold rather than
    // running a fixed 400px past the element: a hero figure sits in a band
    // whose content spreads horizontally, and measuring its narrow column far
    // down the page charged it for width it never claimed. B3's figure is 183px
    // wide in a 1440px canvas — the KPIs beside it are what fill that band, and
    // a column-only reading called the band 42% empty when it was the page's
    // densest region.
    var stripTop = loud.top;
    var stripBottom = VH;
    var stripHeight = Math.max(1, stripBottom - stripTop);
    var inColumn = onScreen.filter(function (it) {
      return it.top >= stripTop && it.top < stripBottom &&
             it.right > loud.left && it.left < loud.right;
    }).sort(function (a, b) { return a.top - b.top; });
    var covered = 0, cursor = stripTop;
    for (var c = 0; c < inColumn.length; c++) {
      var seg = inColumn[c];
      if (seg.top < cursor) continue;
      covered += seg.bottom - seg.top;
      cursor = seg.bottom;
    }

    // Size ladder: distinct sizes on the first screen, loudest to body.
    var sizeCounts = {};
    for (var s = 0; s < onScreen.length; s++) {
      sizeCounts[onScreen[s].size] = (sizeCounts[onScreen[s].size] || 0) + 1;
    }
    var ladder = Object.keys(sizeCounts).map(Number)
      .sort(function (a, b) { return b - a; });

    // Competitors: text at 75% or more of the loud element's size.
    var competitors = onScreen.filter(function (it) {
      return it !== loud && it.size >= loud.size * 0.75;
    }).map(function (it) {
      return {tag: it.tag, size: it.size, text: it.text.slice(0, 40)};
    });

    var pageH1 = document.querySelector("h1");
    var h1 = null;
    if (pageH1) {
      var h1rect = pageH1.getBoundingClientRect();
      h1 = {text: (pageH1.innerText || "").replace(/\s+/g, " ").trim().slice(0, 60),
            size: Math.round(parseFloat(getComputedStyle(pageH1).fontSize)) || 0,
            above_fold: h1rect.top < VH};
    }

    // Visual mass in the loud element's band. Text geometry alone cannot tell
    // "empty" from "occupied by an image": B4's 64px of blank under its display
    // line is a full-bleed horizon photograph, while B3's 78px is genuinely
    // empty. Counting large visual elements in the band is the cheapest honest
    // signal, and when it fires the tool says it cannot judge the emptiness
    // rather than reporting it as a defect.
    var visualBand = [];
    var visuals = document.querySelectorAll(
      "img,picture,svg,canvas,video,[style*='background-image']," +
      "[class*=plate],[class*=figure],[class*=media],[class*=illustration]");
    for (var v = 0; v < visuals.length; v++) {
      var vel = visuals[v];
      var vr = vel.getBoundingClientRect();
      if (vr.width < 200 || vr.height < 120) continue;
      if (vr.bottom < bandLo || vr.top > bandHi) continue;
      visualBand.push({
        tag: label(vel),
        width: Math.round(vr.width),
        height: Math.round(vr.height)
      });
    }

    // The page's own body-level background image or gradient: a hero that is
    // painted rather than filled with elements.
    var bodyStyle = getComputedStyle(document.body || document.documentElement);
    var pageFill = null;
    if (bodyStyle.backgroundImage && bodyStyle.backgroundImage !== "none") {
      pageFill = bodyStyle.backgroundImage.slice(0, 80);
    }

    return {
      viewport: {w: VW, h: VH},
      body_size: bodySize,
      loud: {tag: loud.tag, text: loud.text, size: loud.size, weight: loud.weight,
             top: loud.top, bottom: loud.bottom},
      band: {lo: Math.round(bandLo), hi: Math.round(bandHi), other_items: band.length,
             visual_items: visualBand},
      gap_below: gapBelow,
      column: {height: Math.round(stripHeight), covered: Math.round(covered),
               items: inColumn.length},
      ladder: ladder,
      size_counts: sizeCounts,
      competitors: competitors,
      hero_items: onScreen.length,
      h1: h1,
      page_fill: pageFill,
      capped: capped
    };
  }
})()"""


# --- pure logic ------------------------------------------------------------


def ladder_gaps(ladder, body_size, factor=LADDER_GAP_FACTOR):
    """Size pairs on the ladder whose ratio exceeds `factor`.

    A ladder of 88/30/20/15 has ratios 2.9, 1.5, 1.3 — every step is walkable.
    A ladder of 70/22/14 has 3.2 between the first two, which leaves a visual
    desert under the display figure: nothing at 30–50px to carry the eye down.
    Returns [(bigger, smaller), ...] with the sizes that straddle the gap.
    """
    steps = [float(size) for size in (ladder or []) if float(size) > 0]
    if not steps:
        return []
    steps = sorted(steps, reverse=True)
    if body_size and steps and steps[-1] > float(body_size) * 1.01:
        steps.append(float(body_size))
    gaps = []
    for bigger, smaller in zip(steps, steps[1:]):
        if smaller and bigger / smaller > factor:
            gaps.append((int(bigger), int(smaller)))
    return gaps


def column_fill(payload):
    """Percentage of the loud element's strip that other text occupies."""
    column = payload.get("column") or {}
    height = float(column.get("height") or 0)
    covered = float(column.get("covered") or 0)
    if height <= 0:
        return 0.0
    return min(100.0, round(covered * 100.0 / height, 1))


def density(payload):
    """Text items per 100,000 CSS px² of first screen. No threshold on purpose."""
    viewport = payload.get("viewport") or {}
    area = float(viewport.get("w") or 0) * float(viewport.get("h") or 0)
    items = float(payload.get("hero_items") or 0)
    if area <= 0:
        return 0.0
    return round(items * 100000.0 / area, 1)


def ratio_to_body(payload):
    """The old type ratio, kept as one number among several, not as a verdict."""
    loud = payload.get("loud") or {}
    size = float(loud.get("size") or 0)
    raw_body = payload.get("body_size")
    # `or` would turn a measured 0 into the fallback; a zero body size means the
    # page is unrenderable, and the ratio is undefined rather than 16.
    body = float(raw_body) if raw_body is not None else BODY_FALLBACK
    if not size or body <= 0:
        return 0.0
    return round(size / body, 2)


def visual_fill(payload):
    """Large visual elements inside the loud element's band, and page-level fill.

    Returns (items, page_fill). `items` is the count of big images, canvases,
    plates and painted blocks that overlap the band; `page_fill` is the body's
    background-image when it has one. Both exist because text geometry cannot
    tell an empty band from one the page has filled with a photograph, and a
    tool that reported B4's horizon shot as "78px of blank" would be wrong in
    the most expensive way — confidently.
    """
    band = payload.get("band") or {}
    items = band.get("visual_items") or []
    return len(items), payload.get("page_fill")


def band_is_painted(payload):
    """True when the band has enough visual mass that emptiness cannot be judged."""
    count, page_fill = visual_fill(payload)
    return count > 0 or bool(page_fill)


def attention_questions(payload):
    """The questions a reviewer answers about the loud element.

    This is the substance of the rewrite. The previous version scored the page;
    a score tells a model nothing it can act on and tells a designer nothing
    they did not already suspect. A question with the measured evidence
    attached is answerable: it names the element, what else is near it, and what
    the page's own heading claims the page is about.
    """
    loud = payload.get("loud") or {}
    if not loud:
        return []
    band = payload.get("band") or {}
    h1 = payload.get("h1") or {}
    questions = []
    size = int(loud.get("size") or 0)
    text = (loud.get("text") or "")[:40]
    others = int(band.get("other_items") or 0)
    gap = payload.get("gap_below")
    fill = column_fill(payload)
    painted = band_is_painted(payload)
    visual_count, _page_fill = visual_fill(payload)

    opening = (f"the loudest thing on the first screen is {loud.get('tag')} at "
               f"{size}px (\"{text}\"), with {others} other text item(s) in its band "
               f"and {fill:g}% of its column filled before the fold")
    # The blank-run clause, the painted-band caveat, and the question itself are
    # assembled separately: writing them as one chained conditional swallowed the
    # opening sentence, because a trailing `if painted else` binds to the whole
    # concatenation rather than to its last term.
    if gap is not None and gap > 8 and not painted:
        opening += f", then {gap}px of blank before the next text"
    if painted:
        if visual_count:
            opening += (f"; the band holds {visual_count} large visual element(s), so "
                        f"the blank may be filled with imagery this tool cannot measure")
        else:
            opening += ("; the page paints its own background, so that blank may be "
                        "imagery this tool cannot measure")
    questions.append(opening + ". Is that the thing this screen exists to show?")

    if h1 and h1.get("above_fold") and h1.get("text"):
        h1_size = int(h1.get("size") or 0)
        if h1_size and size and h1_size < size * 0.6:
            questions.append(
                f"the page's own h1 (\"{h1['text']}\") is {h1_size}px while the display "
                f"figure is {size}px; the heading describes the product and the figure "
                f"describes one measurement — confirm the figure is the more important "
                f"of the two")

    competitors = payload.get("competitors") or []
    if len(competitors) > 1:
        names = ", ".join(f"{c.get('text', '')[:24]} ({c.get('size')}px)"
                          for c in competitors[:3])
        questions.append(
            f"{len(competitors)} elements compete at 75% or more of the loudest "
            f"size ({names}); two focal points cancel each other — decide which one "
            f"wins and step the others down")

    gaps = ladder_gaps(payload.get("ladder"), payload.get("body_size"))
    # A skipped rung is only a problem when the band is thin in text AND not
    # painted. B2 skips 102→22 over a 76.9%-filled column; B4 skips 92→25 over a
    # horizon photograph. B3 skips 70→22 over nothing, which is the case worth
    # raising.
    if gaps and (fill < 55 or (gap is not None and gap > 48)) and not painted:
        pairs = ", ".join(f"{big}px → {small}px" for big, small in gaps[:3])
        questions.append(
            f"the size ladder skips {pairs} while only {fill:g}% of the column is "
            f"filled"
            + (f" and {gap}px of it is blank" if gap is not None and gap > 8 else "")
            + "; the band under the display text carries little, so the display "
              f"figure reads as decorative rather than as the page's work")
    return questions


def classify(payload):
    """Split into (measures, reviews). Nothing here is a failure.

    Every number describes how a page spends its attention, which is a product
    judgement. Reporting one of them as a FAIL would let taste break a build.
    """
    reviews = []
    loud = payload.get("loud") or {}
    if loud:
        reviews.append({
            "check": "ATTENTION", "tag": loud.get("tag"),
            "status": "review", "severity": "review",
            "clause": "expression.md item 4 (focal engineering)",
            "size": loud.get("size"), "text": loud.get("text"),
            "column_fill": column_fill(payload),
            "gap_below": payload.get("gap_below"),
            "message": (f"the loudest first-screen element is {loud.get('tag')} at "
                        f"{loud.get('size')}px; {column_fill(payload):g}% of its column "
                        f"is filled before the fold"),
        })
        gaps = ladder_gaps(payload.get("ladder"), payload.get("body_size"))
        fill = column_fill(payload)
        gap = payload.get("gap_below")
        painted = band_is_painted(payload)
        thin = fill < 55 or (gap is not None and gap > 48)
        if gaps and thin and not painted:
            reviews.append({
                "check": "LADDER", "tag": loud.get("tag"),
                "status": "review", "severity": "review",
                "clause": "expression.md item 1 (type drama)",
                "gaps": [{"from": big, "to": small} for big, small in gaps],
                "column_fill": fill,
                "message": ("the size ladder skips "
                            + ", ".join(f"{big}→{small}px" for big, small in gaps[:3])
                            + f" while the column is only {fill:g}% filled; the display "
                              f"text has little around it to be a focal point of"),
            })
        if painted:
            visual_count, page_fill = visual_fill(payload)
            reviews.append({
                "check": "VISUAL-FILL", "tag": loud.get("tag"),
                "status": "uncertain", "severity": "review",
                "clause": "not measurable from text geometry",
                "visual_items": visual_count,
                "page_background_image": page_fill,
                "message": (f"the band around {loud.get('tag')} "
                            + (f"holds {visual_count} large visual element(s)"
                               if visual_count else "sits on a page-painted background")
                            + "; whether the space reads as composed or as empty is "
                              "a visual judgement this tool cannot make"),
            })
    reviews.append({
        "check": "DENSITY", "tag": "(first screen)",
        "status": "review", "severity": "review",
        "clause": "information, not a verdict",
        "density": density(payload),
        "items": payload.get("hero_items", 0),
        "message": (f"{payload.get('hero_items', 0)} text items on the first screen "
                    f"({density(payload):g} per 100k px²); read it against the brief — "
                    f"a portfolio is legitimately sparse, a dashboard is not"),
    })
    return [], reviews


def build_report(url, payload, viewport=None):
    measures, reviews = classify(payload)
    loud = payload.get("loud") or {}
    return {
        "url": url,
        "verified": True,
        "viewport": viewport or payload.get("viewport"),
        "clause_coverage": CLAUSE_COVERAGE,
        "metrics": {
            "body_size": round(float(payload.get("body_size") or BODY_FALLBACK), 1),
            "loud": {"tag": loud.get("tag"), "text": loud.get("text"),
                     "size": loud.get("size"), "weight": loud.get("weight")},
            "ratio_to_body": ratio_to_body(payload),
            "column_fill": column_fill(payload),
            "gap_below": payload.get("gap_below"),
            "ladder": payload.get("ladder") or [],
            "competitors": payload.get("competitors") or [],
            "hero_items": payload.get("hero_items", 0),
            "density": density(payload),
            "h1": payload.get("h1"),
        },
        "findings": reviews,
        "questions": attention_questions(payload),
        "manual": list(MANUAL_ITEMS),
        "summary": {
            "fail": 0,
            "review": sum(1 for item in reviews if item.get("status") == "review"),
            "uncertain": sum(1 for item in reviews if item.get("status") == "uncertain"),
            "hero_items": payload.get("hero_items", 0),
            "column_fill": column_fill(payload),
            "ratio_to_body": ratio_to_body(payload),
            "visual_fill": visual_fill(payload)[0],
            "capped": bool(payload.get("capped")),
        },
    }


def has_measurable_fail(report):
    """Always False: this tool reads allocation, and allocation is a judgement."""
    return bool(report["summary"]["fail"])


def render_text(report):
    metrics = report["metrics"]
    summary = report["summary"]
    loud = metrics["loud"]
    lines = [
        f"Expression audit (first screen): {report['url']}",
        f"Scope: {report['clause_coverage']}",
    ]
    if not loud.get("tag"):
        lines.append("No text found on the first screen; nothing to read.")
        return "\n".join(lines)
    lines.append(
        f"Loudest: {loud['tag']} at {loud['size']}px, weight {loud['weight']} "
        f"(\"{loud['text']}\")")
    lines.append(
        f"Column fill: {metrics['column_fill']:g}% of the strip it occupies is text "
        f"before the fold; blank below it: {metrics['gap_below']}px")
    lines.append(
        f"Density: {metrics['hero_items']} text items on the first screen "
        f"({metrics['density']:g} per 100k px²)")
    ladder = metrics["ladder"]
    if ladder:
        lines.append("Size ladder (first screen): "
                     + " / ".join(f"{size}" for size in ladder) + " px")
    if metrics["ratio_to_body"]:
        lines.append(f"Reference: loudest / body = {metrics['ratio_to_body']:g}x "
                     f"(body {metrics['body_size']:g}px) — reported, not judged")
    if metrics["competitors"]:
        lines.append("Competing at 75%+ of the loudest size: "
                     + ", ".join(f"{c.get('text', '')[:20]} ({c.get('size')}px)"
                                 for c in metrics["competitors"][:4]))
    lines.append("")
    for finding in report["findings"]:
        if finding.get("status") == "uncertain":
            lines.append(f"UNCERTAIN [{finding['check']}] {finding.get('message')}")
    if any(item.get("status") == "uncertain" for item in report["findings"]):
        lines.append("")
    if report["questions"]:
        lines.append("Questions to answer (the measurement cannot):")
        for question in report["questions"]:
            lines.append(f"  ? {question}")
        lines.append("")
    lines.append("Left to the polish pass:")
    for item in report["manual"]:
        lines.append(f"  - {item}")
    lines.append("")
    lines.append(f"Summary: {summary['review']} review item(s), "
                 f"{summary['uncertain']} uncertain"
                 + (f" ({summary['visual_fill']} visual element(s) the text geometry "
                    f"cannot judge)" if summary.get("visual_fill") else "")
                 + ", no exit status (allocation is a judgement, not a conformance rule)")
    if summary.get("capped"):
        lines.append(f"NOTE: sampling stopped at {MAX_SAMPLES} text nodes")
    return "\n".join(lines)


# --- browser path ---------------------------------------------------------


def _collect(session, session_id):
    expression = (
        "(async () => {"
        "try { if (document.fonts && document.fonts.ready) await document.fonts.ready; }"
        " catch (e) {}"
        "return " + COLLECTOR_JS
        .replace("__MAX_SAMPLES__", str(MAX_SAMPLES))
        .replace("__DISPLAY_MIN__", str(DISPLAY_MIN))
        .replace("__BAND_PAD__", str(BAND_PAD_FACTOR)) + ";"
        "})()"
    )
    value = session.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": True},
        session=session_id,
    )["result"].get("value")
    if not isinstance(value, str):
        raise cdp.BrowserError("collector returned no data (evaluation blocked?)")
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise cdp.BrowserError("collector returned unexpected data")
    if payload.get("error"):
        raise cdp.BrowserError(f"collector failed on the page: {payload['error']}")
    return payload


def audit_url(url, width=1440, height=900):
    """Load at desktop size, because the allocation decision is composed there."""
    with cdp.PageSession(url, width=width, height=height) as page:
        page.settle()
        return _collect(page.session, page.session_id)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read how a page allocates attention on its first screen: the "
                    "loudest element, its column fill, the size ladder, density — and "
                    "the questions those numbers raise.")
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true",
                        help="print the JSON report instead of text")
    parser.add_argument("--allow-private", action="store_true",
                        help="allow non-public, non-loopback addresses")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        url = visual_capture.validate_url(args.url, allow_private=args.allow_private)
    except visual_capture.UrlRejected as exc:
        print(json.dumps({"verified": False, "reason": f"URL rejected: {exc}"},
                         ensure_ascii=False))
        return 3

    try:
        payload = audit_url(url, width=args.width, height=args.height)
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
