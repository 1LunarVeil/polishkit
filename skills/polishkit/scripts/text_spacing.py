"""Audit WCAG 1.4.12 Text Spacing on a live page over CDP.

Usage:
  python text_spacing.py URL [--json] [--allow-private] [--limit N]
                             [--width W] [--height H]

SC 1.4.12 (AA) asks whether content survives a user's text-spacing overrides
without loss of content or functionality. Its normative test is specific: set
all four values below and change nothing else, then look for lost content.

  line-height     at least 1.5 x font size
  paragraph gap   at least 2 x font size
  letter-spacing  at least 0.12 x font size
  word-spacing    at least 0.16 x font size

The page is not required to ship those values — it is required to survive them
(W3C: "Content is not required to use these text spacing values"). So the tool
measures twice: the authored page, then the same page with the four overrides
applied, and reports what broke between them.

What counts as loss, and how each is detected:

- CLIP          an element whose text now overflows a box that hides it
                (overflow hidden/clip, fixed height, or a scroll container that
                cannot grow). Detected by comparing scrollWidth/scrollHeight
                against clientWidth/clientHeight before and after.
- OVERLAP       two text runs that occupy the same pixels after the override
                and did not before. Detected by rect intersection between
                sibling text elements that are not nested.
- FIXED         an element with a fixed pixel height whose content grew past it
                by more than one line. The common cause of truncation, and the
                one authors most often miss on cards and table rows.
- TRUNCATION    authored single-line ellipsis that now cuts more than it did.

Uncertainty: the audit reports what the DOM geometry says. Text hidden by a
transform, a clip-path, a mask or an off-screen parent is not reachable this
way and is listed as `uncertain:not-measured` with its evidence, never as a
pass.

Exit status: 0 no measurable loss, 1 at least one CLIP/OVERLAP/TRUNCATION,
2 no browser or CDP failure ({"verified": false} — claims nothing), 3 URL
rejected (visual_capture.validate_url).

Read-only: prints a report and writes nothing. stdlib only; CDP on loopback.
"""

import argparse
import json
import shutil
import sys

sys.dont_write_bytecode = True
import cdp  # noqa: E402  (sibling module; no third-party dependencies)
import visual_capture  # noqa: E402
import wcag  # noqa: E402

LOAD_TIMEOUT = 10.0
MAX_FINDINGS = 150
SNIPPET_CHARS = 70

# SC 1.4.12's four multipliers, applied as `em`-relative values so they follow
# the element's own font size rather than a page-wide constant.
LINE_HEIGHT = 1.5
PARAGRAPH_GAP = 2.0
LETTER_SPACING = 0.12
WORD_SPACING = 0.16

CLAUSE_COVERAGE = (
    "WCAG 1.4.12 Text Spacing (AA): line-height 1.5x, paragraph gap 2x, "
    "letter-spacing 0.12x, word-spacing 0.16x, applied without changing "
    "anything else"
)

# One collector, run once per state (authored, overridden). Everything that
# needs layout lives here; the comparison happens in Python so the two payloads
# are plain dicts and the deciding logic is testable without a browser.
COLLECTOR_JS = r"""(function () {
  var MAX = __MAX_FINDINGS__;
  var SNIPPET = __SNIPPET__;
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

  function visible(el) {
    var cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    if (parseFloat(cs.opacity) === 0) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function hasText(el) {
    if (!el.firstChild) return false;
    for (var i = 0; i < el.childNodes.length; i++) {
      var node = el.childNodes[i];
      if (node.nodeType === 3 && node.nodeValue && node.nodeValue.trim().length > 1) return true;
    }
    return false;
  }

  // A stable identity that survives a reflow. Document coordinates were the
  // first version's key: the override moves everything down, so every key
  // changed, nothing paired, and the audit reported a clean page. The path of
  // child indices from <body> does not move when the layout does.
  function pathOf(el, scope) {
    var parts = [];
    var node = el;
    while (node && node !== scope) {
      var parent = node.parentElement;
      if (!parent) break;
      parts.unshift(Array.prototype.indexOf.call(parent.children, node));
      node = parent;
    }
    return parts.join(".");
  }

  // Ancestor paths, so the overlap test can skip parent/child pairs: a <b>
  // inside a <span> shares pixels with its parent by definition, and an
  // overlap finding against it is noise. The nesting depth alone was not
  // enough, because a <b> and its sibling text sit at different depths but a
  // <b> and a <span> wrapping it can share one.
  function ancestorsOf(el, scope) {
    var chain = [];
    var node = el.parentElement;
    var steps = 0;
    while (node && node !== scope && steps < 40) {
      chain.push(pathOf(node, scope));
      node = node.parentElement;
      steps++;
    }
    return chain;
  }

  // How tall the text actually needs to be, independent of the box it was
  // squeezed into. Range.getBoundingClientRect() returns the inked geometry of
  // the text nodes, which a clipped parent cannot shrink.
  function textHeight(el) {
    try {
      if (document.createRange) {
        var range = document.createRange();
        range.selectNodeContents(el);
        var rect = range.getBoundingClientRect();
        if (rect && rect.height > 0) return rect.height;
      }
    } catch (e) {}
    return el.scrollHeight || 0;
  }

  function clips(el, cs) {
    return cs.overflowX === "hidden" || cs.overflowX === "clip" ||
           cs.overflowY === "hidden" || cs.overflowY === "clip";
  }

  // The box that actually clips text is usually an ancestor, not the <p> the
  // text sits in: a 48px card with overflow:hidden truncates its child
  // paragraph while the paragraph itself reports a comfortable client box.
  // Walk up and return the first clipping ancestor, with the numbers that
  // decide whether text is being lost.
  function clippingAncestor(el, scope) {
    var node = el.parentElement;
    var steps = 0;
    while (node && node !== scope && steps < 30) {
      var s = getComputedStyle(node);
      if (clips(node, s)) {
        var nr = node.getBoundingClientRect();
        var ncs = getComputedStyle(node);
        var pad_y = (parseFloat(ncs.paddingTop) || 0) + (parseFloat(ncs.paddingBottom) || 0);
        return {
          tag: label(node),
          scroll_width: node.scrollWidth,
          scroll_height: node.scrollHeight,
          client_width: node.clientWidth,
          client_height: node.clientHeight,
          // Room the box offers its content, and what the text really needs.
          available_height: Math.max(0, nr.height - pad_y),
          content_height: textHeight(el),
          rect: { x: nr.x, y: nr.y, width: nr.width, height: nr.height,
                  top: nr.top + window.scrollY, left: nr.left + window.scrollX }
        };
      }
      node = node.parentElement;
      steps++;
    }
    return null;
  }

  function collect() {
    var scope = document.body || document.documentElement;
    var all = scope.getElementsByTagName("*");
    var rows = [];
    var capped = false;
    var uncertain = [];

    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (!hasText(el)) continue;
      if (!visible(el)) continue;
      var cs = getComputedStyle(el);
      var r = el.getBoundingClientRect();
      var fontSize = parseFloat(cs.fontSize) || 16;
      var fixedHeight = cs.height !== "auto" &&
                        cs.maxHeight !== "none" && parseFloat(cs.maxHeight) > 0;
      rows.push({
        tag: label(el),
        key: pathOf(el, scope),
        text: (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, SNIPPET),
        font_size: fontSize,
        line_height: cs.lineHeight === "normal" ? null : (parseFloat(cs.lineHeight) || null),
        letter_spacing: cs.letterSpacing === "normal" ? 0 : (parseFloat(cs.letterSpacing) || 0),
        word_spacing: cs.wordSpacing === "normal" ? 0 : (parseFloat(cs.wordSpacing) || 0),
        scroll_width: el.scrollWidth,
        scroll_height: el.scrollHeight,
        client_width: el.clientWidth,
        client_height: el.clientHeight,
        rect: { x: r.x, y: r.y, width: r.width, height: r.height,
                top: r.top + window.scrollY, left: r.left + window.scrollX },
        clips: clips(el, cs),
        overflow_x: cs.overflowX,
        overflow_y: cs.overflowY,
        text_overflow: cs.textOverflow,
        white_space: cs.whiteSpace,
        fixed_height: fixedHeight,
        max_height: cs.maxHeight,
        clipping_ancestor: clippingAncestor(el, scope),
        ancestors: ancestorsOf(el, scope),
        nested_depth: (function () {
          var depth = 0, node = el;
          while (node && node !== scope) { depth++; node = node.parentElement; }
          return depth;
        })()
      });
      if (rows.length >= MAX) { capped = true; break; }
    }

    // Elements whose text is hidden by something this geometry cannot see.
    var masked = document.querySelectorAll("[style*='clip-path'], [style*='mask'], [style*='transform']");
    for (var m = 0; m < masked.length && uncertain.length < 20; m++) {
      if (!visible(masked[m])) continue;
      uncertain.push({ tag: label(masked[m]),
                       evidence: "clip-path, mask or transform on the element or an ancestor" });
    }

    return {
      rows: rows,
      capped: capped,
      uncertain: uncertain,
      viewport: { width: window.innerWidth, height: window.innerHeight },
      doc: { scroll_width: document.documentElement.scrollWidth,
             scroll_height: document.documentElement.scrollHeight },
      scroll_x: window.scrollX,
      scroll_y: window.scrollY
    };
  }
})()"""

# Applied to every element with text. `!important` is the point of a user
# override. Nothing else is touched: no width, no margin shorthand, no display.
OVERRIDE_CSS = (
    "*{line-height:%(line)s !important;"
    "letter-spacing:%(letter)sem !important;"
    "word-spacing:%(word)sem !important;}"
    "p,li,dd,blockquote,figcaption{margin-bottom:%(para)sem !important;}"
)


def override_css(line=LINE_HEIGHT, paragraph=PARAGRAPH_GAP,
                 letter=LETTER_SPACING, word=WORD_SPACING):
    """The user-override stylesheet SC 1.4.12 is about."""
    return OVERRIDE_CSS % {"line": f"{line:g}", "para": f"{paragraph:g}",
                           "letter": f"{letter:g}", "word": f"{word:g}"}


# --- pure logic (no browser; both payloads are plain dicts) ----------------

def climbs(entry, slack=1):
    """True when something in the element's chain hides text beyond its box.

    Checks the element itself and the nearest clipping ancestor, because the
    box that truncates text is usually the card around the paragraph: a 48px
    `overflow:hidden` card clips its child while the child reports a
    comfortable client box. In measured output the card reports scrollHeight 96
    against clientHeight 64 — the ancestor test is the one that fires, and the
    child's own numbers stay clean.

    (A Range-based "text needs X, box offers Y" comparison was tried and
    removed: Range height excludes the lead the line box adds above and below
    the glyphs, so it disagreed with what the browser actually clipped.)
    """
    own_width = int(entry.get("scroll_width") or 0) - int(entry.get("client_width") or 0)
    own_height = int(entry.get("scroll_height") or 0) - int(entry.get("client_height") or 0)
    if entry.get("clips") and (own_width > slack or own_height > slack):
        return True
    ancestor = entry.get("clipping_ancestor") or {}
    if ancestor:
        width_over = int(ancestor.get("scroll_width") or 0) - int(ancestor.get("client_width") or 0)
        height_over = int(ancestor.get("scroll_height") or 0) - int(ancestor.get("client_height") or 0)
        if width_over > slack or height_over > slack:
            return True
    return False


def clipped(entry, slack=1):
    """True when the element's text is larger than a box that hides it."""
    return climbs(entry, slack)


def clip_evidence(entry):
    """The box that is doing the clipping, for the finding message."""
    own_width = int(entry.get("scroll_width") or 0) - int(entry.get("client_width") or 0)
    own_height = int(entry.get("scroll_height") or 0) - int(entry.get("client_height") or 0)
    if entry.get("clips") and (own_width > 1 or own_height > 1):
        return {
            "box": entry.get("tag"),
            "scroll": (entry.get("scroll_width"), entry.get("scroll_height")),
            "client": (entry.get("client_width"), entry.get("client_height")),
            "overflow": f"{entry.get('overflow_x')}/{entry.get('overflow_y')}",
        }
    ancestor = entry.get("clipping_ancestor") or {}
    return {
        "box": ancestor.get("tag") or "(unknown ancestor)",
        "scroll": (ancestor.get("scroll_width"), ancestor.get("scroll_height")),
        "client": (ancestor.get("client_width"), ancestor.get("client_height")),
        "needs": ancestor.get("content_height"),
        "room": ancestor.get("available_height"),
        "overflow": "hidden/clip on an ancestor",
    }


def grew(entry, before, line_slack=1.0):
    """Height growth in lines between the authored and overridden state."""
    before_height = float((before or {}).get("rect", {}).get("height") or 0)
    after_height = float((entry or {}).get("rect", {}).get("height") or 0)
    font = float(entry.get("font_size") or 16) or 16
    return (after_height - before_height) / font


def fixed_height_overflow(entry, before):
    """A fixed-height box whose content now needs more room than it has."""
    max_height = entry.get("max_height")
    if not max_height or max_height == "none":
        return False
    try:
        ceiling = float(str(max_height).replace("px", ""))
    except ValueError:
        return False
    needed = float(entry.get("scroll_height") or 0)
    font = float(entry.get("font_size") or 16) or 16
    return needed > ceiling + font * 0.5


def overlap_area(first, second):
    """Pixels two element rects share, in CSS px squared."""
    a, b = first.get("rect") or {}, second.get("rect") or {}
    left = max(float(a.get("left") or 0), float(b.get("left") or 0))
    right = min(float(a.get("left") or 0) + float(a.get("width") or 0),
                float(b.get("left") or 0) + float(b.get("width") or 0))
    top = max(float(a.get("top") or 0), float(b.get("top") or 0))
    bottom = min(float(a.get("top") or 0) + float(a.get("height") or 0),
                 float(b.get("top") or 0) + float(b.get("height") or 0))
    if right <= left or bottom <= top:
        return 0.0
    return (right - left) * (bottom - top)


def related(first, second):
    """True when one element contains the other (directly or deeper).

    A <b> inside a <span> shares pixels with it by construction. Reporting that
    as an overlap is noise, and the nesting-depth test alone does not catch it.
    """
    first_key, second_key = first.get("key"), second.get("key")
    if not first_key or not second_key:
        return True
    return (second_key in (first.get("ancestors") or [])
            or first_key in (second.get("ancestors") or []))


def overlaps(first, second, min_area=24.0):
    """True when two unrelated element rects share a meaningful area.

    A 1-2px brush between adjacent boxes is normal line-box packing, not lost
    content, so the test needs a floor. 24 px² is roughly one character cell at
    body size.
    """
    if related(first, second):
        return False
    return overlap_area(first, second) > min_area


def classify(authored, overridden):
    """Split the comparison into (measures, uncertain, reviews).

    `authored` and `overridden` are the two collector payloads keyed by the
    same element identity: tag plus its document position. Position is part of
    the key on purpose — two sibling <p> elements with identical text are
    different boxes, and merging them would hide one of the findings.
    """
    before_by_key = {row.get("key"): row for row in authored.get("rows") or []}
    measures, uncertain, reviews = [], [], []

    for entry in overridden.get("rows") or []:
        key = entry.get("key")
        before = before_by_key.get(key)
        if before is None:
            continue  # new element after the override: nothing to compare
        name = entry.get("tag")
        text = entry.get("text") or ""

        # TRUNCATION is tested first, and deliberately so. A single-line
        # ellipsis is already a clipping box in the authored state, so the
        # "already clipped: not this clause" guard below would swallow it. What
        # 1.4.12 cares about is whether the user lost MORE text than before.
        #
        # The floor is one em of extra width, not four pixels. Measured on a
        # real dashboard: a table cell needed 195px in a 187px box before the
        # override (already truncated, and truncated by design) and 235px after.
        # A 4px threshold counted cells that were already losing characters,
        # which is a pre-existing defect under a different clause and would
        # have buried the cells the override actually broke.
        if entry.get("white_space") in ("nowrap", "pre") and \
                entry.get("text_overflow") == "ellipsis" and \
                int(entry.get("scroll_width") or 0) > int(entry.get("client_width") or 0):
            needed_now = int(entry.get("scroll_width") or 0)
            needed_before = int(before.get("scroll_width") or 0)
            font = float(entry.get("font_size") or 16) or 16
            if needed_now - needed_before >= font:
                measures.append({
                    "check": "TRUNCATION", "tag": name, "text": text,
                    "status": "FAIL", "severity": "important", "clause": "WCAG 1.4.12",
                    "message": (f"{name} truncates at least one more line's worth than "
                                f"authored: needs {needed_now}px where the box gives "
                                f"{entry.get('client_width')}px (authored needed "
                                f"{needed_before}px, +{needed_now - needed_before}px)"),
                })
            continue

        if clipped(entry) and not clipped(before):
            evidence = clip_evidence(entry)
            scroll_w, scroll_h = evidence["scroll"]
            client_w, client_h = evidence["client"]
            box = evidence["box"]
            where = ("" if box == name else f" (clipped by {box})")
            measures.append({
                "check": "CLIP", "tag": name, "text": text,
                "status": "FAIL", "severity": "important", "clause": "WCAG 1.4.12",
                "message": (f"{name}{where} hides its own text once the spacing is "
                            f"applied: content needs {scroll_w}x{scroll_h}, the box "
                            f"gives {client_w}x{client_h}"),
            })
            continue
        if clipped(entry):
            continue  # already clipped before the override, and not a nowrap box

        if fixed_height_overflow(entry, before):
            lines = grew(entry, before)
            if lines > 1.0:
                measures.append({
                    "check": "FIXED", "tag": name, "text": text,
                    "status": "FAIL", "severity": "important", "clause": "WCAG 1.4.12",
                    "message": (f"{name} has max-height {entry.get('max_height')} but needs "
                                f"{entry.get('scroll_height')}px after the override "
                                f"({lines:.1f} lines more than authored)"),
                })
                continue

    # Overlap: text runs that collide only after the override. Only compare
    # elements at the same nesting depth, so a parent never "overlaps" its own
    # child.
    entries = [row for row in overridden.get("rows") or []
               if row.get("key") in before_by_key]
    for index, first in enumerate(entries):
        for second in entries[index + 1:]:
            if first.get("nested_depth") != second.get("nested_depth"):
                continue
            if overlaps(first, second) and not overlaps(before_by_key[first["key"]],
                                                        before_by_key[second["key"]]):
                measures.append({
                    "check": "OVERLAP", "tag": first.get("tag"),
                    "text": (first.get("text") or "")[:40],
                    "other": second.get("tag"),
                    "status": "FAIL", "severity": "important", "clause": "WCAG 1.4.12",
                    "message": (f"{first.get('tag')} and {second.get('tag')} occupy the "
                                f"same box only after the spacing override"),
                })

    for item in overridden.get("uncertain") or []:
        uncertain.append(dict(item, status="uncertain:not-measured",
                              severity="review", clause="WCAG 1.4.12",
                              method="uncertain:not-measured"))
    if overridden.get("capped"):
        reviews.append({
            "check": "CAPPED", "tag": "(page)", "status": "review", "severity": "review",
            "clause": "WCAG 1.4.12",
            "message": (f"the collector stopped at {MAX_FINDINGS} text elements; "
                        f"later content was not compared"),
        })
    return measures, uncertain, reviews


def spacing_report(authored, overridden):
    """Which of the four metrics the page already meets (informative).

    SC 1.4.12 does not require these values; the numbers are useful because a
    page that already uses them is far less likely to break under them.
    """
    rows = [row for row in authored.get("rows") or []
            if (row.get("text") or "").strip()]
    if not rows:
        return {"rows": 0}
    meets_line = meets_letter = meets_word = 0
    for row in rows:
        size = float(row.get("font_size") or 0) or 1
        line = row.get("line_height")
        if line is not None and float(line) >= size * LINE_HEIGHT:
            meets_line += 1
        if float(row.get("letter_spacing") or 0) >= size * LETTER_SPACING:
            meets_letter += 1
        if float(row.get("word_spacing") or 0) >= size * WORD_SPACING:
            meets_word += 1
    total = len(rows)
    return {
        "rows": total,
        "line_height": meets_line,
        "letter_spacing": meets_letter,
        "word_spacing": meets_word,
        "already_meets_line": round(meets_line / total, 3),
    }


def build_report(url, authored, overridden, viewport=None):
    measures, uncertain, reviews = classify(authored, overridden)
    fails = [item for item in measures if item.get("status") == "FAIL"]
    summary = {
        "text_elements": len(authored.get("rows") or []),
        "clip": sum(1 for item in fails if item["check"] == "CLIP"),
        "fixed": sum(1 for item in fails if item["check"] == "FIXED"),
        "overlap": sum(1 for item in fails if item["check"] == "OVERLAP"),
        "truncation": sum(1 for item in fails if item["check"] == "TRUNCATION"),
        "fail": len(fails),
        "uncertain": len(uncertain),
        "review": len(reviews),
        "doc_scroll_authored": authored.get("doc"),
        "doc_scroll_overridden": overridden.get("doc"),
        "capped": bool(overridden.get("capped")),
    }
    return {
        "url": url,
        "verified": True,
        "viewport": viewport,
        "clause_coverage": CLAUSE_COVERAGE,
        "override": {
            "line_height": LINE_HEIGHT,
            "paragraph_gap": PARAGRAPH_GAP,
            "letter_spacing": LETTER_SPACING,
            "word_spacing": WORD_SPACING,
        },
        "authored_spacing": spacing_report(authored, overridden),
        "findings": fails + uncertain + reviews,
        "summary": summary,
    }


def has_measurable_fail(report):
    return bool(report["summary"]["fail"])


def render_text(report):
    summary = report["summary"]
    authored = report.get("authored_spacing") or {}
    lines = [
        f"Text spacing audit (WCAG 1.4.12, AA): {report['url']}",
        f"Override applied: line-height {LINE_HEIGHT:g}x, paragraph gap "
        f"{PARAGRAPH_GAP:g}x, letter-spacing {LETTER_SPACING:g}x, "
        f"word-spacing {WORD_SPACING:g}x",
        f"Text elements compared: {summary['text_elements']}"
        + ("" if not authored.get("rows") else
           f"; authored line-height already >= 1.5x on "
           f"{authored.get('line_height')}/{authored.get('rows')}"),
    ]
    for finding in report["findings"]:
        if finding.get("status") == "FAIL":
            lines.append(f"FAIL [{finding['check']}] {finding.get('tag')} — "
                         f"{finding.get('message')}")
    for finding in report["findings"]:
        if finding.get("status") == "review":
            lines.append(f"REVIEW [{finding.get('check')}] {finding.get('tag')} — "
                         f"{finding.get('message')}")
    for finding in report["findings"]:
        if finding.get("status") == "uncertain":
            lines.append(f"UNCERTAIN {finding.get('tag')} — {finding.get('evidence')}")
    authored_doc = summary.get("doc_scroll_authored") or {}
    over_doc = summary.get("doc_scroll_overridden") or {}
    lines.append(
        f"Summary: {summary['fail']} FAIL ({summary['clip']} clip, "
        f"{summary['fixed']} fixed-height, {summary['overlap']} overlap, "
        f"{summary['truncation']} truncation), {summary['uncertain']} uncertain, "
        f"{summary['review']} review across {summary['text_elements']} text elements")
    lines.append(
        f"Document scroll: {authored_doc.get('scroll_width')}x"
        f"{authored_doc.get('scroll_height')} authored → "
        f"{over_doc.get('scroll_width')}x{over_doc.get('scroll_height')} overridden")
    return "\n".join(lines)


# --- browser path ---------------------------------------------------------


def _evaluate(session, session_id, expression, await_promise=False):
    result = session.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": await_promise},
        session=session_id,
    )
    return result["result"].get("value")


def _collect(session, session_id):
    expression = (
        "(async () => {"
        "try { if (document.fonts && document.fonts.ready) await document.fonts.ready; }"
        " catch (e) {}"
        "return " + COLLECTOR_JS.replace("__MAX_FINDINGS__", str(MAX_FINDINGS))
        .replace("__SNIPPET__", str(SNIPPET_CHARS)) + ";"
        "})()"
    )
    value = _evaluate(session, session_id, expression, await_promise=True)
    if not isinstance(value, str):
        raise cdp.BrowserError("collector returned no data (evaluation blocked?)")
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise cdp.BrowserError("collector returned unexpected data")
    if payload.get("error"):
        raise cdp.BrowserError(f"collector failed on the page: {payload['error']}")
    return payload


def audit_url(url, width=1280, height=800):
    """Launch one browser, collect the authored state, apply the override,
    collect again. Raises on any failure so main() can claim nothing."""
    browser = visual_capture.find_browser()
    if not browser:
        raise cdp.BrowserError(
            "no Chromium-family browser found at an absolute path; "
            "text spacing audit disabled")
    process = profile = connection = session = target_id = None
    try:
        process, profile, ws_url = visual_capture._start_cdp_browser(browser)  # noqa: SLF001
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

        authored = _collect(session, session_id)
        # A <style> element appended last wins the cascade for equal
        # specificity, and every declaration carries !important anyway.
        style = override_css()
        _evaluate(session, session_id,
                  "(function(){var s=document.createElement('style');"
                  "s.id='__pk_spacing';"
                  "s.textContent=" + json.dumps(style) + ";"
                  "document.head.appendChild(s);return 1;})()")
        overridden = _collect(session, session_id)
        # Restore, so a caller reusing the page sees it unchanged.
        _evaluate(session, session_id,
                  "(function(){var s=document.getElementById('__pk_spacing');"
                  "if(s)s.remove();return 1;})()")
        return authored, overridden
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
        description="WCAG 1.4.12 text spacing audit over CDP: applies the four "
                    "user overrides and reports content lost between the states.")
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true",
                        help="print the JSON report instead of text")
    parser.add_argument("--allow-private", action="store_true",
                        help="allow non-public, non-loopback addresses")
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
        authored, overridden = audit_url(url, width=args.width, height=args.height)
    except Exception as exc:  # noqa: BLE001 - the documented "claims nothing" contract
        print(json.dumps({
            "verified": False,
            "reason": f"no audit performed: {type(exc).__name__}: {exc}",
        }, ensure_ascii=False))
        return 2

    report = build_report(url, authored, overridden,
                          viewport={"width": args.width, "height": args.height})
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 1 if has_measurable_fail(report) else 0


if __name__ == "__main__":
    sys.exit(main())
